#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载失败图片重试服务

专门处理下载任务中失败图片的重试
"""
from datetime import datetime
from typing import List
from server.state import tasks
from server.utils import add_log


def retry_failed_images(task_id: int) -> dict:
    """重试下载任务中失败的图片
    
    Args:
        task_id: 任务ID
        
    Returns:
        重试结果字典，包含 success 和 message
    """
    task = tasks.get(task_id)
    
    if not task:
        return {'success': False, 'message': '任务不存在'}
    
    if task['type'] != 'download':
        return {'success': False, 'message': '只能重试下载任务'}
    
    # 检查是否有失败的图片
    failed_images = task.get('failed_images', [])
    if not failed_images or len(failed_images) == 0:
        return {'success': False, 'message': '该任务没有失败的图片'}
    
    # 检查任务状态
    if task['status'] == 'running':
        return {'success': False, 'message': '任务正在运行中，无法重试'}
    
    add_log(task_id, 'info', f'开始重试 {len(failed_images)} 张失败的图片...')
    
    # 检查是否使用 Rust 下载器
    config = task.get('config', {})
    use_rust = config.get('use_rust_downloader', True)
    
    try:
        from server.utils.rust_downloader import is_rust_downloader_available
        
        if not use_rust or not is_rust_downloader_available():
            add_log(task_id, 'info', 'Rust 下载器不可用，使用 Python 下载器重试')
            return _retry_with_python_downloader(task_id, task, failed_images)
        else:
            return _retry_with_rust_downloader(task_id, task, failed_images)
            
    except Exception as e:
        add_log(task_id, 'error', f'重试失败: {str(e)}')
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': f'重试失败: {str(e)}'}


def _retry_with_rust_downloader(task_id: int, task: dict, failed_images: List[str]) -> dict:
    """使用 Rust 下载器重试失败的图片"""
    from server.utils.rust_downloader import download_images_with_rust, ImageTask
    from jmcomic import create_option
    from server.utils.jmcomic_helper import setup_jmcomic_env
    import os
    
    config = task.get('config', {})
    
    # 配置环境变量
    setup_jmcomic_env(
        username=config.get('username', ''),
        password=config.get('password', '')
    )
    
    # 创建 option
    option = create_option()
    option.client.impl = config.get('client_impl', 'api')
    
    try:
        # 解析失败的图片信息
        # failed_images 格式: ["url1", "url2", ...]
        # 我们需要重新构建 ImageTask 列表
        
        # 由于我们只有URL，需要从原始下载目录推断路径
        # 这里做简化处理：直接使用URL重试，路径从URL推断
        
        retry_tasks = []
        for url in failed_images:
            # 从URL中提取文件名
            filename = url.split('/')[-1]
            
            # 使用原始下载目录
            download_dir = config.get('download_dir', './download/')
            
            # 简化路径构建（实际应该更精确）
            # TODO: 改进路径推断逻辑
            img_path = os.path.join(download_dir, filename)
            
            # 获取请求头
            headers = option.build_jm_client().get_jm_image_headers()
            
            retry_tasks.append(ImageTask(
                url=url,
                path=img_path,
                headers=headers,
                scramble_id=0  # 默认不重组，除非能从元数据中获取
            ))
        
        add_log(task_id, 'info', f'准备重试 {len(retry_tasks)} 张图片')
        
        # 使用 Rust 下载器下载
        concurrent = config.get('concurrent', 50)
        retry_count = config.get('retry_count', 3)
        timeout = config.get('timeout', 30)
        
        result = download_images_with_rust(
            images=retry_tasks,
            concurrent=concurrent,
            retry=retry_count,
            timeout=timeout,
            progress_callback=None
        )
        
        # 更新任务状态
        if result.failed == 0:
            # 全部重试成功
            task['failed_images'] = []
            if task['status'] == 'partial_success':
                task['status'] = 'completed'
                task['error'] = None
            add_log(task_id, 'success', f'✅ 重试成功！全部 {result.success} 张图片已下载')
            return {'success': True, 'message': f'重试成功，{result.success} 张图片已下载'}
        
        elif result.success > 0:
            # 部分重试成功
            new_failed = result.failed_urls
            task['failed_images'] = new_failed
            add_log(task_id, 'warning', f'⚠️ 重试部分成功：成功 {result.success} 张，仍失败 {result.failed} 张')
            return {
                'success': True, 
                'message': f'部分成功：{result.success} 张成功，{result.failed} 张仍失败'
            }
        
        else:
            # 全部重试失败
            add_log(task_id, 'error', f'❌ 重试失败，{result.failed} 张图片仍无法下载')
            return {'success': False, 'message': f'重试失败，{result.failed} 张图片无法下载'}
        
    except Exception as e:
        add_log(task_id, 'error', f'重试失败: {str(e)}')
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': f'重试失败: {str(e)}'}


def _retry_with_python_downloader(task_id: int, task: dict, failed_images: List[str]) -> dict:
    """使用 Python 下载器重试失败的图片（后备方案）"""
    add_log(task_id, 'info', 'Python 下载器重试功能暂未实现')
    return {'success': False, 'message': 'Python 下载器重试功能暂未实现，请使用 Rust 下载器'}


__all__ = ["retry_failed_images"]

