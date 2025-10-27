import os
import re
from datetime import datetime
from typing import Any, Dict
from server.types import ExportTask

from server.utils import add_log


def run_export_task(task: ExportTask) -> None:
    """执行收藏夹导出任务。task 内应包含 id/username/config。"""
    task_id: int = task["id"]
    username: str = task.get("username", "")
    password: str = task.get("password", "")
    config: Dict[str, Any] = task.get("config", {})

    try:
        task["status"] = "running"
        task["start_time"] = datetime.now().isoformat()
        add_log(task_id, "info", "开始导出收藏夹")

        from jmcomic import create_option
        from server.utils.jmcomic_helper import setup_jmcomic_env, TempConfigFile

        # 配置环境变量
        setup_jmcomic_env(
            username=username,
            password=password,
            zip_password=config.get("zip_password", "")
        )

        save_dir = config.get("save_dir", "./export/")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 压缩文件：若启用压缩且未提供路径，默认在保存目录下生成带时间戳文件
        zip_filepath = config.get("zip_filepath")
        if config.get("zip_enable", False):
            if not zip_filepath:
                zip_filepath = os.path.join(save_dir, f"export_favorites_{ts}.7z")
        else:
            # 未启用压缩时该参数不会生效，但为兼容插件传一个默认值
            zip_filepath = os.path.join(save_dir, f"export_favorites_{ts}.7z")

        # 使用临时配置文件（自动清理）
        modifications = {
            "plugins.main.1.kwargs.save_dir": save_dir,
            "plugins.main.1.kwargs.zip_enable": config.get("zip_enable", False),
            "plugins.main.1.kwargs.zip_filepath": zip_filepath,
        }
        
        with TempConfigFile("local_export_favorites.yml", modifications) as temp_config:
            option = create_option(temp_config)
            option.call_all_plugin("main")

        # 重命名导出的 CSV 文件（添加用户名和时间戳，保留所有历史文件）
        renamed = 0
        try:
            # 清理用户名（移除特殊字符）
            safe_username = re.sub(r'[^\w\-.]', '_', username)
            
            for name in os.listdir(save_dir):
                if name.lower().endswith('.csv'):
                    # 只重命名本次新生成的文件（没有时间戳的原始文件）
                    # 已有时间戳的文件说明是历史文件，不再处理
                    timestamp_pattern = re.compile(r'_\d{8}_\d{6}')
                    if timestamp_pattern.search(name):
                        continue  # 跳过已有时间戳的历史文件
                    
                    base, ext = os.path.splitext(name)
                    
                    # 新文件名格式：原名_用户名_时间戳.csv
                    new_name = f"{base}_{safe_username}_{ts}{ext}"
                    
                    src = os.path.join(save_dir, name)
                    dst = os.path.join(save_dir, new_name)
                    
                    # 如果目标文件已存在（极少情况），添加序号
                    if os.path.exists(dst):
                        counter = 1
                        while os.path.exists(dst):
                            new_name = f"{base}_{safe_username}_{ts}_{counter}{ext}"
                            dst = os.path.join(save_dir, new_name)
                            counter += 1
                    
                    os.replace(src, dst)
                    renamed += 1
        except Exception as e:
            add_log(task_id, "error", f"重命名CSV文件失败: {str(e)}")

        task["status"] = "completed"
        task["progress"] = 100
        task["end_time"] = datetime.now().isoformat()
        
        # 持久化手动任务和日志
        from server.utils.storage import save_manual_tasks
        from server.utils.logs import save_logs
        from server.state import tasks as all_tasks
        save_manual_tasks(all_tasks)
        save_logs()  # 保存日志

        result_info = "导出完成！\n"
        result_info += f"CSV目录: {os.path.abspath(save_dir)}\n"
        if renamed:
            result_info += f"已重命名 CSV: {renamed} 个\n"
        if config.get("zip_enable", False) and os.path.exists(zip_filepath):
            result_info += f"压缩文件: {os.path.abspath(zip_filepath)}"
        add_log(task_id, "success", result_info)
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        task["end_time"] = datetime.now().isoformat()
        add_log(task_id, "error", f"导出失败: {str(e)}")
        
        # 持久化手动任务和日志
        from server.utils.storage import save_manual_tasks
        from server.utils.logs import save_logs
        from server.state import tasks as all_tasks
        save_manual_tasks(all_tasks)
        save_logs()  # 保存日志

__all__ = ["run_export_task"]


