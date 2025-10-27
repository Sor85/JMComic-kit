#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路由统一注册模块
将所有 Blueprint 注册到 Flask app
"""

from .tasks_routes import tasks_bp
from .automation_routes import automation_bp, init_scheduler
from .logs_routes import logs_bp
from .stats_routes import stats_bp
from .csv_routes import csv_bp


def register_blueprints(app, scheduler=None):
    """注册所有 Blueprint 到 Flask app
    
    Args:
        app: Flask 应用实例
        scheduler: APScheduler 调度器实例（用于自动化任务）
    """
    # 初始化自动化路由的调度器引用
    if scheduler:
        init_scheduler(scheduler)
    
    # 注册所有 Blueprint，统一使用 /api 前缀
    app.register_blueprint(tasks_bp, url_prefix='/api')
    app.register_blueprint(automation_bp, url_prefix='/api')
    app.register_blueprint(logs_bp, url_prefix='/api')
    app.register_blueprint(stats_bp, url_prefix='/api')
    app.register_blueprint(csv_bp, url_prefix='/api')


__all__ = ['register_blueprints', 'tasks_bp', 'automation_bp', 'logs_bp', 'stats_bp', 'csv_bp']

