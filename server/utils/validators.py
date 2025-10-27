"""输入验证工具模块"""
import os
import re
from typing import Optional
from apscheduler.triggers.cron import CronTrigger


def validate_path_safety(path: str, allowed_base: Optional[str] = None) -> bool:
    """验证路径安全性，防止路径遍历攻击。
    
    Args:
        path: 待验证的路径
        allowed_base: 允许的基础路径（可选）
        
    Returns:
        bool: 路径是否安全
    """
    if not path:
        return False
    
    # 检查危险字符
    dangerous_patterns = ['..', '~', '$', '`', '|', ';', '&', '\n', '\r']
    for pattern in dangerous_patterns:
        if pattern in path:
            return False
    
    # 如果指定了基础路径，验证是否在允许范围内
    if allowed_base:
        try:
            abs_path = os.path.abspath(os.path.expanduser(path))
            abs_base = os.path.abspath(os.path.expanduser(allowed_base))
            return abs_path.startswith(abs_base)
        except (ValueError, OSError):
            return False
    
    return True


def validate_cron_expression(cron: str) -> tuple[bool, str]:
    """验证 Cron 表达式的合法性。
    
    Args:
        cron: Cron 表达式字符串
        
    Returns:
        tuple[bool, str]: (是否合法, 错误信息)
    """
    if not cron or not isinstance(cron, str):
        return False, "Cron 表达式不能为空"
    
    parts = cron.strip().split()
    if len(parts) != 5:
        return False, "Cron 表达式必须包含5个字段（分 时 日 月 星期）"
    
    # 使用 APScheduler 的 CronTrigger 验证
    try:
        minute, hour, day, month, day_of_week = parts
        CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week
        )
        return True, ""
    except (ValueError, TypeError) as e:
        return False, f"Cron 表达式格式错误: {str(e)}"


def validate_speed_limit(speed_str: str) -> tuple[bool, int, str]:
    """验证并解析速度限制参数。
    
    Args:
        speed_str: 速度字符串，如 "10mb", "512kb"
        
    Returns:
        tuple[bool, int, str]: (是否合法, KB值, 错误信息)
    """
    if not speed_str or not isinstance(speed_str, str):
        return True, 0, ""  # 空值表示不限速
    
    speed_str = speed_str.strip().lower()
    
    # 匹配数字和单位
    match = re.match(r'^(\d+(?:\.\d+)?)\s*(kb|mb)?$', speed_str)
    if not match:
        return False, 0, "速度格式错误，应为数字+单位（如 10mb 或 512kb）"
    
    value_str, unit = match.groups()
    try:
        value = float(value_str)
    except ValueError:
        return False, 0, "速度值必须为数字"
    
    # 转换为 KB
    if unit == 'mb':
        kb_value = int(value * 1024)
    elif unit == 'kb' or unit is None:
        kb_value = int(value)
    else:
        return False, 0, f"不支持的单位: {unit}"
    
    # 验证范围（1KB - 100MB）
    if kb_value < 1:
        return False, 0, "速度限制不能小于 1KB"
    if kb_value > 100 * 1024:
        return False, 0, "速度限制不能超过 100MB"
    
    return True, kb_value, ""


def validate_album_id(album_id: str) -> bool:
    """验证本子ID格式。
    
    Args:
        album_id: 本子ID
        
    Returns:
        bool: 是否为合法的本子ID
    """
    if not album_id:
        return False
    
    # 移除 JM 前缀
    clean_id = album_id.replace('JM', '').replace('jm', '').strip()
    
    # 验证是否为数字且长度合理
    return clean_id.isdigit() and 1 <= len(clean_id) <= 10


def sanitize_album_ids(ids_text: str) -> list[str]:
    """清理并提取本子ID列表。
    
    Args:
        ids_text: 包含ID的文本（每行一个）
        
    Returns:
        list[str]: 清理后的ID列表
    """
    id_list = []
    for line in ids_text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            # 移除 JM 前缀
            clean_id = line.replace('JM', '').replace('jm', '').strip()
            if validate_album_id(clean_id):
                id_list.append(clean_id)
    return list(set(id_list))  # 去重


__all__ = [
    'validate_path_safety',
    'validate_cron_expression',
    'validate_speed_limit',
    'validate_album_id',
    'sanitize_album_ids',
]

