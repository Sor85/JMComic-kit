#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收藏夹获取模块

负责登录、导出收藏夹并解析相册ID
"""
import csv
import os
import re
import tempfile
import yaml
from typing import List, Set
from jmcomic import create_option


def fetch_favorites(
    username: str,
    password: str,
    client_impl: str = "api",
    execution_id: int = 0
) -> List[str]:
    """获取用户收藏夹中的所有相册ID
    
    通过以下步骤获取：
    1. 配置环境并登录
    2. 使用导出插件导出收藏夹为CSV
    3. 解析CSV提取相册ID
    4. 清理临时文件
    
    Args:
        username: 用户名
        password: 密码
        client_impl: 客户端实现方式（api/html）
        execution_id: 执行记录ID（用于日志）
        
    Returns:
        相册ID列表（去重后）
        
    Raises:
        RuntimeError: 登录失败或导出失败
        FileNotFoundError: 配置文件不存在
    """
    from server.utils.jmcomic_helper import setup_jmcomic_env
    from server.utils import add_log
    
    # 配置环境变量
    setup_jmcomic_env(username=username, password=password)
    
    # 步骤1：显式登录
    temp_login_config = _create_login_config()
    try:
        option = create_option(temp_login_config)
        option.client.impl = client_impl
        option.call_all_plugin("main")  # 执行登录
        add_log(execution_id, "info", f"[自动化] 登录完成 (实现: {client_impl})")
    finally:
        _cleanup_file(temp_login_config)
    
    # 步骤2：导出收藏夹
    temp_dir = tempfile.mkdtemp(prefix="auto_export_")
    try:
        csv_file = _export_favorites_to_csv(temp_dir, client_impl, execution_id)
        album_ids = _parse_csv_for_album_ids(csv_file)
        add_log(execution_id, "info", f"[自动化] 通过导出共解析到 {len(album_ids)} 个相册ID")
        return list(album_ids)
    finally:
        _cleanup_temp_dir(temp_dir)


def _create_login_config() -> str:
    """创建临时登录配置文件（仅包含login插件）"""
    with open("local_export_favorites.yml", "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    # 只保留 login 插件
    if isinstance(config_data, dict) and "plugins" in config_data:
        if "main" in config_data["plugins"] and isinstance(config_data["plugins"]["main"], list):
            if len(config_data["plugins"]["main"]) > 0:
                config_data["plugins"]["main"] = [config_data["plugins"]["main"][0]]
    
    temp_config = ".temp_auto_login.yml"
    with open(temp_config, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True)
    
    return temp_config


def _export_favorites_to_csv(
    temp_dir: str,
    client_impl: str,
    execution_id: int
) -> str:
    """导出收藏夹到CSV文件
    
    Returns:
        CSV文件路径
        
    Raises:
        RuntimeError: 导出失败或未找到CSV文件
    """
    from server.utils import add_log
    
    add_log(execution_id, "info", "[自动化] 正在获取收藏夹列表... (通过导出插件稳健获取)")
    
    with open("local_export_favorites.yml", "r", encoding="utf-8") as f:
        export_conf = yaml.safe_load(f)
    
    # 覆盖导出参数：保存目录、禁用压缩
    export_conf["plugins"]["main"][1]["kwargs"]["save_dir"] = temp_dir
    export_conf["plugins"]["main"][1]["kwargs"]["zip_enable"] = False
    
    temp_export_yaml = os.path.join(temp_dir, "auto_export.yml")
    with open(temp_export_yaml, "w", encoding="utf-8") as f:
        yaml.dump(export_conf, f, allow_unicode=True)
    
    export_option = create_option(temp_export_yaml)
    export_option.client.impl = client_impl
    
    try:
        export_option.call_all_plugin("main")
    except Exception as e:
        # 如果当前实现失败，尝试 html
        if client_impl != "html":
            add_log(execution_id, "info", f"[自动化] 导出(实现:{client_impl})失败，尝试 html：{e}")
            export_option.client.impl = "html"
            export_option.call_all_plugin("main")
        else:
            raise RuntimeError(f"导出收藏夹失败: {e}")
    
    # 查找导出的CSV文件
    csv_file = None
    for fn in os.listdir(temp_dir):
        if fn.lower().endswith('.csv'):
            csv_file = os.path.join(temp_dir, fn)
            break
    
    if not csv_file:
        raise RuntimeError("未找到导出的收藏夹CSV文件")
    
    return csv_file


def _parse_csv_for_album_ids(csv_file: str) -> Set[str]:
    """从CSV文件中解析相册ID
    
    Args:
        csv_file: CSV文件路径
        
    Returns:
        相册ID集合
    """
    album_ids: Set[str] = set()
    
    with open(csv_file, "r", encoding="utf-8", newline='') as f:
        reader = csv.reader(f)
        headers = next(reader, [])  # 跳过表头
        
        for row in reader:
            # 在整行中查找数字ID（3位及以上）
            text = ",".join(row)
            match = re.search(r"(\d{3,})", text)
            if match:
                album_ids.add(match.group(1))
    
    return album_ids


def _cleanup_file(filepath: str) -> None:
    """安全删除文件"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass


def _cleanup_temp_dir(temp_dir: str) -> None:
    """安全清理临时目录"""
    try:
        for fn in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, fn))
            except OSError:
                pass
        os.rmdir(temp_dir)
    except (OSError, PermissionError):
        pass


__all__ = ["fetch_favorites"]

