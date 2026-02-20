#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志管理路由
处理日志查询、清空和实时日志获取
"""

from html import escape

from flask import Blueprint, request, jsonify
from server.utils.logs import get_logs as get_logs_safe, clear_logs as clear_logs_safe

logs_bp = Blueprint('logs', __name__)


@logs_bp.route('/logs', methods=['GET'])
def get_logs():
    """获取日志"""
    task_id = request.args.get('task_id', type=int)
    level = request.args.get('level', 'all')
    limit = request.args.get('limit', 100, type=int)
    
    filtered_logs = get_logs_safe(task_id=task_id, level=level, limit=limit)
    return jsonify(filtered_logs)


@logs_bp.route('/realtime_logs/<int:task_id>', methods=['GET'])
def get_realtime_logs(task_id):
    """获取任务的实时日志（格式化为文本数组）"""
    task_logs = get_logs_safe(task_id=task_id, level='all', limit=1000)

    formatted_logs = []
    for log in reversed(task_logs):
        timestamp_raw = str(log.get('timestamp', ''))
        timestamp = timestamp_raw[:19].replace('T', ' ') if timestamp_raw else 'unknown'
        level = str(log.get('level', 'info'))
        level_emoji = {
            'info': 'ℹ️',
            'success': '✅',
            'error': '❌'
        }.get(level, '•')
        message = escape(str(log.get('message', '')))
        formatted_logs.append(f"[{timestamp}] {level_emoji} {message}")

    return jsonify(formatted_logs)


@logs_bp.route('/logs', methods=['DELETE'])
def clear_logs():
    """清空日志"""
    clear_logs_safe()
    return jsonify({'message': '日志已清空'})

