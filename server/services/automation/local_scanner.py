#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地相册扫描模块

从已下载目录中提取相册ID，支持多种目录命名格式
"""
import os
import re
from typing import Set


def scan_local_albums(download_dir: str) -> Set[str]:
    """扫描本地目录，提取已下载的相册ID
    
    支持的目录命名格式：
    - Bd_12345_xxx
    - [12345]_xxx
    - 12345_xxx
    - 其他包含3位及以上数字的格式
    
    Args:
        download_dir: 下载目录路径
        
    Returns:
        相册ID集合
        
    Raises:
        OSError: 目录不存在或无权限访问
    """
    if not os.path.exists(download_dir):
        return set()
    
    album_ids: Set[str] = set()
    
    try:
        for item in os.listdir(download_dir):
            item_path = os.path.join(download_dir, item)
            
            # 只处理目录
            if not os.path.isdir(item_path):
                continue
            
            # 提取目录名中的数字（3位及以上）
            match = re.search(r"(\d{3,})", item)
            if match:
                album_ids.add(match.group(1))
                
    except (OSError, PermissionError) as e:
        raise OSError(f"无法读取目录 {download_dir}: {str(e)}")
    
    return album_ids


__all__ = ["scan_local_albums"]

