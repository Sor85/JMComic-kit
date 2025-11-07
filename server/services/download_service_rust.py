"""
支持 Rust 下载器的下载服务

提供两种下载方式：
1. Rust 下载器（高性能，推荐）
2. Python 下载器（兼容性后备）
"""
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List
from server.types import DownloadTask
from server.utils import add_log


def sanitize_path(path: str, max_bytes: int = 200) -> str:
    """
    清理路径中的非法字符并限制长度（支持 Windows 和 Linux）
    
    Args:
        path: 原始路径
        max_bytes: 单个路径组件的最大字节长度（UTF-8）
                   Linux: 255 字节，Windows: 255 字符
                   默认 200 字节以确保安全
        
    Returns:
        清理后的安全路径
    """
    import platform
    is_windows = platform.system() == 'Windows'
    
    # 规范化路径分隔符
    path = path.replace('\\', '/')
    had_leading_slash = path.startswith('/')
    
    # 分离驱动器和路径（Windows 绝对路径如 C:/）
    drive = ''
    rest = path
    
    if is_windows and len(path) >= 2 and path[1] == ':' and path[0].isalpha():
        drive = path[:2]
        rest = path[2:].lstrip('/')
    elif had_leading_slash:
        rest = path.lstrip('/')
    
    # 分割路径
    parts = rest.split('/')
    cleaned_parts = []
    
    # 平台相关的非法字符
    if is_windows:
        # Windows 不允许的文件名字符
        illegal_chars = r'[<>:"|?*\x00-\x1f]'
    else:
        # Linux 只禁止路径分隔符（已经用 split 处理）和 NULL
        illegal_chars = r'[\x00]'
    
    for i, part in enumerate(parts):
        if not part or part == '.':  # 跳过空部分和单点
            continue
        
        # 移除非法字符
        cleaned = re.sub(illegal_chars, '_', part)
        
        # 移除前后空格和点（Windows 要求，Linux 建议）
        cleaned = cleaned.strip('. ')
        
        # 如果清理后为空，使用默认名称
        if not cleaned:
            cleaned = 'unnamed'
        
        # 限制长度（基于字节长度，兼容 Linux 的 255 字节限制）
        cleaned_bytes = cleaned.encode('utf-8')
        if len(cleaned_bytes) > max_bytes:
            # 保留文件扩展名
            name, ext = os.path.splitext(cleaned)
            ext_bytes = ext.encode('utf-8')
            
            if ext and len(ext_bytes) <= 10:  # 合理的扩展名长度
                # 截断文件名部分，保留扩展名
                max_name_bytes = max_bytes - len(ext_bytes)
                name_bytes = name.encode('utf-8')
                
                # 按字节截断（注意不要截断多字节字符）
                if len(name_bytes) > max_name_bytes:
                    name_bytes = name_bytes[:max_name_bytes]
                    # 解码，忽略不完整的字符
                    name = name_bytes.decode('utf-8', errors='ignore')
                
                cleaned = name + ext
            else:
                # 没有扩展名或扩展名太长，直接按字节截断
                cleaned_bytes = cleaned_bytes[:max_bytes]
                cleaned = cleaned_bytes.decode('utf-8', errors='ignore')
        
        # Windows 保留名称检查（仅 Windows）
        if is_windows:
            reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                             'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                             'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
            name_without_ext = os.path.splitext(cleaned)[0]
            if name_without_ext.upper() in reserved_names:
                cleaned = '_' + cleaned
        
        cleaned_parts.append(cleaned)
    
    # 重新组合路径
    joined = '/'.join(cleaned_parts)

    if drive:
        result = drive + '/' + joined if joined else drive + '/'
    elif had_leading_slash:
        result = '/' + joined if joined else '/'
    else:
        result = joined
    
    # 转换回系统对应的路径分隔符
    return result.replace('/', os.sep)


