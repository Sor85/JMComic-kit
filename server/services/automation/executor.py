#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化任务执行器

协调各个模块完成自动同步任务：
1. 获取收藏夹相册列表
2. 扫描本地已下载相册
3. 对比差异，创建批量下载任务
4. 分批下载，等待并验证每批结果
5. 自动重试失败的相册
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Set
from server.state import auto_executions, get_next_auto_execution_id, tasks, is_auto_task_stopped, clear_auto_task_stop_flag
from server.utils import add_log
from server.utils.storage import save_auto_execution
from .favorites_fetcher import fetch_favorites
from .local_scanner import scan_local_albums
from .task_creator import create_batch_download_tasks


def execute_auto_sync(
    auto_task: Dict[str, Any],
    scheduler=None
) -> None:
    """执行自动同步任务
    
    完整流程：
    1. 创建执行记录
    2. 获取收藏夹相册ID列表
    3. 扫描本地已下载相册ID
    4. 计算差异（需要下载的相册）
    5. 批量创建下载任务
    6. 更新统计数据
    7. 处理异常和清理
    
    Args:
        auto_task: 自动化任务配置
        scheduler: APScheduler 调度器（用于更新下次执行时间）
    """
    # 创建执行记录
    execution = _create_execution_record(auto_task)
    execution_id = execution['id']
    
    try:
        add_log(execution_id, "info", f"[自动化] 开始执行自动同步任务: {auto_task['name']}")
        
        # 步骤1：获取收藏夹相册ID
        favorite_albums = _fetch_favorite_albums(auto_task, execution_id)
        execution['scanned_count'] = len(favorite_albums)
        
        if not favorite_albums:
            _complete_execution_with_no_albums(execution)
            return
        
        # 步骤2：扫描本地已有相册
        local_albums = _scan_local_albums(auto_task['download_dir'], execution_id)
        execution['local_count'] = len(local_albums)
        
        # 步骤3：计算需要下载的相册
        albums_to_download = [aid for aid in favorite_albums if aid not in local_albums]
        skipped_count = len(favorite_albums) - len(albums_to_download)
        
        execution['to_download_count'] = len(albums_to_download)
        execution['skipped_count'] = skipped_count
        
        _log_download_summary(execution_id, favorite_albums, albums_to_download, skipped_count)
        
        # 步骤4：分批下载
        if albums_to_download:
            downloaded_count = _process_batch_downloads(
                albums_to_download, 
                auto_task, 
                execution, 
                execution_id
            )
            add_log(execution_id, "success", f"[自动化] 所有批次处理完成，共尝试下载 {len(albums_to_download)} 个本子")
        else:
            add_log(execution_id, "success", "[自动化] 没有新本子需要下载")
            downloaded_count = 0
        
        # 步骤5：更新任务统计
        _update_task_statistics(auto_task, downloaded_count, skipped_count)
        
        # 步骤6：更新下次执行时间
        if scheduler:
            from .scheduler import update_next_run_time
            update_next_run_time(scheduler, auto_task)
        
        # 完成执行
        execution['status'] = 'completed'
        execution['end_time'] = datetime.now().isoformat()
        save_auto_execution(execution)
        add_log(execution_id, "success", "[自动化] 任务执行完成")
        
        # 清除停止标志
        clear_auto_task_stop_flag(auto_task['id'])
        
    except Exception as e:
        _handle_execution_error(execution, e, execution_id)
        clear_auto_task_stop_flag(auto_task['id'])
    
    finally:
        # 执行结束后将状态恢复为 stopped
        auto_task["status"] = "stopped"
        _save_task_config(auto_task, execution_id)
        # 确保清除停止标志
        clear_auto_task_stop_flag(auto_task['id'])


def _create_execution_record(auto_task: Dict[str, Any]) -> Dict[str, Any]:
    """创建执行记录"""
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
    auto_executions[execution_id] = execution
    save_auto_execution(execution)
    return execution


