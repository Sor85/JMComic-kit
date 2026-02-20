#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计和快照路由
处理任务统计信息和实时快照查询
"""

from copy import deepcopy

from flask import Blueprint, request, jsonify
from server.state import tasks, task_lock
from server.utils.sanitize import deep_strip_sensitive
from server.utils.logs import get_logs as get_logs_safe, get_total_logs_count

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/task_snapshot/<int:task_id>', methods=['GET'])
def get_task_snapshot(task_id: int):
    """返回单个任务的当前状态以及最近日志，用于前端即时一致性刷新。"""
    with task_lock:
        task = deepcopy(tasks.get(task_id))
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    limit = request.args.get('limit', 100, type=int)
    snap_logs = get_logs_safe(task_id=task_id, level='all', limit=limit)
    return jsonify({
        'task': deep_strip_sensitive(task),
        'logs': snap_logs,
    })


@stats_bp.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    with task_lock:
        task_list = [deepcopy(task) for task in tasks.values()]

    stats = {
        'total_tasks': len(task_list),
        'running': sum(1 for t in task_list if t.get('status') == 'running'),
        'completed': sum(1 for t in task_list if t.get('status') == 'completed'),
        'failed': sum(1 for t in task_list if t.get('status') == 'failed'),
        'pending': sum(1 for t in task_list if t.get('status') == 'pending'),
        'total_logs': get_total_logs_count()
    }
    return jsonify(stats)


@stats_bp.route('/version', methods=['GET'])
def get_version():
    """获取版本信息"""
    from server.version import __version__, PROJECT_NAME, FEATURES, BUILD_DATE
    
    return jsonify({
        'version': __version__,
        'project_name': PROJECT_NAME,
        'features': FEATURES,
        'build_date': BUILD_DATE
    })
