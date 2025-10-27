#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化任务路由

处理自动化任务的完整 CRUD 和调度管理
"""
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify
from server.state import tasks, auto_tasks, auto_executions, get_next_auto_task_id, set_auto_task_stop_flag, clear_auto_task_stop_flag
from server.services.automation import execute_auto_sync, schedule_task, unschedule_task
from server.utils.storage import save_auto_tasks as storage_save_auto_tasks
from server.utils.sanitize import deep_strip_sensitive
from server.utils.validators import validate_path_safety, validate_cron_expression, validate_speed_limit
from server.utils.logs import add_log, get_logs

automation_bp = Blueprint('automation', __name__)

# 调度器实例将在注册 Blueprint 时注入
_scheduler = None


def init_scheduler(scheduler):
    """初始化调度器引用"""
    global _scheduler
    _scheduler = scheduler


def run_auto_sync_task(auto_task_id: int):
    """运行自动同步任务（线程入口函数）"""
    auto_task = auto_tasks.get(auto_task_id)
    if not auto_task:
        return
    execute_auto_sync(auto_task, _scheduler)


def schedule_auto_task(auto_task_id: int):
    """调度自动任务"""
    auto_task = auto_tasks.get(auto_task_id)
    if not auto_task:
        return
    
    success = schedule_task(_scheduler, auto_task, run_auto_sync_task)
    
    if success:
        try:
            storage_save_auto_tasks(auto_tasks)
        except Exception as e:
            add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')


@automation_bp.route('/automation', methods=['GET'])
def get_auto_tasks():
    """获取所有自动化任务"""
    return jsonify(deep_strip_sensitive(list(auto_tasks.values())))


@automation_bp.route('/automation/<int:auto_task_id>', methods=['GET'])
def get_auto_task_detail(auto_task_id: int):
    """获取单个自动化任务
    
    默认脱敏；当 include_sensitive=1 时，返回完整任务（包含 password）
    """
    task = auto_tasks.get(auto_task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    include_sensitive = request.args.get('include_sensitive', '0') == '1'
    return jsonify(task if include_sensitive else deep_strip_sensitive(task))


@automation_bp.route('/automation', methods=['POST'])
def create_auto_task():
    """创建自动化任务"""
    data = request.json
    
    # 提取参数
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
    
    # 验证必填字段
    if not name or not username or not password:
        return jsonify({'error': '任务名称、账号和密码不能为空'}), 400
    
    # 验证下载目录路径安全性
    if not validate_path_safety(download_dir):
        return jsonify({'error': '下载目录路径不安全'}), 400
    
    # 验证 Cron 表达式
    valid, error_msg = validate_cron_expression(cron)
    if not valid:
        return jsonify({'error': error_msg}), 400
    
    # 验证速度限制
    if speed_limit:
        valid, kb_value, error_msg = validate_speed_limit(str(speed_limit))
        if not valid:
            return jsonify({'error': f'速度限制参数错误: {error_msg}'}), 400
        speed_limit = kb_value
    
    # 验证批次参数
    if batch_albums_count < 1 or batch_albums_count > 500:
        return jsonify({'error': '每批下载数量必须在 1-500 之间'}), 400
    
    if batch_interval_minutes < 1 or batch_interval_minutes > 1440:
        return jsonify({'error': '批次间隔必须在 1-1440 分钟之间'}), 400
    
    # 创建任务
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
        'run_count': 0,
        'downloaded_count': 0,
        'skipped_count': 0,
        'monthly_new_count': 0,
        'last_month_count': 0,
        'created_time': datetime.now().isoformat(),
        'last_run': None,
        'next_run': None
    }
    
    auto_tasks[auto_task_id] = auto_task
    
    # 持久化任务到磁盘
    try:
        storage_save_auto_tasks(auto_tasks)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')
    
    # 如果选择立即执行
    if run_now:
        auto_task['status'] = 'running'
        schedule_auto_task(auto_task_id)
    
    return jsonify(auto_task)


@automation_bp.route('/automation/<int:auto_task_id>/start', methods=['POST'])
def start_auto_task(auto_task_id: int):
    """启动自动化任务"""
    auto_task = auto_tasks.get(auto_task_id)
    if not auto_task:
        return jsonify({'error': '任务不存在'}), 404
    
    if auto_task['status'] == 'running':
        return jsonify({'error': '任务已在运行中'}), 400
    
    auto_task['status'] = 'running'
    schedule_auto_task(auto_task_id)
    
    try:
        storage_save_auto_tasks(auto_tasks)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')
    
    return jsonify({'message': '任务已启动', 'task': auto_task})


@automation_bp.route('/automation/<int:auto_task_id>/stop', methods=['POST'])
def stop_auto_task(auto_task_id: int):
    """停止自动化任务"""
    auto_task = auto_tasks.get(auto_task_id)
    if not auto_task:
        return jsonify({'error': '任务不存在'}), 404
    
    auto_task['status'] = 'stopped'
    auto_task['next_run'] = None
    
    # 设置停止标志（用于中断正在等待的批次下载）
    set_auto_task_stop_flag(auto_task_id)
    
    # 从调度器移除任务
    unschedule_task(_scheduler, auto_task_id)
    
    try:
        storage_save_auto_tasks(auto_tasks)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')
    
    return jsonify({'message': '任务已停止', 'task': auto_task})


@automation_bp.route('/automation/<int:auto_task_id>/run', methods=['POST'])
def run_auto_task_now(auto_task_id: int):
    """立即执行自动化任务"""
    auto_task = auto_tasks.get(auto_task_id)
    if not auto_task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 临时置为运行中
    auto_task['status'] = 'running'
    
    # 在新线程中执行
    thread = threading.Thread(
        target=run_auto_sync_task,
        args=(auto_task_id,)
    )
    thread.daemon = True
    thread.start()
    
    try:
        storage_save_auto_tasks(auto_tasks)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')
    
    return jsonify({'message': '任务已开始执行', 'task': deep_strip_sensitive(auto_task)})


@automation_bp.route('/automation/<int:auto_task_id>', methods=['PUT'])
def update_auto_task(auto_task_id: int):
    """更新自动化任务"""
    auto_task = auto_tasks.get(auto_task_id)
    if not auto_task:
        return jsonify({'error': '任务不存在'}), 404
    
    data = request.json
    
    # 提取参数
    name = data.get('name', auto_task['name'])
    username = data.get('username', auto_task['username'])
    password = data.get('password', '')
    cron = data.get('cron', auto_task['cron'])
    download_dir = data.get('download_dir', auto_task['download_dir'])
    speed_limit = data.get('speed_limit', auto_task.get('speed_limit', 0))
    client_impl = data.get('client_impl', auto_task['client_impl'])
    image_suffix = data.get('image_suffix', auto_task.get('image_suffix', ''))
    dir_rule = data.get('dir_rule', auto_task.get('dir_rule', 'Aauthoroname/Pindextitle'))
    # 兼容旧数据：如果存在 batch_size 则转换为新字段
    batch_albums_count = data.get('batch_albums_count', auto_task.get('batch_albums_count', auto_task.get('batch_size', 50)))
    batch_interval_minutes = data.get('batch_interval_minutes', auto_task.get('batch_interval_minutes', 30))
    compression = data.get('compression', auto_task.get('compression', {}))
    
    # 验证下载目录路径安全性
    if not validate_path_safety(download_dir):
        return jsonify({'error': '下载目录路径不安全'}), 400
    
    # 验证 Cron 表达式
    valid, error_msg = validate_cron_expression(cron)
    if not valid:
        return jsonify({'error': error_msg}), 400
    
    # 验证速度限制
    if speed_limit:
        valid, kb_value, error_msg = validate_speed_limit(str(speed_limit))
        if not valid:
            return jsonify({'error': f'速度限制参数错误: {error_msg}'}), 400
        speed_limit = kb_value
    
    # 验证批次参数
    if batch_albums_count < 1 or batch_albums_count > 500:
        return jsonify({'error': '每批下载数量必须在 1-500 之间'}), 400
    
    if batch_interval_minutes < 1 or batch_interval_minutes > 1440:
        return jsonify({'error': '批次间隔必须在 1-1440 分钟之间'}), 400
    
    # 记录旧状态
    was_running = auto_task['status'] == 'running'
    
    # 如果正在运行，先停止
    if was_running:
        unschedule_task(_scheduler, auto_task_id)
    
    # 更新任务信息
    auto_task['name'] = name
    auto_task['username'] = username
    if password:  # 只有提供了密码才更新
        auto_task['password'] = password
    auto_task['cron'] = cron
    auto_task['download_dir'] = download_dir
    auto_task['speed_limit'] = speed_limit
    auto_task['client_impl'] = client_impl
    auto_task['image_suffix'] = image_suffix
    auto_task['dir_rule'] = dir_rule
    auto_task['batch_albums_count'] = batch_albums_count
    auto_task['batch_interval_minutes'] = batch_interval_minutes
    auto_task['compression'] = compression
    # 移除旧的 batch_size 字段（如果存在）
    auto_task.pop('batch_size', None)
    
    # 如果之前在运行，重新启动
    if was_running:
        schedule_auto_task(auto_task_id)
    
    try:
        storage_save_auto_tasks(auto_tasks)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')
    
    return jsonify({'message': '任务已更新', 'task': auto_task})


@automation_bp.route('/automation/<int:auto_task_id>', methods=['DELETE'])
def delete_auto_task(auto_task_id: int):
    """删除自动化任务"""
    if auto_task_id not in auto_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    # 先停止任务
    unschedule_task(_scheduler, auto_task_id)
    
    del auto_tasks[auto_task_id]
    
    try:
        storage_save_auto_tasks(auto_tasks)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存任务配置失败: {str(e)}')
    
    return jsonify({'message': '任务已删除'})


@automation_bp.route('/automation/<int:auto_task_id>/executions', methods=['GET'])
def get_auto_task_executions(auto_task_id: int):
    """获取自动化任务的执行历史列表
    
    支持参数：
    - limit: 返回数量，默认20
    - time_range: 时间范围（小时），如24、168、720，默认不限制
    """
    auto_task = auto_tasks.get(auto_task_id)
    if not auto_task:
        return jsonify({'error': '任务不存在'}), 404
    
    # 筛选该任务的执行记录
    task_executions = [
        ex for ex in auto_executions.values() 
        if ex.get('auto_task_id') == auto_task_id
    ]
    
    # 时间范围筛选
    time_range = request.args.get('time_range', type=int)
    if time_range:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(hours=time_range)
        task_executions = [
            ex for ex in task_executions 
            if datetime.fromisoformat(ex['start_time']) > cutoff
        ]
    
    # 按开始时间倒序
    task_executions.sort(key=lambda x: x.get('start_time', ''), reverse=True)
    
    # 限制返回数量
    limit = request.args.get('limit', 20, type=int)
    task_executions = task_executions[:limit]
    
    return jsonify(task_executions)


@automation_bp.route('/automation/execution/<int:execution_id>', methods=['GET'])
def get_execution_detail(execution_id: int):
    """获取执行记录详情，包含关联的下载任务"""
    execution = auto_executions.get(execution_id)
    if not execution:
        return jsonify({'error': '执行记录不存在'}), 404
    
    # 获取关联的下载任务
    downloaded_task_ids = execution.get('downloaded_task_ids', [])
    related_tasks = [
        deep_strip_sensitive(tasks.get(tid)) 
        for tid in downloaded_task_ids 
        if tid in tasks
    ]
    
    return jsonify({
        'execution': execution,
        'related_tasks': related_tasks
    })


@automation_bp.route('/automation/execution/<int:execution_id>/logs', methods=['GET'])
def get_execution_logs(execution_id: int):
    """获取执行记录的日志"""
    execution = auto_executions.get(execution_id)
    if not execution:
        return jsonify({'error': '执行记录不存在'}), 404
    
    # 获取该执行ID的所有日志
    limit = request.args.get('limit', 200, type=int)
    logs = get_logs(task_id=execution_id, level='all', limit=limit)
    
    # 格式化为文本数组（与 realtime_logs 一致）
    formatted_logs = []
    for log in reversed(logs):  # 按时间正序
        timestamp = log['timestamp'][:19].replace('T', ' ')
        level_emoji = {
            'info': 'ℹ️',
            'success': '✅',
            'error': '❌'
        }.get(log['level'], '•')
        formatted_logs.append(f"[{timestamp}] {level_emoji} {log['message']}")
    
    return jsonify(formatted_logs)


@automation_bp.route('/automation/execution/<int:execution_id>', methods=['DELETE'])
def delete_execution(execution_id: int):
    """删除执行记录"""
    if execution_id not in auto_executions:
        return jsonify({'error': '执行记录不存在'}), 404
    
    # 检查执行记录是否正在运行
    execution = auto_executions[execution_id]
    if execution.get('status') == 'running':
        return jsonify({'error': '无法删除正在运行的执行记录'}), 400
    
    # 删除执行记录
    del auto_executions[execution_id]
    
    # 持久化更新：保存所有剩余的执行记录
    try:
        from server.utils.storage import save_all_auto_executions
        save_all_auto_executions(auto_executions)
    except Exception as e:
        add_log(0, 'error', f'[自动化] 保存执行记录失败: {str(e)}')
    
    return jsonify({'message': '执行记录已删除'})
