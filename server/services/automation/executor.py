#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化任务执行器。
负责自动化任务完整执行链路与执行态收敛。
"""

import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from server.state import (
    AUTO_TASK_RUNTIME_ERROR,
    AUTO_TASK_RUNTIME_IDLE,
    AUTO_TASK_RUNTIME_RUNNING,
    auto_execution_lock,
    auto_executions,
    auto_task_lock,
    auto_tasks,
    clear_auto_task_running,
    clear_auto_task_stop_flag,
    get_next_auto_execution_id,
    is_auto_task_stopped,
    task_lock,
    tasks,
    update_auto_task_status,
)
from server.utils import add_log
from server.utils.storage import save_auto_execution

from .favorites_fetcher import fetch_favorites
from .local_scanner import scan_local_albums
from .task_creator import create_batch_download_tasks


def execute_auto_sync(
    auto_task_id: int,
    scheduler=None,
) -> None:
    """执行自动同步任务。"""
    auto_task = _get_auto_task_snapshot(auto_task_id)
    if auto_task is None:
        clear_auto_task_running(auto_task_id)
        return

    execution = _create_execution_record(auto_task)
    execution_id = execution['id']

    _update_auto_task_state(
        auto_task_id,
        runtime_status=AUTO_TASK_RUNTIME_RUNNING,
        current_execution_id=execution_id,
    )

    try:
        add_log(execution_id, 'info', f"[自动化] 开始执行自动同步任务: {auto_task['name']}")

        favorite_albums = _fetch_favorite_albums(auto_task, execution_id)
        execution['scanned_count'] = len(favorite_albums)

        if not favorite_albums:
            _complete_execution_with_no_albums(execution)
            return

        local_albums = _scan_local_albums(auto_task['download_dir'], execution_id)
        execution['local_count'] = len(local_albums)

        albums_to_download = [aid for aid in favorite_albums if aid not in local_albums]
        skipped_count = len(favorite_albums) - len(albums_to_download)

        execution['to_download_count'] = len(albums_to_download)
        execution['skipped_count'] = skipped_count

        _log_download_summary(execution_id, albums_to_download, skipped_count)

        if albums_to_download:
            downloaded_count = _process_batch_downloads(
                albums_to_download,
                auto_task,
                execution,
                execution_id,
            )
            add_log(execution_id, 'success', f'[自动化] 所有批次处理完成，共尝试下载 {len(albums_to_download)} 个本子')
        else:
            add_log(execution_id, 'success', '[自动化] 没有新本子需要下载')
            downloaded_count = 0

        task_for_schedule = _update_task_statistics(auto_task['id'], downloaded_count, skipped_count)

        if scheduler:
            from .scheduler import update_next_run_time

            task_for_schedule = task_for_schedule or _get_auto_task_snapshot(auto_task['id']) or auto_task
            update_next_run_time(scheduler, task_for_schedule)
            _update_auto_task_next_run(auto_task['id'], task_for_schedule.get('next_run'))

        execution['status'] = 'completed'
        execution['end_time'] = datetime.now().isoformat()
        with auto_execution_lock:
            auto_executions[execution_id] = deepcopy(execution)
        save_auto_execution(execution)
        add_log(execution_id, 'success', '[自动化] 任务执行完成')

    except Exception as e:
        _handle_execution_error(execution, e, execution_id)
        _update_auto_task_state(auto_task_id, runtime_status=AUTO_TASK_RUNTIME_ERROR, current_execution_id=None)

    finally:
        latest_state = _get_auto_task_snapshot(auto_task_id)
        if latest_state and latest_state.get('runtime_status') != AUTO_TASK_RUNTIME_ERROR:
            _update_auto_task_state(auto_task_id, runtime_status=AUTO_TASK_RUNTIME_IDLE, current_execution_id=None)
        clear_auto_task_stop_flag(auto_task['id'])
        clear_auto_task_running(auto_task['id'])
        _save_task_config(auto_task_id, execution_id)


def _get_auto_task_snapshot(auto_task_id: int) -> Optional[Dict[str, Any]]:
    with auto_task_lock:
        auto_task = auto_tasks.get(auto_task_id)
        if not auto_task:
            return None
        return deepcopy(auto_task)


def _update_auto_task_state(
    auto_task_id: int,
    runtime_status: Optional[str] = None,
    current_execution_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    with auto_task_lock:
        auto_task = auto_tasks.get(auto_task_id)
        if not auto_task:
            return None
        update_auto_task_status(auto_task, runtime_status=runtime_status, current_execution_id=current_execution_id)
        return deepcopy(auto_task)


def _update_auto_task_next_run(auto_task_id: int, next_run: Optional[str]) -> None:
    with auto_task_lock:
        auto_task = auto_tasks.get(auto_task_id)
        if not auto_task:
            return
        auto_task['next_run'] = next_run


def _create_execution_record(auto_task: Dict[str, Any]) -> Dict[str, Any]:
    execution_id = get_next_auto_execution_id()
    execution = {
        'id': execution_id,
        'auto_task_id': auto_task['id'],
        'auto_task_name': auto_task['name'],
        'status': 'running',
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'scanned_count': 0,
        'local_count': 0,
        'to_download_count': 0,
        'skipped_count': 0,
        'downloaded_task_ids': [],
        'error': None,
    }
    with auto_execution_lock:
        auto_executions[execution_id] = execution
    save_auto_execution(execution)
    return execution


def _fetch_favorite_albums(auto_task: Dict[str, Any], execution_id: int) -> List[str]:
    favorite_albums = fetch_favorites(
        username=auto_task['username'],
        password=auto_task['password'],
        client_impl=auto_task.get('client_impl', 'api'),
        execution_id=execution_id,
    )
    unique_albums = [aid for aid in favorite_albums if str(aid).isdigit()]
    add_log(execution_id, 'info', f'[自动化] 总共找到 {len(unique_albums)} 个唯一本子')
    return unique_albums


def _scan_local_albums(download_dir: str, execution_id: int) -> set:
    try:
        local_albums = scan_local_albums(download_dir)
        add_log(execution_id, 'info', f'[自动化] 本地已有 {len(local_albums)} 个本子')
        return local_albums
    except OSError as e:
        add_log(execution_id, 'error', f'[自动化] 读取本地目录失败: {str(e)}')
        return set()


def _log_download_summary(execution_id: int, albums_to_download: List[str], skipped_count: int) -> None:
    add_log(
        execution_id,
        'info',
        f'[自动化] 需要下载: {len(albums_to_download)} 个，跳过: {skipped_count} 个',
    )
    if albums_to_download:
        sample = ','.join(albums_to_download[:5])
        suffix = ' ...' if len(albums_to_download) > 5 else ''
        add_log(execution_id, 'info', f'[自动化] 待下载ID样本: {sample}{suffix}')


def _update_task_statistics(auto_task_id: int, downloaded_count: int, skipped_count: int) -> Optional[Dict[str, Any]]:
    now = datetime.now()
    with auto_task_lock:
        auto_task = auto_tasks.get(auto_task_id)
        if not auto_task:
            return None

        previous_last_run = auto_task.get('last_run')

        auto_task['run_count'] = auto_task.get('run_count', 0) + 1
        auto_task['skipped_count'] = auto_task.get('skipped_count', 0) + skipped_count

        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_last_run_date = None
        if previous_last_run:
            try:
                previous_last_run_date = datetime.fromisoformat(previous_last_run)
            except ValueError:
                previous_last_run_date = None

        if previous_last_run_date and previous_last_run_date < current_month_start:
            auto_task['last_month_count'] = auto_task.get('monthly_new_count', 0)
            auto_task['monthly_new_count'] = downloaded_count
        else:
            auto_task['monthly_new_count'] = auto_task.get('monthly_new_count', 0) + downloaded_count

        if downloaded_count > 0:
            auto_task['downloaded_count'] = auto_task.get('downloaded_count', 0) + downloaded_count

        auto_task['last_run'] = now.isoformat()
        return deepcopy(auto_task)


def _complete_execution_with_no_albums(execution: Dict[str, Any]) -> None:
    execution_id = execution['id']
    add_log(execution_id, 'success', '[自动化] 收藏夹为空或解析失败，未发现可下载本子')
    execution['status'] = 'completed'
    execution['end_time'] = datetime.now().isoformat()
    with auto_execution_lock:
        auto_executions[execution_id] = deepcopy(execution)
    save_auto_execution(execution)


def _handle_execution_error(execution: Dict[str, Any], error: Exception, execution_id: int) -> None:
    add_log(execution_id, 'error', f'[自动化] 执行失败: {str(error)}')
    execution['status'] = 'failed'
    execution['error'] = str(error)
    execution['end_time'] = datetime.now().isoformat()
    with auto_execution_lock:
        auto_executions[execution_id] = deepcopy(execution)
    save_auto_execution(execution)


def _save_task_config(auto_task_id: int, execution_id: int) -> None:
    from server.utils.storage import save_auto_tasks

    try:
        with auto_task_lock:
            if auto_task_id not in auto_tasks:
                return
            snapshot = {k: deepcopy(v) for k, v in auto_tasks.items()}
        save_auto_tasks(snapshot)
    except Exception as e:
        add_log(execution_id, 'error', f'[自动化] 保存任务配置失败: {str(e)}')


def _process_batch_downloads(
    albums_to_download: List[str],
    auto_task: Dict[str, Any],
    execution: Dict[str, Any],
    execution_id: int,
) -> int:
    batch_albums_count = auto_task.get('batch_albums_count', 50)
    batch_interval_minutes = auto_task.get('batch_interval_minutes', 30)
    download_dir = auto_task['download_dir']

    total_albums = len(albums_to_download)
    total_batches = (total_albums + batch_albums_count - 1) // batch_albums_count
    all_task_ids = []

    add_log(
        execution_id,
        'info',
        f'[自动化] 共 {total_albums} 个本子，将分为 {total_batches} 批次下载（每批 {batch_albums_count} 个，批次间隔 {batch_interval_minutes} 分钟）',
    )

    local_albums_before = scan_local_albums(download_dir)

    for batch_num in range(total_batches):
        if is_auto_task_stopped(auto_task['id']):
            add_log(execution_id, 'info', f'[自动化] 收到停止指令，取消剩余 {total_batches - batch_num} 个批次')
            break

        start_idx = batch_num * batch_albums_count
        end_idx = min(start_idx + batch_albums_count, total_albums)
        batch_albums = albums_to_download[start_idx:end_idx]

        add_log(
            execution_id,
            'info',
            f'[自动化] 开始下载第 {batch_num + 1}/{total_batches} 批（本批 {len(batch_albums)} 个本子）',
        )

        task_ids = create_batch_download_tasks(batch_albums, auto_task, execution_id)
        all_task_ids.extend(task_ids)

        add_log(execution_id, 'info', f'[自动化] 第 {batch_num + 1} 批已创建下载任务，等待完成...')

        _wait_for_tasks_completion(task_ids, execution_id, timeout=3600)

        add_log(execution_id, 'success', f'[自动化] 第 {batch_num + 1} 批下载任务已完成')

        failed_albums = _verify_batch_downloads(batch_albums, download_dir, execution_id)

        if failed_albums:
            add_log(execution_id, 'info', f'[自动化] 发现 {len(failed_albums)} 个下载失败的本子，开始重试...')
            retry_task_ids = _retry_failed_albums(failed_albums, auto_task, execution_id)
            all_task_ids.extend(retry_task_ids)
            _wait_for_tasks_completion(retry_task_ids, execution_id, timeout=1800)
            add_log(execution_id, 'success', f'[自动化] 第 {batch_num + 1} 批重试完成')

        if batch_num + 1 < total_batches:
            remaining_batches = total_batches - batch_num - 1
            add_log(
                execution_id,
                'info',
                f'[自动化] 第 {batch_num + 1} 批处理完成，等待 {batch_interval_minutes} 分钟后继续下载（剩余 {remaining_batches} 批）',
            )
            _wait_with_stop_check(auto_task['id'], batch_interval_minutes * 60, execution_id)

    execution['downloaded_task_ids'] = all_task_ids
    with auto_execution_lock:
        auto_executions[execution['id']] = deepcopy(execution)
    save_auto_execution(execution)

    local_albums_after = scan_local_albums(download_dir)
    actual_downloaded = len(local_albums_after - local_albums_before)

    add_log(execution_id, 'success', f'[自动化] 批量下载完成，实际新增 {actual_downloaded} 个本子')
    return actual_downloaded


def _wait_for_tasks_completion(task_ids: List[int], execution_id: int, timeout: int = 3600) -> None:
    if not task_ids:
        return

    running_statuses = {'pending', 'running', 'downloading'}
    start_time = time.time()
    check_interval = 5

    while time.time() - start_time < timeout:
        with task_lock:
            all_finished = True
            for task_id in task_ids:
                task = tasks.get(task_id)
                if task is None:
                    continue
                if task.get('status') in running_statuses:
                    all_finished = False
                    break

        if all_finished:
            return

        time.sleep(check_interval)

    add_log(execution_id, 'error', f'[自动化] 等待任务完成超时（{timeout}秒）')


def _verify_batch_downloads(album_ids: List[str], download_dir: str, execution_id: int) -> List[str]:
    try:
        local_albums = scan_local_albums(download_dir)
        failed_albums = [aid for aid in album_ids if aid not in local_albums]

        if failed_albums:
            add_log(
                execution_id,
                'info',
                f'[自动化] 验证结果：{len(album_ids) - len(failed_albums)}/{len(album_ids)} 个成功，{len(failed_albums)} 个失败（ID: {", ".join(failed_albums[:5])}{"..." if len(failed_albums) > 5 else ""}）',
            )
        else:
            add_log(execution_id, 'success', f'[自动化] 验证结果：本批 {len(album_ids)} 个本子全部下载成功')

        return failed_albums

    except Exception as e:
        add_log(execution_id, 'error', f'[自动化] 验证下载结果失败: {str(e)}')
        return []


def _retry_failed_albums(failed_album_ids: List[str], auto_task: Dict[str, Any], execution_id: int) -> List[int]:
    if not failed_album_ids:
        return []

    try:
        task_ids = create_batch_download_tasks(failed_album_ids, auto_task, execution_id)
        add_log(execution_id, 'info', f'[自动化] 已创建 {len(task_ids)} 个重试任务，共 {len(failed_album_ids)} 个本子')
        return task_ids
    except Exception as e:
        add_log(execution_id, 'error', f'[自动化] 创建重试任务失败: {str(e)}')
        return []


def _wait_with_stop_check(auto_task_id: int, wait_seconds: int, execution_id: int) -> bool:
    check_interval = 10
    elapsed = 0

    while elapsed < wait_seconds:
        if is_auto_task_stopped(auto_task_id):
            add_log(execution_id, 'info', '[自动化] 等待期间收到停止指令')
            return False

        sleep_time = min(check_interval, wait_seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time

        if elapsed % 60 == 0 and elapsed < wait_seconds:
            remaining_minutes = (wait_seconds - elapsed) // 60
            add_log(execution_id, 'info', f'[自动化] 等待中，还需 {remaining_minutes} 分钟...')

    return True


__all__ = ['execute_auto_sync']
