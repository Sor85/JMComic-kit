#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务管理路由
处理下载和导出任务的 CRUD 操作
"""

import threading
from copy import deepcopy
from datetime import datetime
from flask import Blueprint, request, jsonify
from server.state import tasks, task_lock, get_next_task_id
from server.services.download_service_rust import run_download_task_rust as svc_run_download_task
from server.services.export_service import run_export_task as svc_run_export_task
from server.utils.sanitize import deep_strip_sensitive
from server.utils.validators import validate_path_safety, validate_speed_limit
from server.utils.logs import add_log

tasks_bp = Blueprint('tasks', __name__)


def run_download_task(task_id, album_ids, photo_ids, config):
    """运行下载任务（委托服务层）"""
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return
        task.update({
            'album_ids': album_ids,
            'photo_ids': photo_ids,
            'config': config,
        })
    svc_run_download_task(task)


def run_export_task(task_id, username, password, config):
    """运行导出收藏夹任务（委托服务层）"""
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return
        task.update({
            'username': username,
            'password': password,
            'config': config,
        })
    svc_run_export_task(task)


@tasks_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """获取所有任务（脱敏返回）"""
    with task_lock:
        tasks_snapshot = [deepcopy(task) for task in tasks.values()]
    return jsonify([deep_strip_sensitive(t) for t in tasks_snapshot])


@tasks_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """获取单个任务详情"""
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
        task_snapshot = deepcopy(task)
    return jsonify(deep_strip_sensitive(task_snapshot))


@tasks_bp.route('/download', methods=['POST'])
def create_download_task():
    """创建下载任务"""
    data = request.get_json(silent=True) or {}
    album_ids = data.get('album_ids', [])
    photo_ids = data.get('photo_ids', [])
    config = data.get('config', {})
    
    if not album_ids and not photo_ids:
        return jsonify({'error': '请至少提供一个本子ID或章节ID'}), 400
    
    # 验证下载目录路径安全性
    download_dir = config.get('download_dir', './download/')
    if not validate_path_safety(download_dir):
        return jsonify({'error': '下载目录路径不安全'}), 400
    
    # 验证速度限制
    if 'speed_limit' in config and config['speed_limit']:
        valid, kb_value, error_msg = validate_speed_limit(str(config['speed_limit']))
        if not valid:
            return jsonify({'error': f'速度限制参数错误: {error_msg}'}), 400
        config['speed_limit'] = kb_value
    
    task_id = get_next_task_id()
    
    task = {
        'id': task_id,
        'type': 'download',
        'status': 'pending',
        'progress': 0,
        'album_ids': album_ids,
        'photo_ids': photo_ids,
        'config': config,
        'create_time': datetime.now().isoformat(),
        'start_time': None,
        'end_time': None,
        'error': None
    }
    
    with task_lock:
        tasks[task_id] = task
    add_log(task_id, 'info', f'创建下载任务 #{task_id}')
    
    # 启动后台线程
    thread = threading.Thread(
        target=run_download_task,
        args=(task_id, album_ids, photo_ids, config)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify(deep_strip_sensitive(task))


@tasks_bp.route('/tasks/<int:task_id>/compress', methods=['POST'])
def compress_task_manually(task_id):
    """手动压缩已完成的任务"""
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404

        if task['status'] not in ['completed', 'partial_success']:
            return jsonify({'error': '只能压缩已完成的任务'}), 400

        task_snapshot = deepcopy(task)
    
    # 读取压缩配置
    data = request.json or {}
    compression_config = {
        'enabled': True,
        'format': data.get('format', 'zip'),
        'level': data.get('level', 'album'),
        'password': data.get('password'),
        'delete_original': data.get('delete_original', False)
    }
    
    # 验证格式
    if compression_config['format'] not in ['zip', '7z']:
        return jsonify({'error': '不支持的压缩格式'}), 400
    
    if compression_config['level'] not in ['album', 'photo']:
        return jsonify({'error': '不支持的压缩级别'}), 400
    
    # 获取下载目录
    download_dir = task_snapshot['config'].get('download_dir', './download/')
    
    # 执行压缩
    from server.services.compression_service import compress_task_downloads
    add_log(task_id, 'info', '开始手动压缩...')
    
    result = compress_task_downloads(task_id, download_dir, compression_config)
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': result['message'],
            'files': result['files']
        })
    else:
        return jsonify({
            'success': False,
            'message': result['message'],
            'errors': result.get('errors', [])
        }), 500


@tasks_bp.route('/export', methods=['POST'])
def create_export_task():
    """创建导出收藏夹任务"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')
    config = data.get('config', {})
    
    if not username or not password:
        return jsonify({'error': '请提供账号和密码'}), 400
    
    # 验证保存目录路径安全性
    save_dir = config.get('save_dir', './export/')
    if not validate_path_safety(save_dir):
        return jsonify({'error': '保存目录路径不安全'}), 400
    
    task_id = get_next_task_id()
    
    task = {
        'id': task_id,
        'type': 'export',
        'status': 'pending',
        'progress': 0,
        'username': username,
        'config': config,
        'create_time': datetime.now().isoformat(),
        'start_time': None,
        'end_time': None,
        'error': None
    }
    
    with task_lock:
        tasks[task_id] = task
    add_log(task_id, 'info', f'创建导出任务 #{task_id}')
    
    # 启动后台线程
    thread = threading.Thread(
        target=run_export_task,
        args=(task_id, username, password, config)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify(deep_strip_sensitive(task))


@tasks_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务及其日志"""
    with task_lock:
        if task_id not in tasks:
            return jsonify({'error': '任务不存在'}), 404

        del tasks[task_id]
    
    # 删除任务的所有日志
    from server.utils.logs import delete_task_logs
    delete_task_logs(task_id)
    
    # 持久化更新
    from server.utils.storage import save_manual_tasks
    with task_lock:
        tasks_snapshot = {tid: deepcopy(task) for tid, task in tasks.items()}
    save_manual_tasks(tasks_snapshot)
    
    return jsonify({'message': '任务已删除'})


@tasks_bp.route('/tasks/<int:task_id>/retry', methods=['POST'])
def retry_task_failed_images(task_id):
    """重试下载任务中失败的图片"""
    from server.services.download_retry_service import retry_failed_images

    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': '任务不存在'}), 404
    
    # 在新线程中执行重试
    def do_retry():
        result = retry_failed_images(task_id)
        if not result['success']:
            add_log(task_id, 'error', f'重试失败: {result["message"]}')
    
    thread = threading.Thread(target=do_retry)
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': '已开始重试失败的图片', 'task_id': task_id})
