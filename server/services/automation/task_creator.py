#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量下载任务创建器

负责创建下载任务并启动下载线程
"""
import threading
from datetime import datetime
from typing import Any, Dict, List
from server.state import tasks, task_lock, get_next_task_id
from server.utils import add_log


def create_batch_download_tasks(
    album_ids: List[str],
    auto_task: Dict[str, Any],
    execution_id: int
) -> List[int]:
    """创建下载任务
    
    为传入的相册ID列表创建单个下载任务并启动。
    （分批逻辑已移至 executor.py）
    
    Args:
        album_ids: 要下载的相册ID列表
        auto_task: 自动化任务配置
        execution_id: 执行记录ID
        
    Returns:
        创建的任务ID列表
    """
    if not album_ids:
        add_log(execution_id, 'error', '[自动化] 传入空的下载列表，已跳过')
        return []
    
    # 直接创建单个任务
    task_id = _create_single_download_task(
        batch_albums=album_ids,
        auto_task=auto_task,
        execution_id=execution_id,
        batch_info=None
    )
    
    return [task_id]


def _create_single_download_task(
    batch_albums: List[str],
    auto_task: Dict[str, Any],
    execution_id: int,
    batch_info: tuple = None
) -> int:
    """创建单个下载任务并启动线程
    
    Args:
        batch_albums: 本批次的相册ID列表
        auto_task: 自动化任务配置
        execution_id: 执行记录ID
        batch_info: 批次信息 (当前批次号, 总批次数)，None表示不分批
        
    Returns:
        任务ID
    """
    task_id = get_next_task_id()
    
    task = {
        'id': task_id,
        'type': 'download',
        'status': 'pending',
        'progress': 0,
        'album_ids': batch_albums,
        'photo_ids': [],
        'config': {
            'download_dir': auto_task['download_dir'],
            'client_impl': auto_task.get('client_impl', 'api'),
            'image_suffix': auto_task.get('image_suffix', ''),
            'dir_rule': auto_task.get('dir_rule', 'Aauthoroname/Pindextitle'),
            'username': auto_task['username'],
            'password': auto_task['password'],
            'speed_limit': auto_task.get('speed_limit', 0),
            'use_rust_downloader': True,  # 使用 Rust 下载器（支持图片重组）
            'pdf': auto_task.get('pdf', {}),  # PDF配置
            'compression': auto_task.get('compression', {}),  # 压缩配置
        },
        'create_time': datetime.now().isoformat(),
        'start_time': None,
        'end_time': None,
        'error': None,
        'auto_task_id': auto_task['id'],
        'auto_task_name': auto_task['name'],
        'auto_execution_id': execution_id
    }
    
    with task_lock:
        tasks[task_id] = task
    
    # 记录日志
    if batch_info:
        batch_num, total_batches = batch_info
        add_log(
            execution_id, 
            'info', 
            f'[自动化] 创建下载任务 #{task_id} (批次 {batch_num}/{total_batches})，本子数量: {len(batch_albums)}'
        )
    else:
        add_log(
            execution_id, 
            'info', 
            f'[自动化] 创建下载任务 #{task_id}，本子数量: {len(batch_albums)}'
        )
    
    # 启动下载线程
    thread = threading.Thread(
        target=_run_download_task,
        args=(task_id, batch_albums, task['config'])
    )
    thread.daemon = True
    thread.start()
    
    return task_id


def _run_download_task(task_id: int, album_ids: List[str], config: Dict[str, Any]) -> None:
    """运行下载任务（在独立线程中执行）
    
    使用 Rust 下载器进行下载，支持禁漫图片分片重组
    
    Args:
        task_id: 任务ID
        album_ids: 相册ID列表
        config: 下载配置
    """
    from server.services.download_service_rust import run_download_task_rust
    
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return

        task.update({
            'album_ids': album_ids,
            'photo_ids': [],
            'config': config,
        })
    
    run_download_task_rust(task)


__all__ = ["create_batch_download_tasks"]

