#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本信息模块

存储项目版本号和相关元数据
"""

__version__ = "ver.1.0.1"
__version_info__ = (1, 0, 1)

# 项目元数据
PROJECT_NAME = "禁漫工具箱"
PROJECT_DESCRIPTION = "禁漫下载、导出和自动化工具"
AUTHOR = "JMComic-kit Contributors"
LICENSE = "MIT"

# 功能版本
FEATURES = {
    "web_ui": "1.0.1",
    "automation": "1.0.1",
    "rust_downloader": "1.0.0",
    "retry_failed_images": "1.0.1",
}

# 构建信息
BUILD_DATE = "2025-01"


def get_version() -> str:
    """获取版本号字符串"""
    return __version__


def get_version_info() -> tuple:
    """获取版本号元组"""
    return __version_info__


def get_full_version() -> str:
    """获取完整版本信息"""
    return f"{PROJECT_NAME} {__version__}"


def print_version_info():
    """打印版本信息"""
    print(f"{PROJECT_NAME} {__version__}")
    print(f"构建日期: {BUILD_DATE}")
    print(f"功能版本:")
    for feature, version in FEATURES.items():
        print(f"  - {feature}: {version}")


__all__ = [
    "__version__",
    "__version_info__",
    "PROJECT_NAME",
    "get_version",
    "get_version_info",
    "get_full_version",
    "print_version_info",
]

