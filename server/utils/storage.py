"""
持久化存储工具。
负责自动化任务、执行记录、手动任务的加载与原子写入。
"""

import json
import os
import tempfile
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict

from server.state import normalize_auto_task_state
from server.utils.logs import add_log

DATA_DIR = 'data'
AUTO_TASKS_FILE = os.path.join(DATA_DIR, 'auto_tasks.json')
AUTO_EXECUTIONS_FILE = os.path.join(DATA_DIR, 'auto_executions.json')
MANUAL_TASKS_FILE = os.path.join(DATA_DIR, 'manual_tasks.json')
MAX_EXECUTIONS_PER_TASK = 10
MAX_MANUAL_TASKS = 10
_lock = threading.RLock()


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _atomic_write_json(file_path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(file_path) or '.'
    fd, temp_path = tempfile.mkstemp(prefix='.tmp-', suffix='.json', dir=directory)

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, file_path)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        finally:
            raise


def _load_json_file(file_path: str, default: Any, label: str) -> Any:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        add_log(0, 'error', f'[{label}] 加载失败: {str(e)}')
        return default


def load_auto_tasks() -> Dict[int, Dict[str, Any]]:
    """从磁盘加载自动化任务。返回 id->task 字典。"""
    with _lock:
        data = _load_json_file(AUTO_TASKS_FILE, {}, '自动化任务')

    if isinstance(data, dict) and 'tasks' in data:
        task_list = data.get('tasks', [])
    else:
        task_list = data if isinstance(data, list) else []

    result: Dict[int, Dict[str, Any]] = {}
    for task in task_list:
        try:
            normalized = _migrate_auto_task_schema(task)
            task_id = int(normalized.get('id'))
            result[task_id] = normalize_auto_task_state(normalized)
        except Exception:
            continue
    return result


def _migrate_auto_task_schema(task: Dict[str, Any]) -> Dict[str, Any]:
    migrated = deepcopy(task)

    if 'batch_size' in migrated and 'batch_albums_count' not in migrated:
        migrated['batch_albums_count'] = migrated['batch_size']
        migrated['batch_interval_minutes'] = 30
        migrated.pop('batch_size', None)

    return migrated


def save_auto_tasks(auto_tasks: Dict[int, Dict[str, Any]]) -> None:
    """将自动化任务写入磁盘。"""
    _ensure_data_dir()

    with _lock:
        tasks_list = [normalize_auto_task_state(deepcopy(task)) for task in auto_tasks.values()]
        payload = {
            'version': 2,
            'updated_at': datetime.now().isoformat(),
            'tasks': tasks_list,
        }
        _atomic_write_json(AUTO_TASKS_FILE, payload)


def load_auto_executions() -> Dict[int, Dict[str, Any]]:
    """从磁盘加载执行记录。返回 id->execution 字典。"""
    with _lock:
        data = _load_json_file(AUTO_EXECUTIONS_FILE, {}, '自动化执行记录')

    if not isinstance(data, dict) or 'executions' not in data:
        return {}

    result: Dict[int, Dict[str, Any]] = {}
    for execution in data.get('executions', []):
        try:
            execution_id = int(execution.get('id'))
            result[execution_id] = execution
        except Exception:
            continue
    return result


def save_auto_execution(execution: Dict[str, Any]) -> None:
    """保存单条执行记录并裁剪历史。"""
    _ensure_data_dir()

    with _lock:
        data = _load_json_file(AUTO_EXECUTIONS_FILE, {'executions': []}, '自动化执行记录')
        executions = data.get('executions', []) if isinstance(data, dict) else []

        by_task: Dict[int, list] = {}
        for item in executions:
            task_id = item.get('auto_task_id')
            if task_id is None:
                continue
            by_task.setdefault(task_id, []).append(item)

        task_id = execution.get('auto_task_id')
        if task_id is not None:
            by_task.setdefault(task_id, [])
            by_task[task_id] = [item for item in by_task[task_id] if item.get('id') != execution.get('id')]
            by_task[task_id].append(execution)
            by_task[task_id].sort(key=lambda x: x.get('start_time', ''), reverse=True)
            by_task[task_id] = by_task[task_id][:MAX_EXECUTIONS_PER_TASK]

        all_executions = []
        for task_execs in by_task.values():
            all_executions.extend(task_execs)

        all_executions.sort(key=lambda x: x.get('id', 0), reverse=True)
        payload = {
            'version': 1,
            'updated_at': datetime.now().isoformat(),
            'executions': all_executions,
        }
        _atomic_write_json(AUTO_EXECUTIONS_FILE, payload)


def save_all_auto_executions(executions: Dict[int, Dict[str, Any]]) -> None:
    """保存所有执行记录（用于删除等全量更新）。"""
    _ensure_data_dir()

    with _lock:
        all_executions = list(executions.values())
        all_executions.sort(key=lambda x: x.get('id', 0), reverse=True)

        payload = {
            'version': 1,
            'updated_at': datetime.now().isoformat(),
            'executions': all_executions,
        }
        _atomic_write_json(AUTO_EXECUTIONS_FILE, payload)


def load_manual_tasks() -> Dict[int, Dict[str, Any]]:
    """从磁盘加载手动任务。返回 id->task 字典。"""
    with _lock:
        data = _load_json_file(MANUAL_TASKS_FILE, {}, '手动任务')

    if not isinstance(data, dict) or 'tasks' not in data:
        return {}

    result: Dict[int, Dict[str, Any]] = {}
    for task in data.get('tasks', []):
        try:
            task_id = int(task.get('id'))
            result[task_id] = task
        except Exception:
            continue
    return result


def save_manual_tasks(tasks: Dict[int, Dict[str, Any]]) -> None:
    """保存手动任务，仅保留已结束的最近记录。"""
    _ensure_data_dir()

    with _lock:
        completed_tasks = [
            task
            for task in tasks.values()
            if task.get('status') in {'completed', 'failed', 'partial_success'}
        ]
        completed_tasks.sort(key=lambda x: x.get('create_time', ''), reverse=True)
        completed_tasks = completed_tasks[:MAX_MANUAL_TASKS]

        payload = {
            'version': 1,
            'updated_at': datetime.now().isoformat(),
            'tasks': completed_tasks,
        }
        _atomic_write_json(MANUAL_TASKS_FILE, payload)


__all__ = [
    'load_auto_tasks',
    'save_auto_tasks',
    'load_auto_executions',
    'save_auto_execution',
    'save_all_auto_executions',
    'load_manual_tasks',
    'save_manual_tasks',
    'AUTO_TASKS_FILE',
    'AUTO_EXECUTIONS_FILE',
    'MANUAL_TASKS_FILE',
]
