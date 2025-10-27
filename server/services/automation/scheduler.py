#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化任务调度管理模块

负责将自动化任务添加到 APScheduler 调度器
"""
from typing import Any, Dict, Optional
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.base import BaseScheduler
from server.utils import add_log


def schedule_task(
    scheduler: BaseScheduler,
    auto_task: Dict[str, Any],
    task_executor_func
) -> bool:
    """调度自动化任务
    
    将任务添加到调度器，并更新下次执行时间
    
    Args:
        scheduler: APScheduler 调度器实例
        auto_task: 自动化任务配置
        task_executor_func: 任务执行函数，签名为 func(auto_task_id: int)
        
    Returns:
        是否调度成功
    """
    auto_task_id = auto_task['id']
    
    if auto_task['status'] != 'running':
        return False
    
    try:
        # 解析 Cron 表达式
        cron_parts = auto_task['cron'].split()
        if len(cron_parts) != 5:
            add_log(0, 'error', f'[自动化] 任务 {auto_task["name"]} 的 Cron 表达式格式错误')
            return False
        
        trigger = _build_cron_trigger(auto_task['cron'])
        
        # 添加任务到调度器
        job_id = f'auto_task_{auto_task_id}'
        
        # 如果已存在，先移除
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        scheduler.add_job(
            func=task_executor_func,
            trigger=trigger,
            args=(auto_task_id,),
            id=job_id,
            replace_existing=True
        )
        
        # 更新下次执行时间
        update_next_run_time(scheduler, auto_task)
        
        add_log(0, 'info', f'[自动化] 任务 {auto_task["name"]} 已调度，Cron: {auto_task["cron"]}')
        return True
        
    except Exception as e:
        add_log(0, 'error', f'[自动化] 调度任务失败: {str(e)}')
        import traceback
        traceback.print_exc()
        return False


def unschedule_task(scheduler: BaseScheduler, auto_task_id: int) -> bool:
    """取消调度任务
    
    从调度器中移除任务
    
    Args:
        scheduler: APScheduler 调度器实例
        auto_task_id: 自动化任务ID
        
    Returns:
        是否取消成功
    """
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
    """更新任务的下次执行时间
    
    从调度器中获取任务的下次运行时间并更新到任务配置
    
    Args:
        scheduler: APScheduler 调度器实例
        auto_task: 自动化任务配置（会直接修改）
    """
    job_id = f'auto_task_{auto_task["id"]}'
    job = scheduler.get_job(job_id)
    
    if job and job.next_run_time:
        auto_task['next_run'] = job.next_run_time.isoformat()
    else:
        auto_task['next_run'] = None


def _build_cron_trigger(cron_expr: str) -> CronTrigger:
    """构建 Cron 触发器
    
    Args:
        cron_expr: Cron 表达式（5个字段：分 时 日 月 周）
        
    Returns:
        CronTrigger 实例
    """
    minute, hour, day, month, day_of_week = cron_expr.split()
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week
    )


__all__ = ["schedule_task", "unschedule_task", "update_next_run_time"]

