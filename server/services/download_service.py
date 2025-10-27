import os
import io
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
from server.types import DownloadTask

from server.utils import add_log


def retry_failed_images(
    task_id: int,
    failed_images_with_errors: List[Tuple[Any, Exception]],
    option: Any,
    client: Any,
    retry_count: int = 3,
    initial_delay: int = 5,
    use_backoff: bool = True,
) -> Tuple[int, int, List[str]]:
    """
    重试失败的图片下载
    
    返回: (成功数量, 失败数量, 失败图片URL列表)
    """
    if not failed_images_with_errors:
        return 0, 0, []
    
    success_count = 0
    still_failed = []
    
    add_log(task_id, "warning", f"检测到 {len(failed_images_with_errors)} 张图片下载失败，准备重试...")
    
    for attempt in range(1, retry_count + 1):
        if not failed_images_with_errors:
            break
            
        delay = initial_delay * (attempt if use_backoff else 1)
        add_log(task_id, "info", f"第 {attempt}/{retry_count} 次重试，等待 {delay} 秒...")
        time.sleep(delay)
        
        retry_batch = failed_images_with_errors.copy()
        failed_images_with_errors = []
        
        for img_detail, error in retry_batch:
            try:
                add_log(task_id, "info", f"重试下载: {img_detail.img_url}")
                
                # 重新下载图片
                client.download_by_image_detail(
                    img_detail,
                    option.dir_rule.get_image_dir(img_detail),
                    option.download.image.suffix,
                )
                success_count += 1
                add_log(task_id, "success", f"重试成功: {img_detail.img_url}")
                
            except Exception as retry_error:
                add_log(task_id, "error", f"重试失败: {img_detail.img_url} - {str(retry_error)}")
                failed_images_with_errors.append((img_detail, retry_error))
    
    # 收集最终失败的图片URL
    for img_detail, error in failed_images_with_errors:
        still_failed.append(img_detail.img_url)
    
    fail_count = len(still_failed)
    
    if success_count > 0:
        add_log(task_id, "success", f"重试完成: 成功 {success_count} 张，失败 {fail_count} 张")
    else:
        add_log(task_id, "error", f"重试全部失败: {fail_count} 张图片无法下载")
    
    return success_count, fail_count, still_failed


