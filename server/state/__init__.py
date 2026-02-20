"""
全局运行时状态容器。
集中管理任务内存状态、计数器、并发锁与自动化运行标记。
"""

from copy import deepcopy
from threading import Lock
from typing import Any, Dict, Optional, Set

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
auto_task_stop_flags: Set[int] = set()
auto_task_stop_lock: Lock = Lock()

# 自动化任务运行标志（single-flight）
auto_task_running_ids: Set[int] = set()
auto_task_runtime_lock: Lock = Lock()

AUTO_TASK_DESIRED_ENABLED = 'enabled'
AUTO_TASK_DESIRED_DISABLED = 'disabled'
AUTO_TASK_RUNTIME_IDLE = 'idle'
AUTO_TASK_RUNTIME_SCHEDULED = 'scheduled'
AUTO_TASK_RUNTIME_RUNNING = 'running'
AUTO_TASK_RUNTIME_STOPPING = 'stopping'
AUTO_TASK_RUNTIME_ERROR = 'error'

_AUTO_TASK_DESIRED_SET = {
    AUTO_TASK_DESIRED_ENABLED,
    AUTO_TASK_DESIRED_DISABLED,
}

_AUTO_TASK_RUNTIME_SET = {
    AUTO_TASK_RUNTIME_IDLE,
    AUTO_TASK_RUNTIME_SCHEDULED,
    AUTO_TASK_RUNTIME_RUNNING,
    AUTO_TASK_RUNTIME_STOPPING,
    AUTO_TASK_RUNTIME_ERROR,
}


def _derive_legacy_status(desired_status: str, runtime_status: str) -> str:
    if desired_status == AUTO_TASK_DESIRED_ENABLED:
        return 'running'
    if runtime_status in {
        AUTO_TASK_RUNTIME_SCHEDULED,
        AUTO_TASK_RUNTIME_RUNNING,
        AUTO_TASK_RUNTIME_STOPPING,
    }:
        return 'running'
    return 'stopped'


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


def try_mark_auto_task_running(auto_task_id: int) -> bool:
    """尝试标记自动化任务进入运行态（single-flight）。"""
    with auto_task_runtime_lock:
        if auto_task_id in auto_task_running_ids:
            return False
        auto_task_running_ids.add(auto_task_id)
        return True


def clear_auto_task_running(auto_task_id: int) -> None:
    """清除自动化任务运行标记。"""
    with auto_task_runtime_lock:
        auto_task_running_ids.discard(auto_task_id)


def is_auto_task_running(auto_task_id: int) -> bool:
    """检查自动化任务是否处于运行态。"""
    with auto_task_runtime_lock:
        return auto_task_id in auto_task_running_ids


def normalize_auto_task_state(auto_task: Dict[str, Any]) -> Dict[str, Any]:
    """归一化自动化任务状态字段并返回新对象。"""
    normalized = deepcopy(auto_task)

    desired_status = normalized.get('desired_status')
    runtime_status = normalized.get('runtime_status')
    status = normalized.get('status')

    if desired_status not in _AUTO_TASK_DESIRED_SET:
        desired_status = AUTO_TASK_DESIRED_ENABLED if status == 'running' else AUTO_TASK_DESIRED_DISABLED

    if runtime_status not in _AUTO_TASK_RUNTIME_SET:
        runtime_status = AUTO_TASK_RUNTIME_IDLE

    normalized['desired_status'] = desired_status
    normalized['runtime_status'] = runtime_status
    normalized['status'] = _derive_legacy_status(desired_status, runtime_status)

    if 'current_execution_id' not in normalized:
        normalized['current_execution_id'] = None

    return normalized


def update_auto_task_status(
    auto_task: Dict[str, Any],
    desired_status: Optional[str] = None,
    runtime_status: Optional[str] = None,
    current_execution_id: Optional[int] = None,
) -> Dict[str, Any]:
    """更新自动化任务状态字段并返回同一对象。"""
    resolved_desired_status = auto_task.get('desired_status')
    resolved_runtime_status = auto_task.get('runtime_status')

    if desired_status in _AUTO_TASK_DESIRED_SET:
        auto_task['desired_status'] = desired_status
        resolved_desired_status = desired_status

    if runtime_status in _AUTO_TASK_RUNTIME_SET:
        auto_task['runtime_status'] = runtime_status
        resolved_runtime_status = runtime_status

    if current_execution_id is not None or runtime_status in {
        AUTO_TASK_RUNTIME_IDLE,
        AUTO_TASK_RUNTIME_SCHEDULED,
        AUTO_TASK_RUNTIME_ERROR,
        AUTO_TASK_RUNTIME_STOPPING,
    }:
        auto_task['current_execution_id'] = current_execution_id

    resolved_desired_status = resolved_desired_status or AUTO_TASK_DESIRED_DISABLED
    resolved_runtime_status = resolved_runtime_status or AUTO_TASK_RUNTIME_IDLE
    auto_task['status'] = _derive_legacy_status(resolved_desired_status, resolved_runtime_status)

    return auto_task


__all__ = [
    'tasks',
    'task_lock',
    'auto_tasks',
    'auto_task_lock',
    'auto_executions',
    'auto_execution_lock',
    'get_next_task_id',
    'init_task_counter',
    'get_next_auto_task_id',
    'get_next_auto_execution_id',
    'init_auto_task_counter',
    'init_auto_execution_counter',
    'set_auto_task_stop_flag',
    'clear_auto_task_stop_flag',
    'is_auto_task_stopped',
    'try_mark_auto_task_running',
    'clear_auto_task_running',
    'is_auto_task_running',
    'normalize_auto_task_state',
    'update_auto_task_status',
    'AUTO_TASK_DESIRED_ENABLED',
    'AUTO_TASK_DESIRED_DISABLED',
    'AUTO_TASK_RUNTIME_IDLE',
    'AUTO_TASK_RUNTIME_SCHEDULED',
    'AUTO_TASK_RUNTIME_RUNNING',
    'AUTO_TASK_RUNTIME_STOPPING',
    'AUTO_TASK_RUNTIME_ERROR',
]