def _fetch_favorite_albums(auto_task: Dict[str, Any], execution_id: int) -> List[str]:
    """获取收藏夹相册ID列表"""
    favorite_albums = fetch_favorites(
        username=auto_task['username'],
        password=auto_task['password'],
        client_impl=auto_task.get('client_impl', 'api'),
        execution_id=execution_id
    )
    
    # 去重并验证
    unique_albums = [aid for aid in favorite_albums if str(aid).isdigit()]
    add_log(execution_id, "info", f"[自动化] 总共找到 {len(unique_albums)} 个唯一本子")
    
    return unique_albums


def _scan_local_albums(download_dir: str, execution_id: int) -> set:
    """扫描本地已有相册"""
    try:
        local_albums = scan_local_albums(download_dir)
        add_log(execution_id, "info", f"[自动化] 本地已有 {len(local_albums)} 个本子")
        return local_albums
    except OSError as e:
        add_log(execution_id, 'error', f'[自动化] 读取本地目录失败: {str(e)}')
        return set()


def _log_download_summary(
    execution_id: int,
    favorite_albums: List[str],
    albums_to_download: List[str],
    skipped_count: int
) -> None:
    """记录下载摘要日志"""
    add_log(
        execution_id, 
        "info", 
        f"[自动化] 需要下载: {len(albums_to_download)} 个，跳过: {skipped_count} 个"
    )
    
    if albums_to_download:
        sample = ','.join(list(albums_to_download)[:5])
        suffix = ' ...' if len(albums_to_download) > 5 else ''
        add_log(execution_id, "info", f"[自动化] 待下载ID样本: {sample}{suffix}")


def _update_task_statistics(
    auto_task: Dict[str, Any],
    downloaded_count: int,
    skipped_count: int
) -> None:
    """更新任务统计数据"""
    auto_task["run_count"] = auto_task.get("run_count", 0) + 1
    auto_task["skipped_count"] = auto_task.get("skipped_count", 0) + skipped_count
    auto_task["last_run"] = datetime.now().isoformat()
    
    # 更新月度统计
    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_run_date = (
        datetime.fromisoformat(auto_task["last_run"]) 
        if auto_task.get("last_run") else None
    )
    
    if last_run_date and last_run_date < current_month:
        # 跨月，重置月度统计
        auto_task["last_month_count"] = auto_task.get("downloaded_count", 0)
        auto_task["monthly_new_count"] = downloaded_count
    else:
        # 同月，累加
        auto_task["monthly_new_count"] = auto_task.get("monthly_new_count", 0) + downloaded_count
    
    if downloaded_count > 0:
        auto_task["downloaded_count"] = auto_task.get("downloaded_count", 0) + downloaded_count


def _complete_execution_with_no_albums(execution: Dict[str, Any]) -> None:
    """处理收藏夹为空的情况"""
    execution_id = execution['id']
    add_log(execution_id, "success", "[自动化] 收藏夹为空或解析失败，未发现可下载本子")
    execution['status'] = 'completed'
    execution['end_time'] = datetime.now().isoformat()
    save_auto_execution(execution)


def _handle_execution_error(
    execution: Dict[str, Any],
    error: Exception,
    execution_id: int
) -> None:
    """处理执行错误"""
    add_log(execution_id, "error", f"[自动化] 执行失败: {str(error)}")
    execution['status'] = 'failed'
    execution['error'] = str(error)
    execution['end_time'] = datetime.now().isoformat()
    save_auto_execution(execution)


def _save_task_config(auto_task: Dict[str, Any], execution_id: int) -> None:
    """保存任务配置到磁盘"""
    from server.state import auto_tasks
    from server.utils.storage import save_auto_tasks
    
    try:
        save_auto_tasks(auto_tasks)
    except Exception as e:
        add_log(execution_id, 'error', f'[自动化] 保存任务配置失败: {str(e)}')


