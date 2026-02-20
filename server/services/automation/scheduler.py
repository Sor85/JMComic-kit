#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化任务调度模块。
统一处理定时任务注册、取消与下次执行时间更新。
"""

from typing import Any, Dict

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger

from server.state import (
    AUTO_TASK_DESIRED_ENABLED,
    AUTO_TASK_RUNTIME_IDLE,
    AUTO_TASK_RUNTIME_SCHEDULED,
    update_auto_task_status,
)
from server.utils import add_log


def _is_task_enabled(auto_task: Dict[str, Any]) -> bool:
    desired_status = auto_task.get('desired_status')
    if desired_status is not None:
        return desired_status == AUTO_TASK_DESIRED_ENABLED
    return auto_task.get('status') == 'running'


def schedule_task(
    scheduler: BaseScheduler,
    auto_task: Dict[str, Any],
    task_executor_func,
) -> bool:
    """调度自动化任务。"""
    auto_task_id = auto_task['id']

    if not _is_task_enabled(auto_task):
        update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_IDLE)
        auto_task['next_run'] = None
        return False

    try:
        cron_parts = auto_task['cron'].split()
        if len(cron_parts) != 5:
            add_log(0, 'error', f'[自动化] 任务 {auto_task["name"]} 的 Cron 表达式格式错误')
            return False

        trigger = _build_cron_trigger(auto_task['cron'])
        job_id = f'auto_task_{auto_task_id}'

        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(
            func=task_executor_func,
            trigger=trigger,
            args=(auto_task_id,),
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        update_next_run_time(scheduler, auto_task)
        update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_SCHEDULED)

        add_log(0, 'info', f'[自动化] 任务 {auto_task["name"]} 已调度，Cron: {auto_task["cron"]}')
        return True

    except Exception as e:
        add_log(0, 'error', f'[自动化] 调度任务失败: {str(e)}')
        update_auto_task_status(auto_task, runtime_status=AUTO_TASK_RUNTIME_IDLE)
        return False


def unschedule_task(scheduler: BaseScheduler, auto_task_id: int) -> bool:
    """取消调度任务。"""
    job_id = f'auto_task_{auto_task_id}'

    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            return True
        return False
    except Exception as e:
        add_log(0, 'error', f'[自动化] 取消调度失败: {str(e)}')
        return False


def update_next_run_time(scheduler: BaseScheduler, auto_task: Dict[str, Any]) -> None:
    """更新任务的下次执行时间。"""
    job_id = f'auto_task_{auto_task["id"]}'
    job = scheduler.get_job(job_id)

    if job and job.next_run_time:
        auto_task['next_run'] = job.next_run_time.isoformat()
    else:
        auto_task['next_run'] = None


def _build_cron_trigger(cron_expr: str) -> CronTrigger:
    """构建 Cron 触发器。"""
    minute, hour, day, month, day_of_week = cron_expr.split()
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )


__all__ = ['schedule_task', 'unschedule_task', 'update_next_run_time']