def run_download_task_rust(task: DownloadTask) -> None:
    """
    使用 Rust 下载器执行下载任务
    
    Args:
        task: 下载任务，包含 id/album_ids/photo_ids/config
    """
    task_id: int = task["id"]
    album_ids: List[str] = task.get("album_ids", [])
    photo_ids: List[str] = task.get("photo_ids", [])
    config: Dict[str, Any] = task.get("config", {})
    
    # 检查是否启用 Rust 下载器
    use_rust = config.get("use_rust_downloader", True)
    
    try:
        from server.utils.rust_downloader import is_rust_downloader_available
        
        if not use_rust or not is_rust_downloader_available():
            add_log(task_id, "info", "Rust 下载器不可用，使用 Python 下载器")
            from server.services.download_service import run_download_task
            return run_download_task(task)
        
        task["status"] = "running"
        task["start_time"] = datetime.now().isoformat()
        add_log(task_id, "info", f"开始下载任务（使用 Rust 下载器），本子数量: {len(album_ids)}, 章节数量: {len(photo_ids)}")
        
        from jmcomic import create_option, DirRule, fix_suffix, mkdir_if_not_exists, download_album, download_photo
        from jmcomic.jm_downloader import JmDownloader
        from server.utils.jmcomic_helper import setup_jmcomic_env, TempConfigFile
        from server.utils.rust_downloader import download_images_with_rust, ImageTask
        
        # 配置环境变量
        download_dir = config.get("download_dir", "./download/")
        setup_jmcomic_env(
            username=config.get("username", ""),
            password=config.get("password", ""),
            download_dir=download_dir
        )
        
        mkdir_if_not_exists(download_dir)
        
        # 使用临时配置文件
        with TempConfigFile("local_download.yml", {"plugins": None}) as temp_config:
            option = create_option(temp_config)
            
            if config.get("dir_rule"):
                option.dir_rule = DirRule(config["dir_rule"], base_dir=download_dir)
            if config.get("client_impl"):
                option.client.impl = config["client_impl"]
            if config.get("image_suffix"):
                option.download.image.suffix = fix_suffix(config["image_suffix"])
            
            add_log(task_id, "info", "正在获取图片列表...")
            task["progress"] = 5
            
            # 收集所有图片任务
            all_image_tasks = []
            collected_images = []
            
            # 自定义下载器来拦截图片信息
            class CollectorDownloader(JmDownloader):
                def __init__(self, option):
                    super().__init__(option)
                
                def download_by_image_detail(self, image):
                    """拦截图片信息，不实际下载"""
                    img_save_path = self.option.decide_image_filepath(image)
                    image.save_path = img_save_path
                    from jmcomic.jm_toolkit import file_exists
                    image.exists = file_exists(img_save_path)
                    
                    # 收集图片信息
                    collected_images.append(image)
                    
                    # 调用回调
                    self.before_image(image, img_save_path)
                    if not image.skip and not image.exists:
                        self.after_image(image, img_save_path)
            
            # 使用自定义下载器收集图片信息
            add_log(task_id, "info", "解析本子和章节信息...")
            
            # 下载 albums
            for idx, album_id in enumerate(album_ids):
                try:
                    add_log(task_id, "info", f"解析本子 {album_id} ({idx+1}/{len(album_ids)})...")
                    download_album(album_id, option, CollectorDownloader, check_exception=False)
                except Exception as e:
                    add_log(task_id, "error", f"解析本子 {album_id} 失败: {str(e)}")
            
            # 下载 photos
            for idx, photo_id in enumerate(photo_ids):
                try:
                    add_log(task_id, "info", f"解析章节 {photo_id} ({idx+1}/{len(photo_ids)})...")
                    download_photo(photo_id, option, CollectorDownloader, check_exception=False)
                except Exception as e:
                    add_log(task_id, "error", f"解析章节 {photo_id} 失败: {str(e)}")
            
            add_log(task_id, "info", f"解析完成，共收集到 {len(collected_images)} 张图片信息")
            
            # 转换为 Rust 下载任务
            path_cleaned_count = 0
            skipped_existing = 0
            for img_detail in collected_images:
                # 清理路径中的非法字符和过长的名称
                original_path = img_detail.save_path
                img_path = sanitize_path(original_path)
                
                # 记录路径清理情况
                if img_path != original_path:
                    path_cleaned_count += 1
                
                # 检查图片是否已存在（使用 img_detail.exists 而不是 os.path.exists）
                if hasattr(img_detail, 'exists') and img_detail.exists:
                    skipped_existing += 1
                    continue
                
                # 检查 download_url 是否存在
                if not hasattr(img_detail, 'download_url') or not img_detail.download_url:
                    add_log(task_id, "warning", f"图片缺少 download_url: {img_path}")
                    continue
                
                # 构建请求头 - 使用 img_detail 中的下载 URL（已包含必要的参数）
                headers = {"User-Agent": "Mozilla/5.0"}
                
                # 获取 scramble_id（如果存在）
                scramble_id = None
                if hasattr(img_detail, 'scramble_id') and img_detail.scramble_id:
                    try:
                        scramble_id = int(img_detail.scramble_id)
                    except (ValueError, TypeError):
                        pass
                
                all_image_tasks.append(ImageTask(
                    url=img_detail.download_url,  # 使用 download_url 而不是 img_url
                    path=img_path,
                    headers=headers,
                    scramble_id=scramble_id
                ))
            
            # 记录统计信息
            if path_cleaned_count > 0:
                add_log(task_id, "info", f"已清理 {path_cleaned_count} 个路径（移除非法字符或截断过长名称）")
            if skipped_existing > 0:
                add_log(task_id, "info", f"跳过 {skipped_existing} 张已存在的图片")
            
            if not all_image_tasks:
                add_log(task_id, "info", "所有图片已存在，无需下载")
                task["status"] = "completed"
                task["progress"] = 100
                task["end_time"] = datetime.now().isoformat()
                
                # 持久化手动任务和日志
                if not task.get('auto_task_id'):
                    from server.utils.storage import save_manual_tasks
                    from server.utils.logs import save_logs
                    from server.state import tasks as all_tasks
                    save_manual_tasks(all_tasks)
                    save_logs()  # 保存日志
                
                return
            
            add_log(task_id, "info", f"共需下载 {len(all_image_tasks)} 张图片")
            add_log(task_id, "info", "=" * 60)
            add_log(task_id, "info", "⏳ 准备调用 Rust 高性能下载器...")
            add_log(task_id, "info", "📂 所有目录已创建完毕")
            add_log(task_id, "info", "🚀 即将开始并发下载图片，请耐心等待...")
            add_log(task_id, "info", "=" * 60)
            
            # 记录前 3 个下载任务用于调试
            for i, img_task in enumerate(all_image_tasks[:3]):
                add_log(task_id, "debug", f"示例任务 {i+1}: URL={img_task.url[:80]}..., 路径={img_task.path}")
            task["progress"] = 10
            
            # 定义进度回调
            def progress_callback(progress_data):
                completed = progress_data.get("completed", 0)
                total = progress_data.get("total", len(all_image_tasks))
                failed = progress_data.get("failed", 0)
                
                # 更新进度 (10% ~ 95%)
                task["progress"] = 10 + int((completed / total) * 85)
                
                # 定期输出日志
                if completed % 10 == 0:
                    add_log(task_id, "info", f"下载进度: {completed}/{total} (失败: {failed})")
            
            # 使用 Rust 下载器下载
            concurrent = config.get("concurrent", 50)
            retry = config.get("retry_count", 3)
            timeout = config.get("timeout", 30)
            
            add_log(task_id, "info", f"▶️ 正在启动 Rust 下载器...")
            add_log(task_id, "info", f"   配置: 并发={concurrent}, 重试={retry}次, 超时={timeout}秒")
            
            import time
            start_time = time.time()
            
            result = download_images_with_rust(
                images=all_image_tasks,
                concurrent=concurrent,
                retry=retry,
                timeout=timeout,
                progress_callback=progress_callback
            )
            
            elapsed = time.time() - start_time
            add_log(task_id, "info", f"⏱️ Rust 下载器执行完毕，耗时: {elapsed:.1f}秒")
            
            # 处理结果
            task["progress"] = 100
            task["end_time"] = datetime.now().isoformat()
            
            add_log(task_id, "info", "=" * 60)
            if result.failed == 0:
                add_log(task_id, "success", f"✅ 全部下载完成！")
                add_log(task_id, "success", f"   成功: {result.success} 张")
                add_log(task_id, "success", f"   失败: 0 张")
                
                # 执行PDF生成（如果启用）
                pdf_config = config.get('pdf', {})
                if pdf_config.get('enabled', False):
                    add_log(task_id, "info", "📄 开始生成PDF...")
                    from server.services.pdf_service import generate_task_pdfs
                    pdf_result = generate_task_pdfs(task_id, download_dir, pdf_config)
                    if pdf_result['success']:
                        add_log(task_id, "success", f"✅ PDF生成完成: {pdf_result['message']}")
                    else:
                        add_log(task_id, "warning", f"⚠️ PDF生成失败: {pdf_result['message']}")
                
                # 执行压缩（如果启用）
                compression_config = config.get('compression', {})
                if compression_config.get('enabled', False):
                    add_log(task_id, "info", "🗜️ 开始压缩文件...")
                    from server.services.compression_service import compress_task_downloads
                    compress_result = compress_task_downloads(task_id, download_dir, compression_config)
                    if compress_result['success']:
                        add_log(task_id, "success", f"✅ 压缩完成: {compress_result['message']}")
                    else:
                        add_log(task_id, "warning", f"⚠️ 压缩失败: {compress_result['message']}")
                
                task["status"] = "completed"
                
                # 持久化手动任务和日志
                if not task.get('auto_task_id'):
                    from server.utils.storage import save_manual_tasks
                    from server.utils.logs import save_logs
                    from server.state import tasks as all_tasks
                    save_manual_tasks(all_tasks)
                    save_logs()  # 保存日志
            elif result.success > 0:
                task["status"] = "partial_success"
                task["failed_images"] = result.failed_urls
                task["error"] = f"部分图片下载失败（{result.failed}/{result.success + result.failed}）"
                add_log(task_id, "warning", f"⚠️ 下载部分成功")
                add_log(task_id, "warning", f"   成功: {result.success} 张")
                add_log(task_id, "warning", f"   失败: {result.failed} 张")
                
                # 执行PDF生成（如果启用）
                pdf_config = config.get('pdf', {})
                if pdf_config.get('enabled', False):
                    add_log(task_id, "info", "📄 开始生成PDF（基于已下载的图片）...")
                    from server.services.pdf_service import generate_task_pdfs
                    pdf_result = generate_task_pdfs(task_id, download_dir, pdf_config)
                    if pdf_result['success']:
                        add_log(task_id, "success", f"✅ PDF生成完成: {pdf_result['message']}")
                    else:
                        add_log(task_id, "warning", f"⚠️ PDF生成失败: {pdf_result['message']}")
                
                # 执行压缩（如果启用）
                compression_config = config.get('compression', {})
                if compression_config.get('enabled', False):
                    add_log(task_id, "info", "🗜️ 开始压缩文件（基于已下载的图片）...")
                    from server.services.compression_service import compress_task_downloads
                    compress_result = compress_task_downloads(task_id, download_dir, compression_config)
                    if compress_result['success']:
                        add_log(task_id, "success", f"✅ 压缩完成: {compress_result['message']}")
                    else:
                        add_log(task_id, "warning", f"⚠️ 压缩失败: {compress_result['message']}")
                
                # 持久化手动任务和日志
                if not task.get('auto_task_id'):
                    from server.utils.storage import save_manual_tasks
                    from server.utils.logs import save_logs
                    from server.state import tasks as all_tasks
                    save_manual_tasks(all_tasks)
                    save_logs()  # 保存日志
            else:
                task["status"] = "failed"
                task["failed_images"] = result.failed_urls
                task["error"] = f"所有图片下载失败（{result.failed}张）"
                add_log(task_id, "error", f"❌ 下载失败！")
                add_log(task_id, "error", f"   失败: {result.failed} 张")
                
                # 持久化手动任务和日志
                if not task.get('auto_task_id'):
                    from server.utils.storage import save_manual_tasks
                    from server.utils.logs import save_logs
                    from server.state import tasks as all_tasks
                    save_manual_tasks(all_tasks)
                    save_logs()  # 保存日志
            
            add_log(task_id, "info", f"📁 文件保存在: {os.path.abspath(download_dir)}")
            add_log(task_id, "info", "=" * 60)
    
    except Exception as e:
        import traceback
        
        task["status"] = "failed"
        task["error"] = str(e)
        task["end_time"] = datetime.now().isoformat()
        add_log(task_id, "error", f"下载失败: {str(e)}")
        traceback.print_exc()
        
        # 持久化手动任务和日志
        if not task.get('auto_task_id'):
            from server.utils.storage import save_manual_tasks
            from server.utils.logs import save_logs
            from server.state import tasks as all_tasks
            save_manual_tasks(all_tasks)
            save_logs()  # 保存日志


__all__ = ["run_download_task_rust"]

