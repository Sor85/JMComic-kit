from threading import Lock
from typing import Any, Dict

tasks: Dict[int, Dict[str, Any]] = {}
_task_id_counter: int = 0
task_lock: Lock = Lock()

auto_tasks: Dict[int, Dict[str, Any]] = {}
_auto_task_id_counter: int = 0
auto_task_lock: Lock = Lock()

auto_executions: Dict[int, Dict[str, Any]] = {}
_auto_execution_id_counter: int = 1000  # 从1000开始，与下载任务ID区分
auto_execution_lock: Lock = Lock()

# 自动化任务停止标志集合（用于在等待期间停止任务）
auto_task_stop_flags: set = set()
auto_task_stop_lock: Lock = Lock()


def get_next_task_id() -> int:
    """线程安全地获取下一个任务ID。"""
    global _task_id_counter
    with task_lock:
        _task_id_counter += 1
        return _task_id_counter


def init_task_counter(max_id: int) -> None:
    """初始化任务ID计数器。"""
    global _task_id_counter
    with task_lock:
        _task_id_counter = max(max_id, _task_id_counter)


def get_next_auto_task_id() -> int:
    """线程安全地获取下一个自动化任务ID。"""
    global _auto_task_id_counter
    with auto_task_lock:
        _auto_task_id_counter += 1
        return _auto_task_id_counter


def init_auto_task_counter(max_id: int) -> None:
    """初始化自动化任务ID计数器。"""
    global _auto_task_id_counter
    with auto_task_lock:
        _auto_task_id_counter = max(max_id, _auto_task_id_counter)


def get_next_auto_execution_id() -> int:
    """线程安全地获取下一个执行记录ID。"""
    global _auto_execution_id_counter
    with auto_execution_lock:
        _auto_execution_id_counter += 1
        return _auto_execution_id_counter


def init_auto_execution_counter(max_id: int) -> None:
    """初始化执行记录ID计数器。"""
    global _auto_execution_id_counter
    with auto_execution_lock:
        _auto_execution_id_counter = max(max_id, _auto_execution_id_counter)


def set_auto_task_stop_flag(auto_task_id: int) -> None:
    """设置自动化任务停止标志。"""
    with auto_task_stop_lock:
        auto_task_stop_flags.add(auto_task_id)


def clear_auto_task_stop_flag(auto_task_id: int) -> None:
    """清除自动化任务停止标志。"""
    with auto_task_stop_lock:
        auto_task_stop_flags.discard(auto_task_id)


def is_auto_task_stopped(auto_task_id: int) -> bool:
    """检查自动化任务是否被停止。"""
    with auto_task_stop_lock:
        return auto_task_id in auto_task_stop_flags


__all__ = [
    "tasks",
    "task_lock",
    "auto_tasks",
    "auto_task_lock",
    "auto_executions",
    "auto_execution_lock",
    "get_next_task_id",
    "init_task_counter",
    "get_next_auto_task_id",
    "get_next_auto_execution_id",
    "init_auto_task_counter",
    "init_auto_execution_counter",
    "set_auto_task_stop_flag",
    "clear_auto_task_stop_flag",
    "is_auto_task_stopped",
]


