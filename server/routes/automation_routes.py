#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化任务路由。
负责自动化任务 CRUD、执行触发、调度恢复与执行记录查询。
"""

import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from server.services.automation import execute_auto_sync, schedule_task, unschedule_task
from server.state import (
    AUTO_TASK_DESIRED_DISABLED,
    AUTO_TASK_DESIRED_ENABLED,
    AUTO_TASK_RUNTIME_ERROR,
    AUTO_TASK_RUNTIME_IDLE,
    AUTO_TASK_RUNTIME_RUNNING,
    AUTO_TASK_RUNTIME_SCHEDULED,
    AUTO_TASK_RUNTIME_STOPPING,
    auto_execution_lock,
    auto_executions,
    auto_task_lock,
    auto_tasks,
    clear_auto_task_running,
    clear_auto_task_stop_flag,
    get_next_auto_task_id,
    normalize_auto_task_state,
    set_auto_task_stop_flag,
    task_lock,
    tasks,
    try_mark_auto_task_running,
    update_auto_task_status,
)
from server.utils.logs import add_log, get_logs
from server.utils.sanitize import deep_strip_sensitive
from server.utils.storage import (
    save_all_auto_executions,
    save_auto_tasks as storage_save_auto_tasks,
)
from server.utils.validators import validate_cron_expression, validate_path_safety, validate_speed_limit

automation_bp = Blueprint('automation', __name__)

_scheduler = None


def init_scheduler(scheduler) -> None:
    """初始化调度器引用。"""
    global _scheduler
    _scheduler = scheduler


def _persist_auto_tasks() -> None:
    try:
        with auto_task_lock:
            snapshot = {task_id: deepcopy(task) for task_id, task in auto_tasks.items()}
        storage_save_auto_tasks(snapshot)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')


def _get_auto_task_locked(auto_task_id: int) -> Optional[Dict[str, Any]]:
    task = auto_tasks.get(auto_task_id)
    if not task:
        return None
    normalized = normalize_auto_task_state(task)
    auto_tasks[auto_task_id] = normalized
    return normalized


def _sanitize_task_payload(task: Dict[str, Any]) -> Dict[str, Any]:
    return deep_strip_sensitive(deepcopy(task))


_AUTO_TASK_ROLLBACK_FIELDS = (
    'name',
    'username',
    'password',
    'cron',
    'download_dir',
    'speed_limit',
    'client_impl',
    'image_suffix',
    'dir_rule',
    'batch_albums_count',
    'batch_interval_minutes',
    'compression',
    'desired_status',
    'runtime_status',
    'current_execution_id',
    'next_run',
    'status',
)

_AUTO_TASK_UPDATE_CONFLICT_FIELDS = (
    'name',
    'username',
    'password',
    'cron',
    'download_dir',
    'speed_limit',
    'client_impl',
    'image_suffix',
    'dir_rule',
    'batch_albums_count',
    'batch_interval_minutes',
    'compression',
    'desired_status',
)


def _build_auto_task_rollback_snapshot(auto_task: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = {field: deepcopy(auto_task.get(field)) for field in _AUTO_TASK_ROLLBACK_FIELDS}
    snapshot['has_batch_size'] = 'batch_size' in auto_task
    if snapshot['has_batch_size']:
        snapshot['batch_size'] = deepcopy(auto_task.get('batch_size'))
    return snapshot


def _restore_auto_task_from_snapshot(auto_task: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
    for field in _AUTO_TASK_ROLLBACK_FIELDS:
        auto_task[field] = deepcopy(snapshot.get(field))

    if snapshot.get('has_batch_size'):
        auto_task['batch_size'] = deepcopy(snapshot.get('batch_size'))
    else:
        auto_task.pop('batch_size', None)


def _restore_auto_task_update_fields(auto_task: Dict[str, Any], snapshot: Dict[str, Any]) -> None:
    for field in _AUTO_TASK_UPDATE_CONFLICT_FIELDS:
        auto_task[field] = deepcopy(snapshot.get(field))

    if snapshot.get('has_batch_size'):
        auto_task['batch_size'] = deepcopy(snapshot.get('batch_size'))
    else:
        auto_task.pop('batch_size', None)

    desired_status = auto_task.get('desired_status', AUTO_TASK_DESIRED_DISABLED)
    runtime_status = auto_task.get('runtime_status', AUTO_TASK_RUNTIME_IDLE)
    current_execution_id = auto_task.get('current_execution_id')
    update_auto_task_status(
        auto_task,
        desired_status=desired_status,
        runtime_status=runtime_status,
        current_execution_id=current_execution_id,
    )

    if desired_status != AUTO_TASK_DESIRED_ENABLED:
        auto_task['next_run'] = None


def _is_auto_task_snapshot_match(auto_task: Dict[str, Any], snapshot: Dict[str, Any], fields) -> bool:
    for field in fields:
        if auto_task.get(field) != snapshot.get(field):
            return False

    if snapshot.get('has_batch_size'):
        return auto_task.get('batch_size') == snapshot.get('batch_size')

    return 'batch_size' not in auto_task


def run_auto_sync_task(auto_task_id: int, force_run: bool = False, already_marked: bool = False):
    """运行自动同步任务（线程入口函数）。"""
    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            if already_marked:
                clear_auto_task_running(auto_task_id)
            return

        if not force_run and auto_task.get('desired_status') != AUTO_TASK_DESIRED_ENABLED:
            update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_IDLE, current_execution_id=None)
            if already_marked:
                clear_auto_task_running(auto_task_id)
            return

        if not already_marked and not try_mark_auto_task_running(auto_task_id):
            add_log(0, 'info', f'[自动化] 任务 {auto_task["name"]} 已在执行中，忽略重复触发')
            return

        update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_RUNNING)

    try:
        execute_auto_sync(auto_task_id, _scheduler)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 任务 {auto_task_id} 执行异常退出: {str(e)}')
        with auto_task_lock:
            task = _get_auto_task_locked(auto_task_id)
            if task:
                update_auto_task_status(task, runtime_status=AUTO_TASK_RUNTIME_ERROR, current_execution_id=None)
                task['next_run'] = None
        _persist_auto_tasks()
    finally:
        clear_auto_task_running(auto_task_id)


def schedule_auto_task(auto_task_id: int) -> bool:
    """调度自动任务。"""
    if _scheduler is None:
        add_log(0, 'error', '[自动化] 调度器未初始化，无法调度任务')
        return False

    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            return False
        task_snapshot = deepcopy(auto_task)
        before_runtime_status = auto_task.get('runtime_status')
        before_status = auto_task.get('status')

    scheduled = schedule_task(_scheduler, task_snapshot, run_auto_sync_task)
    should_unschedule = False

    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            should_unschedule = scheduled
            scheduled = False
        else:
            current_runtime_status = auto_task.get('runtime_status')
            current_status = auto_task.get('status')

            if current_runtime_status == before_runtime_status and current_status == before_status:
                auto_task['runtime_status'] = task_snapshot.get('runtime_status', auto_task.get('runtime_status'))
                auto_task['status'] = task_snapshot.get('status', auto_task.get('status'))

            auto_task['next_run'] = task_snapshot.get('next_run')

            if auto_task.get('desired_status') != AUTO_TASK_DESIRED_ENABLED:
                update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_IDLE, current_execution_id=None)
                auto_task['next_run'] = None
                should_unschedule = should_unschedule or scheduled
                scheduled = False

    if should_unschedule and _scheduler is not None:
        unschedule_task(_scheduler, auto_task_id)

    _persist_auto_tasks()
    return scheduled


def recover_scheduled_auto_tasks() -> int:
    """恢复所有已启用自动化任务的调度。"""
    recovered = 0
    with auto_task_lock:
        task_ids = list(auto_tasks.keys())

    for task_id in task_ids:
        try:
            with auto_task_lock:
                auto_task = _get_auto_task_locked(task_id)
                if not auto_task:
                    continue
                if auto_task.get('desired_status') != AUTO_TASK_DESIRED_ENABLED:
                    continue

            if schedule_auto_task(task_id):
                recovered += 1
            else:
                with auto_task_lock:
                    auto_task = _get_auto_task_locked(task_id)
                    if auto_task:
                        update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_IDLE, current_execution_id=None)
                        auto_task['next_run'] = None
                _persist_auto_tasks()
        except Exception as e:
            add_log(0, 'error', f'[自动化] 恢复任务 #{task_id} 调度失败: {str(e)}')

    return recovered


@automation_bp.route('/automation', methods=['GET'])
def get_auto_tasks():
    """获取所有自动化任务。"""
    with auto_task_lock:
        normalized_tasks = [_get_auto_task_locked(task_id) for task_id in list(auto_tasks.keys())]
        payload = [deepcopy(task) for task in normalized_tasks if task]

    return jsonify(deep_strip_sensitive(payload))


@automation_bp.route('/automation/<int:auto_task_id>', methods=['GET'])
def get_auto_task_detail(auto_task_id: int):
    """获取单个自动化任务。"""
    with auto_task_lock:
        task = _get_auto_task_locked(auto_task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        payload = deepcopy(task)

    return jsonify(deep_strip_sensitive(payload))


@automation_bp.route('/automation', methods=['POST'])
def create_auto_task():
    """创建自动化任务。"""
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    elif not isinstance(data, dict):
        return jsonify({'error': '请求体必须是 JSON 对象'}), 400

    name = data.get('name', '')
    username = data.get('username', '')
    password = data.get('password', '')
    cron = data.get('cron', '0 */6 * * *')
    download_dir = data.get('download_dir', './download/')
    speed_limit = data.get('speed_limit', 0)
    client_impl = data.get('client_impl', 'api')
    image_suffix = data.get('image_suffix', '')
    dir_rule = data.get('dir_rule', 'Aauthoroname/Pindextitle')
    batch_albums_count = data.get('batch_albums_count', 50)
    batch_interval_minutes = data.get('batch_interval_minutes', 30)
    compression = data.get('compression', {})
    run_now = data.get('run_now', False)

    if not name or not username or not password:
        return jsonify({'error': '任务名称、账号和密码不能为空'}), 400

    if 'run_now' in data and not isinstance(run_now, bool):
        return jsonify({'error': 'run_now 必须是布尔值'}), 400

    if not validate_path_safety(download_dir):
        return jsonify({'error': '下载目录路径不安全'}), 400

    valid, error_msg = validate_cron_expression(cron)
    if not valid:
        return jsonify({'error': error_msg}), 400

    if 'speed_limit' in data:
        if isinstance(speed_limit, bool):
            return jsonify({'error': '速度限制参数错误: 速度值必须为数字'}), 400
        valid, kb_value, error_msg = validate_speed_limit(str(speed_limit))
        if not valid:
            return jsonify({'error': f'速度限制参数错误: {error_msg}'}), 400
        speed_limit = kb_value
    else:
        speed_limit = 0

    try:
        batch_albums_count = int(batch_albums_count)
    except (TypeError, ValueError):
        return jsonify({'error': '每批下载数量必须是整数'}), 400

    try:
        batch_interval_minutes = int(batch_interval_minutes)
    except (TypeError, ValueError):
        return jsonify({'error': '批次间隔必须是整数'}), 400

    if batch_albums_count < 1 or batch_albums_count > 500:
        return jsonify({'error': '每批下载数量必须在 1-500 之间'}), 400

    if batch_interval_minutes < 1 or batch_interval_minutes > 1440:
        return jsonify({'error': '批次间隔必须在 1-1440 分钟之间'}), 400

    auto_task_id = get_next_auto_task_id()
    auto_task = {
        'id': auto_task_id,
        'name': name,
        'username': username,
        'password': password,
        'cron': cron,
        'download_dir': download_dir,
        'speed_limit': speed_limit,
        'client_impl': client_impl,
        'image_suffix': image_suffix,
        'dir_rule': dir_rule,
        'batch_albums_count': batch_albums_count,
        'batch_interval_minutes': batch_interval_minutes,
        'compression': compression,
        'status': 'stopped',
        'desired_status': AUTO_TASK_DESIRED_DISABLED,
        'runtime_status': AUTO_TASK_RUNTIME_IDLE,
        'current_execution_id': None,
        'run_count': 0,
        'downloaded_count': 0,
        'skipped_count': 0,
        'monthly_new_count': 0,
        'last_month_count': 0,
        'created_time': datetime.now().isoformat(),
        'last_run': None,
        'next_run': None,
    }

    if run_now:
        update_auto_task_status(auto_task, desired_status=AUTO_TASK_DESIRED_ENABLED, runtime_status=AUTO_TASK_RUNTIME_SCHEDULED)

    with auto_task_lock:
        auto_tasks[auto_task_id] = normalize_auto_task_state(auto_task)

    if run_now:
        if not schedule_auto_task(auto_task_id):
            with auto_task_lock:
                task = _get_auto_task_locked(auto_task_id)
                if task:
                    update_auto_task_status(task, desired_status=AUTO_TASK_DESIRED_DISABLED, runtime_status=AUTO_TASK_RUNTIME_IDLE, current_execution_id=None)
                    task['next_run'] = None
            _persist_auto_tasks()
            return jsonify({'error': '任务创建成功，但调度失败'}), 500
    else:
        _persist_auto_tasks()

    with auto_task_lock:
        task = _get_auto_task_locked(auto_task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        payload = _sanitize_task_payload(task)
    return jsonify(payload)


@automation_bp.route('/automation/<int:auto_task_id>/start', methods=['POST'])
def start_auto_task(auto_task_id: int):
    """启动自动化任务。"""
    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            return jsonify({'error': '任务不存在'}), 404

        if auto_task.get('desired_status') == AUTO_TASK_DESIRED_ENABLED:
            return jsonify({'error': '任务已在运行中'}), 400

        clear_auto_task_stop_flag(auto_task_id)
        update_auto_task_status(auto_task, desired_status=AUTO_TASK_DESIRED_ENABLED, runtime_status=AUTO_TASK_RUNTIME_SCHEDULED)

    if not schedule_auto_task(auto_task_id):
        with auto_task_lock:
            task = _get_auto_task_locked(auto_task_id)
            if task:
                update_auto_task_status(task, desired_status=AUTO_TASK_DESIRED_DISABLED, runtime_status=AUTO_TASK_RUNTIME_IDLE, current_execution_id=None)
                task['next_run'] = None
        _persist_auto_tasks()
        return jsonify({'error': '任务启动失败，调度未生效'}), 500

    with auto_task_lock:
        task = _get_auto_task_locked(auto_task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        payload = _sanitize_task_payload(task)
    return jsonify({'message': '任务已启动', 'task': payload})


@automation_bp.route('/automation/<int:auto_task_id>/stop', methods=['POST'])
def stop_auto_task(auto_task_id: int):
    """停止自动化任务。"""
    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            return jsonify({'error': '任务不存在'}), 404
        rollback_snapshot = _build_auto_task_rollback_snapshot(auto_task)

        runtime_status = AUTO_TASK_RUNTIME_STOPPING if auto_task.get('runtime_status') == AUTO_TASK_RUNTIME_RUNNING else AUTO_TASK_RUNTIME_IDLE
        update_auto_task_status(auto_task, desired_status=AUTO_TASK_DESIRED_DISABLED, runtime_status=runtime_status, current_execution_id=None)
        auto_task['next_run'] = None

    set_auto_task_stop_flag(auto_task_id)
    try:
        if _scheduler is not None:
            unschedule_task(_scheduler, auto_task_id)
    except Exception as e:
        with auto_task_lock:
            task = _get_auto_task_locked(auto_task_id)
            if task:
                _restore_auto_task_from_snapshot(task, rollback_snapshot)
        clear_auto_task_stop_flag(auto_task_id)
        _persist_auto_tasks()
        add_log(0, 'error', f'[自动化] 停止任务 {auto_task_id} 失败: {str(e)}')
        return jsonify({'error': '任务停止失败，调度取消异常'}), 500

    _persist_auto_tasks()

    with auto_task_lock:
        task = _get_auto_task_locked(auto_task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        payload = _sanitize_task_payload(task)
    return jsonify({'message': '任务已停止', 'task': payload})


@automation_bp.route('/automation/<int:auto_task_id>/run', methods=['POST'])
def run_auto_task_now(auto_task_id: int):
    """立即执行自动化任务。"""
    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            return jsonify({'error': '任务不存在'}), 404

        clear_auto_task_stop_flag(auto_task_id)

        if not try_mark_auto_task_running(auto_task_id):
            payload = _sanitize_task_payload(auto_task)
            return jsonify({'message': '任务已在执行中', 'already_running': True, 'task': payload})

        update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_RUNNING)

    try:
        thread = threading.Thread(target=run_auto_sync_task, args=(auto_task_id, True, True))
        thread.daemon = True
        thread.start()
    except Exception as e:
        with auto_task_lock:
            task = _get_auto_task_locked(auto_task_id)
            if task:
                update_auto_task_status(task, runtime_status=AUTO_TASK_RUNTIME_IDLE, current_execution_id=None)
        clear_auto_task_running(auto_task_id)
        clear_auto_task_stop_flag(auto_task_id)
        _persist_auto_tasks()
        add_log(0, 'error', f'[自动化] 任务 {auto_task_id} 立即执行启动失败: {str(e)}')
        return jsonify({'error': '任务启动失败'}), 500

    _persist_auto_tasks()

    with auto_task_lock:
        task = _get_auto_task_locked(auto_task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        payload = _sanitize_task_payload(task)
    return jsonify({'message': '任务已开始执行', 'task': payload})


@automation_bp.route('/automation/<int:auto_task_id>', methods=['PUT'])
def update_auto_task(auto_task_id: int):
    """更新自动化任务。"""
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    elif not isinstance(data, dict):
        return jsonify({'error': '请求体必须是 JSON 对象'}), 400

    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            return jsonify({'error': '任务不存在'}), 404
        rollback_snapshot = _build_auto_task_rollback_snapshot(auto_task)
        original_task = deepcopy(auto_task)

    current_desired_status = original_task.get('desired_status', AUTO_TASK_DESIRED_DISABLED)

    name = data.get('name')
    username = data.get('username')
    password = data.get('password')
    cron = data.get('cron')
    download_dir = data.get('download_dir')
    speed_limit = None
    client_impl = data.get('client_impl')
    image_suffix = data.get('image_suffix')
    dir_rule = data.get('dir_rule')
    compression = data.get('compression')
    batch_albums_count = None
    batch_interval_minutes = None

    if download_dir is not None and not validate_path_safety(download_dir):
        return jsonify({'error': '下载目录路径不安全'}), 400

    if cron is not None:
        valid, error_msg = validate_cron_expression(cron)
        if not valid:
            return jsonify({'error': error_msg}), 400

    if 'speed_limit' in data:
        speed_limit = data.get('speed_limit', 0)
        if isinstance(speed_limit, bool):
            return jsonify({'error': '速度限制参数错误: 速度值必须为数字'}), 400
        if speed_limit:
            valid, kb_value, error_msg = validate_speed_limit(str(speed_limit))
            if not valid:
                return jsonify({'error': f'速度限制参数错误: {error_msg}'}), 400
            speed_limit = kb_value
        else:
            speed_limit = 0

    if 'batch_albums_count' in data:
        try:
            batch_albums_count = int(data.get('batch_albums_count'))
        except (TypeError, ValueError):
            return jsonify({'error': '每批下载数量必须是整数'}), 400

        if batch_albums_count < 1 or batch_albums_count > 500:
            return jsonify({'error': '每批下载数量必须在 1-500 之间'}), 400

    if 'batch_interval_minutes' in data:
        try:
            batch_interval_minutes = int(data.get('batch_interval_minutes'))
        except (TypeError, ValueError):
            return jsonify({'error': '批次间隔必须是整数'}), 400

        if batch_interval_minutes < 1 or batch_interval_minutes > 1440:
            return jsonify({'error': '批次间隔必须在 1-1440 分钟之间'}), 400

    desired_status = data.get('desired_status')
    if 'desired_status' in data and desired_status not in {AUTO_TASK_DESIRED_ENABLED, AUTO_TASK_DESIRED_DISABLED}:
        return jsonify({'error': 'desired_status 必须是 enabled 或 disabled'}), 400
    if desired_status not in {AUTO_TASK_DESIRED_ENABLED, AUTO_TASK_DESIRED_DISABLED}:
        desired_status = None

    desired_status_effective = current_desired_status

    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            return jsonify({'error': '任务不存在'}), 404

        if name is not None:
            auto_task['name'] = name
        if username is not None:
            auto_task['username'] = username
        if password:
            auto_task['password'] = password
        if cron is not None:
            auto_task['cron'] = cron
        if download_dir is not None:
            auto_task['download_dir'] = download_dir
        if speed_limit is not None:
            auto_task['speed_limit'] = speed_limit
        if client_impl is not None:
            auto_task['client_impl'] = client_impl
        if image_suffix is not None:
            auto_task['image_suffix'] = image_suffix
        if dir_rule is not None:
            auto_task['dir_rule'] = dir_rule
        if batch_albums_count is not None:
            auto_task['batch_albums_count'] = batch_albums_count
        if batch_interval_minutes is not None:
            auto_task['batch_interval_minutes'] = batch_interval_minutes
        if compression is not None:
            auto_task['compression'] = compression
        auto_task.pop('batch_size', None)

        desired_status_effective = desired_status
        if desired_status_effective is None:
            desired_status_effective = auto_task.get('desired_status', AUTO_TASK_DESIRED_DISABLED)

        if desired_status_effective == AUTO_TASK_DESIRED_ENABLED:
            clear_auto_task_stop_flag(auto_task_id)
            update_auto_task_status(
                auto_task,
                desired_status=desired_status_effective,
                runtime_status=AUTO_TASK_RUNTIME_SCHEDULED,
            )
        else:
            update_auto_task_status(
                auto_task,
                desired_status=AUTO_TASK_DESIRED_DISABLED,
                runtime_status=AUTO_TASK_RUNTIME_IDLE,
                current_execution_id=None,
            )
            auto_task['next_run'] = None

        applied_snapshot = _build_auto_task_rollback_snapshot(auto_task)

    if current_desired_status == AUTO_TASK_DESIRED_ENABLED and _scheduler is not None:
        try:
            unschedule_task(_scheduler, auto_task_id)
        except Exception as e:
            add_log(0, 'error', f'[自动化] 任务 {auto_task_id} 取消旧调度失败: {str(e)}')

    if desired_status_effective == AUTO_TASK_DESIRED_ENABLED:
        if not schedule_auto_task(auto_task_id):
            conflict = False
            with auto_task_lock:
                task = _get_auto_task_locked(auto_task_id)
                if task and _is_auto_task_snapshot_match(task, applied_snapshot, _AUTO_TASK_ROLLBACK_FIELDS):
                    _restore_auto_task_from_snapshot(task, rollback_snapshot)
                elif task and _is_auto_task_snapshot_match(task, applied_snapshot, _AUTO_TASK_UPDATE_CONFLICT_FIELDS):
                    _restore_auto_task_update_fields(task, rollback_snapshot)
                elif task:
                    conflict = True
            _persist_auto_tasks()
            if current_desired_status == AUTO_TASK_DESIRED_ENABLED and _scheduler is not None:
                try:
                    schedule_auto_task(auto_task_id)
                except Exception as e:
                    add_log(0, 'error', f'[自动化] 任务 {auto_task_id} 恢复旧调度失败: {str(e)}')
            if conflict:
                return jsonify({'error': '任务更新失败，检测到并发修改，请重试'}), 409
            return jsonify({'error': '任务更新成功，但调度失败'}), 500
    else:
        _persist_auto_tasks()

    with auto_task_lock:
        task = _get_auto_task_locked(auto_task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        payload = _sanitize_task_payload(task)
    return jsonify({'message': '任务已更新', 'task': payload})


@automation_bp.route('/automation/<int:auto_task_id>', methods=['DELETE'])
def delete_auto_task(auto_task_id: int):
    """删除自动化任务。"""
    with auto_task_lock:
        if auto_task_id not in auto_tasks:
            return jsonify({'error': '任务不存在'}), 404

    try:
        if _scheduler is not None:
            unschedule_task(_scheduler, auto_task_id)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 删除任务 {auto_task_id} 前取消调度失败: {str(e)}')
        return jsonify({'error': '任务删除失败，调度取消异常'}), 500

    set_auto_task_stop_flag(auto_task_id)
    clear_auto_task_running(auto_task_id)

    with auto_task_lock:
        auto_tasks.pop(auto_task_id, None)

    _persist_auto_tasks()
    return jsonify({'message': '任务已删除'})


@automation_bp.route('/automation/<int:auto_task_id>/executions', methods=['GET'])
def get_auto_task_executions(auto_task_id: int):
    """获取自动化任务执行历史。"""
    with auto_task_lock:
        auto_task = _get_auto_task_locked(auto_task_id)
        if not auto_task:
            return jsonify({'error': '任务不存在'}), 404

    with auto_execution_lock:
        task_executions = [deepcopy(ex) for ex in auto_executions.values() if ex.get('auto_task_id') == auto_task_id]

    raw_time_range = request.args.get('time_range')
    time_range = None
    if raw_time_range is not None:
        try:
            time_range = int(raw_time_range)
        except (TypeError, ValueError):
            return jsonify({'error': 'time_range 必须是整数'}), 400

    if time_range is not None:
        if time_range < 1:
            return jsonify({'error': 'time_range 必须大于 0'}), 400
        if time_range > 24 * 31:
            return jsonify({'error': 'time_range 超出允许范围'}), 400

        from datetime import timedelta

        cutoff_ts = (datetime.now() - timedelta(hours=time_range)).timestamp()
        filtered_executions = []
        for ex in task_executions:
            start_time = ex.get('start_time')
            if not start_time:
                continue
            try:
                if datetime.fromisoformat(start_time).timestamp() > cutoff_ts:
                    filtered_executions.append(ex)
            except (TypeError, ValueError, OSError, OverflowError):
                continue
        task_executions = filtered_executions

    def _execution_start_timestamp(execution: Dict[str, Any]) -> float:
        start_time = execution.get('start_time')
        if not start_time:
            return float('-inf')
        try:
            return datetime.fromisoformat(start_time).timestamp()
        except (TypeError, ValueError, OSError, OverflowError):
            return float('-inf')

    task_executions.sort(key=_execution_start_timestamp, reverse=True)
    raw_limit = request.args.get('limit')
    limit = 20
    if raw_limit is not None:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return jsonify({'error': 'limit 必须是整数'}), 400
    if limit < 1:
        return jsonify({'error': 'limit 必须大于 0'}), 400
    if limit > 200:
        limit = 200
    task_executions = task_executions[:limit]

    return jsonify(task_executions)


@automation_bp.route('/automation/execution/<int:execution_id>', methods=['GET'])
def get_execution_detail(execution_id: int):
    """获取执行记录详情，包含关联下载任务。"""
    with auto_execution_lock:
        execution = deepcopy(auto_executions.get(execution_id))
    if not execution:
        return jsonify({'error': '执行记录不存在'}), 404

    downloaded_task_ids = execution.get('downloaded_task_ids', [])
    if not isinstance(downloaded_task_ids, (list, tuple, set)):
        downloaded_task_ids = []
    with task_lock:
        related_tasks = [deep_strip_sensitive(deepcopy(tasks.get(tid))) for tid in downloaded_task_ids if tid in tasks]

    return jsonify({'execution': execution, 'related_tasks': related_tasks})


@automation_bp.route('/automation/execution/<int:execution_id>/logs', methods=['GET'])
def get_execution_logs(execution_id: int):
    """获取执行记录日志。"""
    with auto_execution_lock:
        execution_exists = execution_id in auto_executions
    if not execution_exists:
        return jsonify({'error': '执行记录不存在'}), 404

    raw_limit = request.args.get('limit')
    limit = 200
    if raw_limit is not None:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return jsonify({'error': 'limit 必须是整数'}), 400
    if limit < 1:
        return jsonify({'error': 'limit 必须大于 0'}), 400
    if limit > 500:
        limit = 500
    log_entries = get_logs(task_id=execution_id, level='all', limit=limit)

    formatted_logs = []
    for log in reversed(log_entries):
        timestamp_raw = str(log.get('timestamp', ''))
        timestamp = timestamp_raw[:19].replace('T', ' ') if timestamp_raw else 'unknown'
        level = str(log.get('level', 'info'))
        level_emoji = {'info': 'ℹ️', 'success': '✅', 'error': '❌'}.get(level, '•')
        message = str(log.get('message', ''))
        formatted_logs.append(f"[{timestamp}] {level_emoji} {message}")

    return jsonify(formatted_logs)


@automation_bp.route('/automation/execution/<int:execution_id>', methods=['DELETE'])
def delete_execution(execution_id: int):
    """删除执行记录。"""
    with auto_execution_lock:
        execution = auto_executions.get(execution_id)
        if not execution:
            return jsonify({'error': '执行记录不存在'}), 404

        if execution.get('status') == 'running':
            return jsonify({'error': '无法删除正在运行的执行记录'}), 400

        del auto_executions[execution_id]
        snapshot = {eid: deepcopy(ex) for eid, ex in auto_executions.items()}

        try:
            save_all_auto_executions(snapshot)
        except Exception as e:
            auto_executions[execution_id] = execution
            add_log(0, 'error', f'[自动化] 保存执行记录失败: {str(e)}')
            return jsonify({'error': '执行记录删除失败，持久化未完成'}), 500

    return jsonify({'message': '执行记录已删除'})
