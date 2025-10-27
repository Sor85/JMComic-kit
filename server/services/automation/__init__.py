#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化任务服务模块

提供自动化下载任务的完整功能：
- 任务执行：协调收藏夹获取、本地扫描、批量下载
- 调度管理：启动、停止、更新定时任务
- 收藏夹获取：登录并导出收藏夹数据
- 本地扫描：扫描已下载的相册
- 任务创建：批量创建下载任务
"""

from .executor import execute_auto_sync
from .scheduler import schedule_task, unschedule_task, update_next_run_time
from .favorites_fetcher import fetch_favorites
from .local_scanner import scan_local_albums
from .task_creator import create_batch_download_tasks

__all__ = [
    "execute_auto_sync",
    "schedule_task",
    "unschedule_task",
    "update_next_run_time",
    "fetch_favorites",
    "scan_local_albums",
    "create_batch_download_tasks",
]