def _process_batch_downloads(
    albums_to_download: List[str],
    auto_task: Dict[str, Any],
    execution: Dict[str, Any],
    execution_id: int
) -> int:
    """分批处理下载任务
    
    Args:
        albums_to_download: 待下载的相册ID列表
        auto_task: 自动化任务配置
        execution: 执行记录
        execution_id: 执行记录ID
        
    Returns:
        实际成功下载的相册数量
    """
    batch_albums_count = auto_task.get('batch_albums_count', 50)
    batch_interval_minutes = auto_task.get('batch_interval_minutes', 30)
    download_dir = auto_task['download_dir']
    
    total_albums = len(albums_to_download)
    total_batches = (total_albums + batch_albums_count - 1) // batch_albums_count
    all_task_ids = []
    
    add_log(
        execution_id, 
        'info', 
        f'[自动化] 共 {total_albums} 个本子，将分为 {total_batches} 批次下载'
        f'（每批 {batch_albums_count} 个，批次间隔 {batch_interval_minutes} 分钟）'
    )
    
    # 记录下载前的本地相册数量
    local_albums_before = scan_local_albums(download_dir)
    
    for batch_num in range(total_batches):
        # 检查是否被停止
        if is_auto_task_stopped(auto_task['id']):
            add_log(execution_id, 'info', f'[自动化] 收到停止指令，取消剩余 {total_batches - batch_num} 个批次')
            break
        
        # 计算当前批次的相册列表
        start_idx = batch_num * batch_albums_count
        end_idx = min(start_idx + batch_albums_count, total_albums)
        batch_albums = albums_to_download[start_idx:end_idx]
        
        add_log(
            execution_id,
            'info',
            f'[自动化] 开始下载第 {batch_num + 1}/{total_batches} 批（本批 {len(batch_albums)} 个本子）'
        )
        
        # 创建并启动下载任务
        task_ids = create_batch_download_tasks(batch_albums, auto_task, execution_id)
        all_task_ids.extend(task_ids)
        
        add_log(execution_id, 'info', f'[自动化] 第 {batch_num + 1} 批已创建下载任务，等待完成...')
        
        # 等待当前批次完成
        _wait_for_tasks_completion(task_ids, execution_id, timeout=3600)
        
        add_log(execution_id, 'success', f'[自动化] 第 {batch_num + 1} 批下载任务已完成')
        
        # 验证下载结果
        failed_albums = _verify_batch_downloads(batch_albums, download_dir, execution_id)
        
        # 重试失败的相册
        if failed_albums:
            add_log(
                execution_id, 
                'info', 
                f'[自动化] 发现 {len(failed_albums)} 个下载失败的本子，开始重试...'
            )
            retry_task_ids = _retry_failed_albums(failed_albums, auto_task, execution_id)
            all_task_ids.extend(retry_task_ids)
            
            # 等待重试完成
            _wait_for_tasks_completion(retry_task_ids, execution_id, timeout=1800)
            add_log(execution_id, 'success', f'[自动化] 第 {batch_num + 1} 批重试完成')
        
        # 如果还有下一批，等待指定时间
        if batch_num + 1 < total_batches:
            remaining_batches = total_batches - batch_num - 1
            add_log(
                execution_id, 
                'info', 
                f'[自动化] 第 {batch_num + 1} 批处理完成，等待 {batch_interval_minutes} 分钟后继续下载（剩余 {remaining_batches} 批）'
            )
            
            # 分段等待，每10秒检查一次是否被停止
            _wait_with_stop_check(auto_task['id'], batch_interval_minutes * 60, execution_id)
    
    # 更新执行记录
    execution['downloaded_task_ids'] = all_task_ids
    save_auto_execution(execution)
    
    # 计算实际下载成功的数量
    local_albums_after = scan_local_albums(download_dir)
    actual_downloaded = len(local_albums_after - local_albums_before)
    
    add_log(
        execution_id, 
        'success', 
        f'[自动化] 批量下载完成，实际新增 {actual_downloaded} 个本子'
    )
    
    return actual_downloaded


