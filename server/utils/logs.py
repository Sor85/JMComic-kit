from datetime import datetime
from typing import Any, Dict, List, Optional
from threading import RLock
import json
import os

# 简单日志存储（内存）
logs: List[Dict[str, Any]] = []
max_logs: int = 1000
_lock = RLock()

# 持久化配置
DATA_DIR = "data"
LOGS_FILE = os.path.join(DATA_DIR, "logs.json")
MAX_LOGS_PER_TASK = 200  # 每个任务保留最新的200条日志

def _ensure_data_dir() -> None:
    """确保数据目录存在。"""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_logs() -> List[Dict[str, Any]]:
    """从磁盘加载日志。返回日志列表。"""
    with _lock:
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return []
        except Exception:
            return []
    
    if not isinstance(data, dict) or "logs" not in data:
        return []
    
    log_list = data.get("logs", [])
    return log_list if isinstance(log_list, list) else []


def save_logs() -> None:
    """将日志持久化到磁盘，按 task_id 分组并裁剪每个任务的历史记录到上限。"""
    _ensure_data_dir()
    with _lock:
        # 按任务ID分组
        by_task: Dict[int, list] = {}
        for log_entry in logs:
            task_id = log_entry.get("task_id")
            if task_id is not None:
                if task_id not in by_task:
                    by_task[task_id] = []
                by_task[task_id].append(log_entry)
        
        # 对每个任务的日志按时间倒序排序，保留最新的记录
        for task_id in by_task:
            by_task[task_id].sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            by_task[task_id] = by_task[task_id][:MAX_LOGS_PER_TASK]
        
        # 重新组合所有日志
        all_logs = []
        for task_logs in by_task.values():
            all_logs.extend(task_logs)
        
        # 按ID倒序排序（最新的在前，与内存结构一致）
        all_logs.sort(key=lambda x: x.get("id", 0), reverse=True)
        
        # 写入磁盘
        with open(LOGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"logs": all_logs}, f, ensure_ascii=False, indent=2)


def add_log(task_id: int, level: str, message: str) -> Dict[str, Any]:
    """添加日志到内存（批量保存以提高性能）"""
    with _lock:
        entry: Dict[str, Any] = {
            "id": len(logs) + 1,
            "task_id": task_id,
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        logs.insert(0, entry)
        if len(logs) > max_logs:
            del logs[max_logs:]
        
        return entry

def get_logs(task_id: Optional[int] = None, level: str = "all", limit: int = 100) -> List[Dict[str, Any]]:
    with _lock:
        filtered = logs
        if task_id is not None:
            filtered = [log for log in filtered if log["task_id"] == task_id]
        if level != "all":
            filtered = [log for log in filtered if log["level"] == level]
        return filtered[:limit]

def clear_logs() -> None:
    with _lock:
        logs.clear()


def delete_task_logs(task_id: int) -> None:
    """删除指定任务的所有日志"""
    with _lock:
        # 从内存中删除
        logs[:] = [log for log in logs if log.get("task_id") != task_id]
        
        # 持久化到磁盘
        try:
            save_logs()
        except Exception as e:
            print(f"警告: 日志持久化失败: {str(e)}")


__all__ = ["add_log", "get_logs", "clear_logs", "delete_task_logs", "load_logs", "save_logs", "logs", "max_logs"]


