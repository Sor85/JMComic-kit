import json
import os
import threading
from typing import Dict, Any


DATA_DIR = "data"
AUTO_TASKS_FILE = os.path.join(DATA_DIR, "auto_tasks.json")
AUTO_EXECUTIONS_FILE = os.path.join(DATA_DIR, "auto_executions.json")
MANUAL_TASKS_FILE = os.path.join(DATA_DIR, "manual_tasks.json")
MAX_EXECUTIONS_PER_TASK = 10  # 每个任务保留最近10条执行记录
MAX_MANUAL_TASKS = 10  # 最多保留10个手动任务
_lock = threading.RLock()


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def load_auto_tasks() -> Dict[int, Dict[str, Any]]:
    """从磁盘加载自动化任务。返回 id->task 的字典。"""
    with _lock:
        try:
            with open(AUTO_TASKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except Exception:
            return {}

    if isinstance(data, dict) and "tasks" in data:
        tasks = data.get("tasks", [])
    else:
        tasks = data if isinstance(data, list) else []

    result: Dict[int, Dict[str, Any]] = {}
    for t in tasks:
        try:
            tid = int(t.get("id"))
            
            # 数据迁移：将旧的 batch_size 转换为新字段
            if 'batch_size' in t and 'batch_albums_count' not in t:
                t['batch_albums_count'] = t['batch_size']
                t['batch_interval_minutes'] = 30  # 默认间隔30分钟
                # 移除旧字段
                del t['batch_size']
            
            result[tid] = t
        except Exception:
            continue
    return result


def save_auto_tasks(auto_tasks: Dict[int, Dict[str, Any]]) -> None:
    """将自动化任务写入磁盘。"""
    _ensure_data_dir()
    tasks_list = list(auto_tasks.values())
    with _lock:
        with open(AUTO_TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump({"tasks": tasks_list}, f, ensure_ascii=False, indent=2)


def load_auto_executions() -> Dict[int, Dict[str, Any]]:
    """从磁盘加载执行记录。返回 id->execution 的字典。"""
    with _lock:
        try:
            with open(AUTO_EXECUTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
    
    if not isinstance(data, dict) or "executions" not in data:
        return {}
    
    executions = data.get("executions", [])
    result: Dict[int, Dict[str, Any]] = {}
    for ex in executions:
        try:
            eid = int(ex.get("id"))
            result[eid] = ex
        except Exception:
            continue
    return result


def save_auto_execution(execution: Dict[str, Any]) -> None:
    """保存单条执行记录。会加载现有记录，追加新记录，并裁剪每个任务的历史记录到上限。"""
    _ensure_data_dir()
    with _lock:
        # 加载现有记录
        try:
            with open(AUTO_EXECUTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            executions = data.get("executions", []) if isinstance(data, dict) else []
        except FileNotFoundError:
            executions = []
        except Exception:
            executions = []
        
        # 按任务ID分组
        by_task: Dict[int, list] = {}
        for ex in executions:
            task_id = ex.get("auto_task_id")
            if task_id is not None:
                if task_id not in by_task:
                    by_task[task_id] = []
                by_task[task_id].append(ex)
        
        # 添加新记录到对应任务分组
        new_task_id = execution.get("auto_task_id")
        if new_task_id is not None:
            if new_task_id not in by_task:
                by_task[new_task_id] = []
            # 移除旧记录（如果已存在相同ID）
            by_task[new_task_id] = [ex for ex in by_task[new_task_id] if ex.get("id") != execution.get("id")]
            by_task[new_task_id].append(execution)
            # 按时间倒序排序，保留最近的记录
            by_task[new_task_id].sort(key=lambda x: x.get("start_time", ""), reverse=True)
            by_task[new_task_id] = by_task[new_task_id][:MAX_EXECUTIONS_PER_TASK]
        
        # 重新组合所有记录
        all_executions = []
        for task_execs in by_task.values():
            all_executions.extend(task_execs)
        
        # 按ID倒序排序（最新的在前）
        all_executions.sort(key=lambda x: x.get("id", 0), reverse=True)
        
        # 写入磁盘
        with open(AUTO_EXECUTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({"executions": all_executions}, f, ensure_ascii=False, indent=2)


def save_all_auto_executions(executions: Dict[int, Dict[str, Any]]) -> None:
    """保存所有执行记录到磁盘（用于删除操作）"""
    _ensure_data_dir()
    with _lock:
        # 转换为列表
        all_executions = list(executions.values())
        
        # 按ID倒序排序（最新的在前）
        all_executions.sort(key=lambda x: x.get("id", 0), reverse=True)
        
        # 写入磁盘
        with open(AUTO_EXECUTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({"executions": all_executions}, f, ensure_ascii=False, indent=2)


def load_manual_tasks() -> Dict[int, Dict[str, Any]]:
    """从磁盘加载手动任务。返回 id->task 的字典。"""
    with _lock:
        try:
            with open(MANUAL_TASKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
    
    if not isinstance(data, dict) or "tasks" not in data:
        return {}
    
    tasks = data.get("tasks", [])
    result: Dict[int, Dict[str, Any]] = {}
    for task in tasks:
        try:
            tid = int(task.get("id"))
            result[tid] = task
        except Exception:
            continue
    return result


def save_manual_tasks(tasks: Dict[int, Dict[str, Any]]) -> None:
    """保存手动任务到磁盘，只保留已完成/失败的任务（最近MAX_MANUAL_TASKS个）"""
    _ensure_data_dir()
    with _lock:
        # 只保留已完成或失败的任务
        completed_tasks = [
            task for task in tasks.values()
            if task.get('status') in ['completed', 'failed', 'partial_success']
        ]
        
        # 按创建时间倒序排序，保留最新的
        completed_tasks.sort(key=lambda x: x.get("create_time", ""), reverse=True)
        completed_tasks = completed_tasks[:MAX_MANUAL_TASKS]
        
        # 写入磁盘
        with open(MANUAL_TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump({"tasks": completed_tasks}, f, ensure_ascii=False, indent=2)


__all__ = [
    "load_auto_tasks", 
    "save_auto_tasks", 
    "load_auto_executions",
    "save_auto_execution",
    "save_all_auto_executions",
    "load_manual_tasks",
    "save_manual_tasks",
    "AUTO_TASKS_FILE",
    "AUTO_EXECUTIONS_FILE",
    "MANUAL_TASKS_FILE",
]