def run_download_task(task: DownloadTask) -> None:
    """执行下载任务。task 内应包含 id/album_ids/photo_ids/config。"""
    task_id: int = task["id"]
    album_ids: List[str] = task.get("album_ids", [])
    photo_ids: List[str] = task.get("photo_ids", [])
    config: Dict[str, Any] = task.get("config", {})

    try:
        task["status"] = "running"
        task["start_time"] = datetime.now().isoformat()
        add_log(task_id, "info", f"开始下载任务，本子数量: {len(album_ids)}, 章节数量: {len(photo_ids)}")

        from jmcomic import create_option, DirRule, fix_suffix, mkdir_if_not_exists
        from jmcomic.cl import JmcomicUI
        from server.utils.jmcomic_helper import setup_jmcomic_env, TempConfigFile
        import sys

        # 配置环境变量
        download_dir = config.get("download_dir", "./download/")
        setup_jmcomic_env(
            username=config.get("username", ""),
            password=config.get("password", ""),
            download_dir=download_dir
        )

        mkdir_if_not_exists(download_dir)

        # 使用临时配置文件（自动清理）
        with TempConfigFile("local_download.yml", {"plugins": None}) as temp_config:
            option = create_option(temp_config)

            if config.get("dir_rule"):
                option.dir_rule = DirRule(config["dir_rule"], base_dir=download_dir)
            if config.get("client_impl"):
                option.client.impl = config["client_impl"]
            if config.get("image_suffix"):
                option.download.image.suffix = fix_suffix(config["image_suffix"])

            speed_limit = config.get("speed_limit", 0)
            if speed_limit > 0:
                option.download.image.speed_limit = speed_limit * 1024
                add_log(task_id, "info", f"已设置速度限制: {speed_limit} KB/s")

            helper = JmcomicUI()
            helper.album_id_list = album_ids
            helper.photo_id_list = photo_ids

            add_log(task_id, "info", "正在下载...")
            task["progress"] = 10

            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            try:
                helper.run(option)
            finally:
                sys.stdout = old_stdout
                output = captured_output.getvalue()

                exist_count = 0
                download_count = 0
                for line in output.split("\n"):
                    if (
                        "image.exist" in line
                        or "图片已存在" in line
                        or "exist" in line.lower()
                    ):
                        exist_count += 1
                    if "image.after" in line or "图片下载完成" in line:
                        download_count += 1

                if exist_count > 0:
                    add_log(task_id, "info", f"跳过已存在的图片: {exist_count} 张")
                if download_count > 0:
                    add_log(task_id, "info", f"新下载的图片: {download_count} 张")

        add_log(task_id, "success", f"下载完成！文件保存在: {os.path.abspath(download_dir)}")
        
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
        task["progress"] = 100
        task["end_time"] = datetime.now().isoformat()
        
        # 持久化手动任务和日志
        if not task.get('auto_task_id'):
            from server.utils.storage import save_manual_tasks
            from server.utils.logs import save_logs
            from server.state import tasks as all_tasks
            save_manual_tasks(all_tasks)
            save_logs()  # 保存日志
        
    except Exception as e:
        import traceback
        
        # 检查是否为部分下载失败
        from jmcomic.jm_exception import PartialDownloadFailedException
        
        if isinstance(e, PartialDownloadFailedException):
            add_log(task_id, "warning", f"部分图片下载失败，尝试自动重试...")
            
            # 提取失败的图片信息
            failed_images_with_errors = getattr(e, 'fail_list', [])
            
            if failed_images_with_errors:
                # 获取重试配置
                retry_count = config.get("retry_count", 3)
                retry_delay = config.get("retry_delay", 5)
                retry_backoff = config.get("retry_backoff", True)
                
                # 执行重试
                # 使用 option 中的客户端实例
                client = option.client
                
                success_count, fail_count, failed_urls = retry_failed_images(
                    task_id=task_id,
                    failed_images_with_errors=failed_images_with_errors,
                    option=option,
                    client=client,
                    retry_count=retry_count,
                    initial_delay=retry_delay,
                    use_backoff=retry_backoff,
                )
                
                # 更新任务状态
                task["retry_count"] = retry_count
                if fail_count == 0:
                    # 重试后全部成功
                    add_log(task_id, "success", f"重试成功！所有图片已下载完成")
                    
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
                    task["progress"] = 100
                    
                    # 持久化手动任务和日志
                    if not task.get('auto_task_id'):
                        from server.utils.storage import save_manual_tasks
                        from server.utils.logs import save_logs
                        from server.state import tasks as all_tasks
                        save_manual_tasks(all_tasks)
                        save_logs()  # 保存日志
                elif fail_count < len(failed_images_with_errors):
                    # 部分重试成功
                    task["status"] = "partial_success"
                    task["progress"] = 95
                    task["failed_images"] = failed_urls
                    task["error"] = f"部分图片下载失败（{fail_count}/{len(failed_images_with_errors)}）"
                    add_log(task_id, "warning", f"下载部分成功！{fail_count} 张图片无法下载")
                    
                    # 持久化手动任务和日志
                    if not task.get('auto_task_id'):
                        from server.utils.storage import save_manual_tasks
                        from server.utils.logs import save_logs
                        from server.state import tasks as all_tasks
                        save_manual_tasks(all_tasks)
                        save_logs()  # 保存日志
                else:
                    # 重试后仍全部失败
                    task["status"] = "failed"
                    task["failed_images"] = failed_urls
                    task["error"] = f"所有失败图片重试后仍无法下载（{fail_count}张）"
                    add_log(task_id, "error", f"下载失败！{fail_count} 张图片无法下载")
                    
                    # 持久化手动任务和日志
                    if not task.get('auto_task_id'):
                        from server.utils.storage import save_manual_tasks
                        from server.utils.logs import save_logs
                        from server.state import tasks as all_tasks
                        save_manual_tasks(all_tasks)
                        save_logs()  # 保存日志
            else:
                task["status"] = "failed"
                task["error"] = str(e)
                add_log(task_id, "error", f"下载失败: {str(e)}")
                
                # 持久化手动任务和日志
                if not task.get('auto_task_id'):
                    from server.utils.storage import save_manual_tasks
                    from server.utils.logs import save_logs
                    from server.state import tasks as all_tasks
                    save_manual_tasks(all_tasks)
                    save_logs()  # 保存日志
        else:
            # 其他异常
            task["status"] = "failed"
            task["error"] = str(e)
            add_log(task_id, "error", f"下载失败: {str(e)}")
            traceback.print_exc()
            
                    # 持久化手动任务和日志
                    if not task.get('auto_task_id'):
                        from server.utils.storage import save_manual_tasks
                        from server.utils.logs import save_logs
                        from server.state import tasks as all_tasks
                        save_manual_tasks(all_tasks)
                        save_logs()  # 保存日志
        
        task["end_time"] = datetime.now().isoformat()

__all__ = ["run_download_task"]