def _wait_for_tasks_completion(task_ids: List[int], execution_id: int, timeout: int = 3600) -> None:
    """等待指定的下载任务完成
    
    Args:
        task_ids: 任务ID列表
        execution_id: 执行记录ID
        timeout: 超时时间（秒）
    """
    if not task_ids:
        return
    
    start_time = time.time()
    check_interval = 5  # 每5秒检查一次
    
    while time.time() - start_time < timeout:
        # 检查所有任务状态
        all_finished = True
        for task_id in task_ids:
            task = tasks.get(task_id)
            if task and task.get('status') in ['pending', 'downloading']:
                all_finished = False
                break
        
        if all_finished:
            return
        
        time.sleep(check_interval)
    
    # 超时
    add_log(execution_id, 'error', f'[自动化] 等待任务完成超时（{timeout}秒）')


def _verify_batch_downloads(
    album_ids: List[str], 
    download_dir: str, 
    execution_id: int
) -> List[str]:
    """验证批次下载结果，返回失败的相册ID列表
    
    通过扫描本地目录，检查哪些相册ID没有成功下载
    
    Args:
        album_ids: 本批次尝试下载的相册ID列表
        download_dir: 下载目录
        execution_id: 执行记录ID
        
    Returns:
        下载失败的相册ID列表
    """
    try:
        # 扫描本地已有相册
        local_albums = scan_local_albums(download_dir)
        
        # 找出没有成功下载的相册
        failed_albums = [aid for aid in album_ids if aid not in local_albums]
        
        if failed_albums:
            add_log(
                execution_id,
                'info',
                f'[自动化] 验证结果：{len(album_ids) - len(failed_albums)}/{len(album_ids)} 个成功，'
                f'{len(failed_albums)} 个失败（ID: {", ".join(failed_albums[:5])}{"..." if len(failed_albums) > 5 else ""}）'
            )
        else:
            add_log(execution_id, 'success', f'[自动化] 验证结果：本批 {len(album_ids)} 个本子全部下载成功')
        
        return failed_albums
        
    except Exception as e:
        add_log(execution_id, 'error', f'[自动化] 验证下载结果失败: {str(e)}')
        return []


def _retry_failed_albums(
    failed_album_ids: List[str],
    auto_task: Dict[str, Any],
    execution_id: int
) -> List[int]:
    """重新下载失败的相册
    
    Args:
        failed_album_ids: 失败的相册ID列表
        auto_task: 自动化任务配置
        execution_id: 执行记录ID
        
    Returns:
        创建的重试任务ID列表
    """
    if not failed_album_ids:
        return []
    
    try:
        task_ids = create_batch_download_tasks(failed_album_ids, auto_task, execution_id)
        add_log(
            execution_id,
            'info',
            f'[自动化] 已创建 {len(task_ids)} 个重试任务，共 {len(failed_album_ids)} 个本子'
        )
        return task_ids
    except Exception as e:
        add_log(execution_id, 'error', f'[自动化] 创建重试任务失败: {str(e)}')
        return []


def _wait_with_stop_check(auto_task_id: int, wait_seconds: int, execution_id: int) -> bool:
    """等待指定时间，期间定期检查停止标志
    
    Args:
        auto_task_id: 自动化任务ID
        wait_seconds: 等待秒数
        execution_id: 执行记录ID
        
    Returns:
        True: 正常等待完成，False: 被停止
    """
    check_interval = 10  # 每10秒检查一次
    elapsed = 0
    
    while elapsed < wait_seconds:
        # 检查是否被停止
        if is_auto_task_stopped(auto_task_id):
            add_log(execution_id, 'info', '[自动化] 等待期间收到停止指令')
            return False
        
        # 等待一小段时间
        sleep_time = min(check_interval, wait_seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time
        
        # 每分钟输出一次剩余等待时间
        if elapsed % 60 == 0 and elapsed < wait_seconds:
            remaining_minutes = (wait_seconds - elapsed) // 60
            add_log(execution_id, 'info', f'[自动化] 等待中，还需 {remaining_minutes} 分钟...')
    
    return True


__all__ = ["execute_auto_sync"]

