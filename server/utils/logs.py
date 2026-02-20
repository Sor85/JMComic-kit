"""
日志存储工具。
负责内存日志管理、容量收敛与持久化。
"""

import json
import logging
import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

logs: List[Dict[str, Any]] = []
max_logs: int = 1000
_lock = RLock()
_logger = logging.getLogger(__name__)

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


DATA_DIR = 'data'
LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
LOGS_WAL_FILE = os.path.join(DATA_DIR, 'logs.wal.jsonl')
MAX_LOGS_PER_TASK = _env_int('MAX_LOGS_PER_TASK', 200)
MAX_LOGS_ON_DISK = _env_int('MAX_LOGS_ON_DISK', 20000)
WAL_COMPACT_BATCH_SIZE = _env_int('WAL_COMPACT_BATCH_SIZE', 100)

_last_log_id: Optional[int] = None
_pending_wal_entries = 0


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


def _atomic_write_text(file_path: str, content: str = '') -> None:
    directory = os.path.dirname(file_path) or '.'
    fd, temp_path = tempfile.mkstemp(prefix='.tmp-', suffix='.log', dir=directory)

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, file_path)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        finally:
            raise


@contextmanager
def _exclusive_file_lock() -> None:
    lock_path = os.path.join(DATA_DIR, '.logs.lock')
    os.makedirs(os.path.dirname(lock_path) or '.', exist_ok=True)

    with open(lock_path, 'a+', encoding='utf-8') as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _load_logs_from_disk_snapshot() -> List[Dict[str, Any]]:
    try:
        with open(LOGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        raise RuntimeError(f'加载日志快照失败: {str(e)}') from e

    if not isinstance(data, dict):
        return []

    log_list = data.get('logs', [])
    return log_list if isinstance(log_list, list) else []


def _load_wal_logs() -> List[Dict[str, Any]]:
    try:
        with open(LOGS_WAL_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    except Exception as e:
        raise RuntimeError(f'加载日志增量文件失败: {str(e)}') from e

    wal_logs: List[Dict[str, Any]] = []
    for line_no, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            _logger.warning('日志增量文件第 %s 行格式错误，已跳过', line_no)
            continue
        if isinstance(payload, dict):
            wal_logs.append(payload)

    return wal_logs


def _append_wal_entry(log_entry: Dict[str, Any]) -> None:
    with open(LOGS_WAL_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False))
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def _wal_entry_count() -> int:
    try:
        with open(LOGS_WAL_FILE, 'r', encoding='utf-8') as f:
            return sum(1 for line in f if line.strip())
    except FileNotFoundError:
        return 0
    except Exception as e:
        raise RuntimeError(f'统计日志增量条数失败: {str(e)}') from e


def _reset_wal_file() -> None:
    _atomic_write_text(LOGS_WAL_FILE, '')


def _log_sort_key(log_entry: Dict[str, Any]) -> int:
    try:
        return int(log_entry.get('id', 0))
    except (TypeError, ValueError):
        return 0


def _safe_task_id(log_entry: Dict[str, Any]) -> int:
    try:
        return int(log_entry.get('task_id', 0))
    except (TypeError, ValueError):
        return 0


def _log_signature(log_entry: Dict[str, Any]) -> tuple:
    return (
        log_entry.get('id'),
        log_entry.get('task_id'),
        log_entry.get('level'),
        log_entry.get('message'),
        log_entry.get('timestamp'),
    )


def _deduplicate_logs(log_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduplicated: List[Dict[str, Any]] = []
    seen = set()

    for log_entry in log_entries:
        signature = _log_signature(log_entry)
        if signature in seen:
            continue
        seen.add(signature)
        deduplicated.append(log_entry)

    return deduplicated


def _max_log_id(log_entries: List[Dict[str, Any]]) -> int:
    max_id = 0
    for log_entry in log_entries:
        try:
            log_id = int(log_entry.get('id', 0))
        except (TypeError, ValueError):
            continue
        if log_id > max_id:
            max_id = log_id
    return max_id


def _apply_retention(log_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not log_entries:
        return []

    by_task: Dict[int, List[Dict[str, Any]]] = {}
    for log_entry in log_entries:
        task_id = _safe_task_id(log_entry)
        by_task.setdefault(task_id, []).append(log_entry)

    retained: List[Dict[str, Any]] = []
    for task_logs in by_task.values():
        task_logs.sort(key=_log_sort_key, reverse=True)
        retained.extend(task_logs[:MAX_LOGS_PER_TASK])

    retained.sort(key=_log_sort_key, reverse=True)
    if len(retained) > MAX_LOGS_ON_DISK:
        retained = retained[:MAX_LOGS_ON_DISK]

    return retained


def _merge_logs(log_groups: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for group in log_groups:
        merged.extend(deepcopy(log_entry) for log_entry in group)

    merged = _deduplicate_logs(merged)
    merged.sort(key=_log_sort_key, reverse=True)
    return _apply_retention(merged)


def _persist_logs_snapshot(log_entries: List[Dict[str, Any]]) -> None:
    payload = {
        'version': 1,
        'updated_at': datetime.now().isoformat(),
        'logs': log_entries,
    }
    _atomic_write_json(LOGS_FILE, payload)


def _initialize_last_log_id_locked() -> None:
    global _last_log_id

    max_id = _max_log_id(logs)

    try:
        max_id = max(max_id, _max_log_id(_load_logs_from_disk_snapshot()))
    except RuntimeError:
        _logger.exception('刷新日志ID时读取快照失败')

    try:
        max_id = max(max_id, _max_log_id(_load_wal_logs()))
    except RuntimeError:
        _logger.exception('刷新日志ID时读取增量文件失败')

    _last_log_id = max_id


def _compact_logs_locked(filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None) -> List[Dict[str, Any]]:
    global _last_log_id, _pending_wal_entries

    snapshot_logs = _load_logs_from_disk_snapshot()
    wal_logs = _load_wal_logs()
    merged = _merge_logs([snapshot_logs, wal_logs, logs])

    if filter_func is not None:
        merged = [log_entry for log_entry in merged if filter_func(log_entry)]
        merged.sort(key=_log_sort_key, reverse=True)
        merged = _apply_retention(merged)

    _persist_logs_snapshot(merged)
    _reset_wal_file()

    logs[:] = merged[:max_logs]
    _last_log_id = _max_log_id(merged)
    _pending_wal_entries = 0

    return merged


def load_logs() -> List[Dict[str, Any]]:
    """从磁盘加载日志。"""
    global _last_log_id, _pending_wal_entries

    with _lock:
        with _exclusive_file_lock():
            snapshot_logs = _load_logs_from_disk_snapshot()
            wal_logs = _load_wal_logs()
            merged = _merge_logs([snapshot_logs, wal_logs])

            if wal_logs:
                _persist_logs_snapshot(merged)
                _reset_wal_file()
                _pending_wal_entries = 0

            _last_log_id = _max_log_id(merged)
            return [deepcopy(log_entry) for log_entry in merged]


def save_logs() -> None:
    """将内存日志与磁盘历史合并后原子写入。"""
    _ensure_data_dir()

    with _lock:
        with _exclusive_file_lock():
            _compact_logs_locked()


def add_log(task_id: int, level: str, message: str) -> Dict[str, Any]:
    """添加日志到内存并立即持久化。"""
    global _last_log_id, _pending_wal_entries

    with _lock:
        _ensure_data_dir()

        with _exclusive_file_lock():
            _initialize_last_log_id_locked()

            next_id = (_last_log_id or 0) + 1
            _last_log_id = next_id

            entry: Dict[str, Any] = {
                'id': next_id,
                'task_id': task_id,
                'level': level,
                'message': message,
                'timestamp': datetime.now().isoformat(),
            }

            logs.insert(0, entry)
            if len(logs) > max_logs:
                del logs[max_logs:]

            try:
                _append_wal_entry(entry)
            except Exception:
                if logs and logs[0] is entry:
                    logs.pop(0)
                else:
                    logs[:] = [log_entry for log_entry in logs if log_entry is not entry]
                raise

            _pending_wal_entries += 1

            try:
                wal_entries = _wal_entry_count()
            except RuntimeError:
                _logger.exception('统计日志增量条数失败')
                wal_entries = _pending_wal_entries

            if wal_entries >= WAL_COMPACT_BATCH_SIZE:
                try:
                    _compact_logs_locked()
                except Exception:
                    _logger.exception('日志容量收敛失败')

            return deepcopy(entry)


def get_logs(task_id: Optional[int] = None, level: str = 'all', limit: int = 100) -> List[Dict[str, Any]]:
    with _lock:
        filtered = list(logs)
        if task_id is not None:
            filtered = [log for log in filtered if log.get('task_id') == task_id]
        if level != 'all':
            filtered = [log for log in filtered if log.get('level') == level]
        return [deepcopy(log_entry) for log_entry in filtered[:limit]]


def get_total_logs_count() -> int:
    with _lock:
        return len(logs)


def clear_logs() -> None:
    global _last_log_id, _pending_wal_entries

    with _lock:
        logs.clear()
        _ensure_data_dir()
        with _exclusive_file_lock():
            _persist_logs_snapshot([])
            _reset_wal_file()
        _last_log_id = 0
        _pending_wal_entries = 0


def delete_task_logs(task_id: int) -> None:
    """删除指定任务的所有日志并落盘。"""
    with _lock:
        _ensure_data_dir()
        logs[:] = [log for log in logs if _safe_task_id(log) != task_id]
        with _exclusive_file_lock():
            _compact_logs_locked(filter_func=lambda log: _safe_task_id(log) != task_id)


__all__ = ['add_log', 'get_logs', 'get_total_logs_count', 'clear_logs', 'delete_task_logs', 'load_logs', 'save_logs', 'max_logs']
