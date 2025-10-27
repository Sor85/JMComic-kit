#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地下载禁漫本子脚本

使用说明：
1. 在下方配置区域填写要下载的本子ID
2. 运行脚本：python local_download.py
3. 等待下载完成

"""

import os
import sys

# ==================== 配置区域 ====================

# 要下载的本子ID（一行一个，支持JM前缀）
ALBUM_IDS = """



"""

# 单独下载章节ID（可选）
PHOTO_IDS = """
422866


"""

# 禁漫账号（可选，如果不需要登录可留空）
JM_USERNAME = ""
JM_PASSWORD = ""

# 下载目录
DOWNLOAD_DIR = "./download/"

# 客户端类型：api（推荐，快速）或 html（慢但稳定）
CLIENT_IMPL = "api"

# 图片格式：.jpg 或 .png 或 .webp（留空表示不转换）
IMAGE_SUFFIX = ""

# 目录层级规则（可选配置）
# 默认: Bd_Aauthor_Atitle_Pindex (表示: 基础路径/作者/标题/章节索引)
# 注意: Bd 必须在最前面，表示基础路径标记
# 用 _ 分隔表示目录层级：Bd_Aauthor_Atitle_Pindex 等同于 Bd/Aauthor/Atitle/Pindex
# 详见: https://jmcomic.readthedocs.io/
DIR_RULE = "Bd_Aauthor_Atitle_Pindex"

# ==================== 配置区域结束 ====================


def check_dependencies():
    """检查依赖"""
    try:
        import jmcomic
        return True
    except ImportError:
        print("✗ 未安装 jmcomic 模块")
        print("\n请先安装 jmcomic:")
        print("  pip install jmcomic -U")
        return False


def str_to_set(text):
    """将文本转换为ID集合"""
    id_set = set()
    for line in text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            # 移除JM前缀
            line = line.replace('JM', '').replace('jm', '')
            if line.isdigit():
                id_set.add(line)
    return id_set


def main():
    print("=" * 60)
    print("禁漫本子下载工具 - 本地运行版本")
    print("=" * 60)
    print()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    print("✓ jmcomic 模块已安装")
    print()
    
    # 导入 jmcomic
    from jmcomic import (
        create_option, JmOption, DirRule,
        fix_suffix, mkdir_if_not_exists, JmcomicText
    )
    from jmcomic.cl import JmcomicUI
    
    # 解析ID
    album_id_set = str_to_set(ALBUM_IDS)
    photo_id_set = str_to_set(PHOTO_IDS)
    
    if not album_id_set and not photo_id_set:
        print("✗ 错误: 没有配置要下载的本子ID")
        print("\n请编辑 local_download.py 文件，在配置区域填写本子ID")
        print("例如:")
        print('  ALBUM_IDS = """')
        print('  422866')
        print('  123456')
        print('  """')
        sys.exit(1)
    
    print(">>> 下载任务")
    print("-" * 60)
    if album_id_set:
        print(f"本子数量: {len(album_id_set)}")
        print(f"本子ID: {', '.join(sorted(album_id_set))}")
    if photo_id_set:
        print(f"章节数量: {len(photo_id_set)}")
        print(f"章节ID: {', '.join(sorted(photo_id_set))}")
    print()
    
    print(">>> 下载设置")
    print("-" * 60)
    print(f"下载目录: {os.path.abspath(DOWNLOAD_DIR)}")
    print(f"客户端类型: {CLIENT_IMPL}")
    if IMAGE_SUFFIX:
        print(f"图片格式: {IMAGE_SUFFIX}")
    if JM_USERNAME:
        print(f"登录账号: {JM_USERNAME}")
    print(f"目录规则: {DIR_RULE}")
    print()
    
    # 确认
    response = input("是否开始下载？[Y/n]: ")
    if response.lower() == 'n':
        print("已取消")
        sys.exit(0)
    
    print()
    print("=" * 60)
    print("开始下载...")
    print("=" * 60)
    print()
    
    # 设置环境变量
    os.environ['DOWNLOAD_DIR'] = os.path.abspath(DOWNLOAD_DIR)
    os.environ['JM_USERNAME'] = JM_USERNAME if JM_USERNAME else ''
    os.environ['JM_PASSWORD'] = JM_PASSWORD if JM_PASSWORD else ''
    
    # 配置 DSL 替换器
    def env_replacer(match):
        name = match[1]
        return os.getenv(name, '')
    
    JmcomicText.dsl_replacer.add_dsl_and_replacer(r'\$\{(.*?)\}', env_replacer)
    
    # 创建下载目录
    mkdir_if_not_exists(DOWNLOAD_DIR)
    
    # 读取配置
    config_file = os.path.join(os.path.dirname(__file__), 'local_download.yml')
    option = create_option(config_file)
    
    # 覆盖配置
    if DIR_RULE:
        option.dir_rule = DirRule(DIR_RULE, base_dir=DOWNLOAD_DIR)
    
    if CLIENT_IMPL:
        option.client.impl = CLIENT_IMPL
    
    if IMAGE_SUFFIX:
        option.download.image.suffix = fix_suffix(IMAGE_SUFFIX)
    
    # 创建下载器
    helper = JmcomicUI()
    helper.album_id_list = list(album_id_set)
    helper.photo_id_list = list(photo_id_set)
    
    try:
        # 开始下载
        helper.run(option)
        
        print()
        print("=" * 60)
        print("✓ 下载完成！")
        print("=" * 60)
        print()
        print(f"下载文件位置: {os.path.abspath(DOWNLOAD_DIR)}")
        print()
        
    except KeyboardInterrupt:
        print("\n\n下载已中断")
        sys.exit(0)
    except Exception as e:
        print()
        print("=" * 60)
        print("✗ 下载失败")
        print("=" * 60)
        print(f"错误信息: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        sys.exit(0)

