from typing import Any, Dict, List, Literal, Optional, TypedDict


TaskStatus = Literal["pending", "running", "completed", "failed", "partial_success"]
TaskType = Literal["download", "export"]


class BaseTask(TypedDict, total=False):
    id: int
    type: TaskType
    status: TaskStatus
    progress: int
    create_time: str
    start_time: Optional[str]
    end_time: Optional[str]
    error: Optional[str]


class DownloadTask(BaseTask, total=False):
    album_ids: List[str]
    photo_ids: List[str]
    config: Dict[str, Any]
    auto_task_id: Optional[int]
    auto_task_name: Optional[str]
    auto_execution_id: Optional[int]
    retry_count: Optional[int]
    failed_images: Optional[List[str]]


class ExportTask(BaseTask, total=False):
    username: str
    password: str
    config: Dict[str, Any]


class AutoTask(TypedDict, total=False):
    id: int
    name: str
    username: str
    password: str
    cron: str
    download_dir: str
    speed_limit: int
    client_impl: str
    image_suffix: str
    batch_size: int
    status: Literal["running", "stopped"]
    run_count: int
    downloaded_count: int
    skipped_count: int
    monthly_new_count: int
    last_month_count: int
    created_time: str
    last_run: Optional[str]
    next_run: Optional[str]


ExecutionStatus = Literal["running", "completed", "failed"]


class AutoTaskExecution(TypedDict, total=False):
    """自动化任务执行记录"""
    id: int
    auto_task_id: int
    auto_task_name: str
    status: ExecutionStatus
    start_time: str
    end_time: Optional[str]
    scanned_count: int
    local_count: int
    to_download_count: int
    skipped_count: int
    downloaded_task_ids: List[int]
    error: Optional[str]


__all__ = [
    "TaskStatus",
    "TaskType",
    "BaseTask",
    "DownloadTask",
    "ExportTask",
    "AutoTask",
    "ExecutionStatus",
    "AutoTaskExecution",
]


