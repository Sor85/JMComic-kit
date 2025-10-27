#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地运行收藏夹导出脚本

功能说明：
- 导出你的禁漫收藏夹数据到CSV文件
- 可以选择是否压缩为7z文件
- 可以选择是否设置压缩密码

使用方法：
1. 直接运行此脚本
2. 按照提示输入账号密码等信息
3. 等待导出完成

或者：
1. 在代码中直接配置账号密码（见下方配置区域）
2. 运行脚本

"""

import os
import sys

# ==================== 配置区域 ====================
# 你可以在这里直接填写账号密码，这样就不需要每次运行都输入了
# 留空则会在运行时提示输入

# 禁漫账号
JM_USERNAME = ""

# 禁漫密码
JM_PASSWORD = ""

# 压缩文件密码（可选，留空表示不设置密码）
ZIP_PASSWORD = ""

# 是否启用压缩（True/False）
ENABLE_ZIP = True

# 导出文件保存目录
SAVE_DIR = "./export/"

# 压缩文件路径（如果启用压缩）
ZIP_FILEPATH = "./export_favorites.7z"

# ==================== 配置区域结束 ====================


def get_input(prompt, default="", password=False):
    """获取用户输入，支持默认值"""
    if default:
        prompt = f"{prompt} (默认: {default if not password else '***'}): "
    else:
        prompt = f"{prompt}: "
    
    if password:
        import getpass
        value = getpass.getpass(prompt)
    else:
        value = input(prompt)
    
    return value.strip() if value.strip() else default


def check_dependencies():
    """检查依赖"""
    try:
        import jmcomic
        print("✓ jmcomic 模块已安装")
    except ImportError:
        print("✗ 未安装 jmcomic 模块")
        print("\n请先安装 jmcomic:")
        print("  pip install jmcomic -U")
        sys.exit(1)
    
    if ENABLE_ZIP:
        import shutil
        if shutil.which('7z') is None and shutil.which('7za') is None:
            print("\n⚠ 警告: 未找到 7z 命令")
            print("如果需要压缩功能，请先安装 7-Zip:")
            print("  Windows: 从 https://www.7-zip.org/ 下载安装")
            print("  Linux: sudo apt install p7zip-full")
            print("  Mac: brew install p7zip")
            response = input("\n是否继续（不压缩）？[y/N]: ")
            if response.lower() != 'y':
                sys.exit(1)
            return False
    return True


def main():
    print("=" * 60)
    print("禁漫收藏夹导出工具 - 本地运行版本")
    print("=" * 60)
    print()
    
    # 检查依赖
    zip_available = check_dependencies()
    print()
    
    # 获取配置
    global JM_USERNAME, JM_PASSWORD, ZIP_PASSWORD, ENABLE_ZIP, ZIP_FILEPATH, SAVE_DIR
    
    print(">>> 配置信息")
    print("-" * 60)
    
    if not JM_USERNAME:
        JM_USERNAME = get_input("请输入禁漫账号")
    else:
        print(f"禁漫账号: {JM_USERNAME}")
    
    if not JM_PASSWORD:
        JM_PASSWORD = get_input("请输入禁漫密码", password=True)
    else:
        print(f"禁漫密码: ***")
    
    if not JM_USERNAME or not JM_PASSWORD:
        print("\n✗ 错误: 账号或密码不能为空")
        sys.exit(1)
    
    if zip_available and ENABLE_ZIP:
        if not ZIP_PASSWORD:
            ZIP_PASSWORD = get_input("请输入压缩文件密码（留空表示不设置密码）", password=True)
        else:
            print(f"压缩密码: ***")
    
    print()
    print(">>> 导出设置")
    print("-" * 60)
    print(f"保存目录: {os.path.abspath(SAVE_DIR)}")
    if zip_available and ENABLE_ZIP:
        print(f"压缩文件: {os.path.abspath(ZIP_FILEPATH)}")
        print(f"是否加密: {'是' if ZIP_PASSWORD else '否'}")
    else:
        print("压缩功能: 禁用")
    print()
    
    # 确认
    response = input("是否开始导出？[Y/n]: ")
    if response.lower() == 'n':
        print("已取消")
        sys.exit(0)
    
    print()
    print("=" * 60)
    print("开始导出...")
    print("=" * 60)
    print()
    
    # 设置环境变量
    os.environ['JM_USERNAME'] = JM_USERNAME
    os.environ['JM_PASSWORD'] = JM_PASSWORD
    os.environ['ZIP_PASSWORD'] = ZIP_PASSWORD if ZIP_PASSWORD else ''
    
    # 导入jmcomic
    from jmcomic import create_option, JmcomicText
    
    # 配置DSL替换器
    def env_replacer(match):
        name = match[1]
        value = os.getenv(name, '')
        return value
    
    JmcomicText.dsl_replacer.add_dsl_and_replacer(r'\$\{(.*?)\}', env_replacer)
    
    # 创建配置
    config_file = os.path.join(os.path.dirname(__file__), 'local_export_favorites.yml')
    
    # 动态修改配置
    import yaml
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    # 更新配置
    config_data['plugins']['main'][1]['kwargs']['save_dir'] = SAVE_DIR
    config_data['plugins']['main'][1]['kwargs']['zip_enable'] = ENABLE_ZIP and zip_available
    config_data['plugins']['main'][1]['kwargs']['zip_filepath'] = ZIP_FILEPATH
    
    # 创建临时配置文件
    temp_config = '.temp_local_export_favorites.yml'
    with open(temp_config, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, allow_unicode=True)
    
    try:
        # 创建option并运行
        option = create_option(temp_config)
        option.call_all_plugin('main')
        
        print()
        print("=" * 60)
        print("✓ 导出完成！")
        print("=" * 60)
        print()
        print(f"导出文件位置: {os.path.abspath(SAVE_DIR)}")
        if ENABLE_ZIP and zip_available:
            if os.path.exists(ZIP_FILEPATH):
                print(f"压缩文件位置: {os.path.abspath(ZIP_FILEPATH)}")
        print()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("✗ 导出失败")
        print("=" * 60)
        print(f"错误信息: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 清理临时文件
        if os.path.exists(temp_config):
            os.remove(temp_config)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        sys.exit(0)

