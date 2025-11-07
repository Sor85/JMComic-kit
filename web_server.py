#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
禁漫工具 Web 服务器

提供 Web 界面用于下载本子和导出收藏夹
"""

import os
import stat
import atexit
from flask import Flask, render_template
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from server.state import tasks, auto_tasks, auto_executions, init_task_counter, init_auto_task_counter, init_auto_execution_counter
from server.utils.storage import load_auto_tasks as storage_load_auto_tasks, load_auto_executions as storage_load_auto_executions, load_manual_tasks as storage_load_manual_tasks
from server.utils.logs import add_log, load_logs, logs
from server.routes import register_blueprints
from server.routes.automation_routes import schedule_auto_task

app = Flask(__name__, 
            static_folder='web/static',
            template_folder='web')
CORS(app)


def _apply_umask_and_permissions() -> None:
    """根据环境变量设置 umask，并确保核心目录具备 0777 权限。"""
    umask_str = os.getenv('UMASK', '000')
    try:
        os.umask(int(umask_str, 8))
    except ValueError:
        print(f"无效的 UMASK 值: {umask_str}，保持默认 umask")

    for rel_path in ('data', 'download', 'export'):
        abs_path = os.path.abspath(rel_path)
        os.makedirs(abs_path, exist_ok=True)
        try:
            os.chmod(abs_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        except PermissionError:
            print(f"无法修改目录权限: {abs_path}")


_apply_umask_and_permissions()

# 手动任务从磁盘恢复
try:
    persisted_tasks = storage_load_manual_tasks()
    if persisted_tasks:
        tasks.update(persisted_tasks)
        init_task_counter(max(persisted_tasks.keys()))
        add_log(0, 'info', f'成功恢复 {len(persisted_tasks)} 个历史手动任务')
except Exception as e:
    add_log(0, 'error', f'加载手动任务失败: {str(e)}')

# 自动化任务存储从磁盘恢复
try:
    persisted = storage_load_auto_tasks()
    if persisted:
        auto_tasks.update(persisted)
        init_auto_task_counter(max(auto_tasks.keys()))
except Exception as e:
    add_log(0, 'error', f'加载自动化任务失败: {str(e)}')

# 执行记录从磁盘恢复
try:
    persisted_executions = storage_load_auto_executions()
    if persisted_executions:
        auto_executions.update(persisted_executions)
        init_auto_execution_counter(max(auto_executions.keys()))
except Exception as e:
    add_log(0, 'error', f'加载执行记录失败: {str(e)}')

# 日志从磁盘恢复
try:
    persisted_logs = load_logs()
    if persisted_logs:
        # 直接恢复所有日志，不清理
        # 因为手动任务的日志应该和任务一起持久化保存
        logs.clear()
        logs.extend(persisted_logs)
        
        add_log(0, 'info', f'成功恢复 {len(persisted_logs)} 条历史日志')
except Exception as e:
    add_log(0, 'error', f'加载历史日志失败: {str(e)}')

# APScheduler 调度器
scheduler = BackgroundScheduler()
scheduler.start()


@atexit.register
def shutdown_scheduler():
    """优雅关闭调度器。"""
    if scheduler.running:
        add_log(0, 'info', '正在关闭调度器...')
        scheduler.shutdown(wait=True)
        add_log(0, 'info', '调度器已关闭')


# 注册所有路由 Blueprint
register_blueprints(app, scheduler)


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


if __name__ == '__main__':
    from server.version import get_full_version, __version__

    host = os.getenv('WEB_SERVER_HOST', '127.0.0.1')
    port = int(os.getenv('WEB_SERVER_PORT', '5000'))

    print("=" * 60)
    print(f"禁漫工具 Web 服务器 {__version__}")
    print("=" * 60)
    print()
    print(f"访问地址: http://{host}:{port}")
    print()
    print("功能:")
    print("  - 手动下载本子")
    print("  - 导出收藏夹")
    print("  - 自动化同步")
    print("  - 失败图片重试")
    print("  - 任务管理")
    print("  - 日志查看")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()

    # 关闭 debug 模式和 reloader，加快启动速度
    # 启动时恢复调度（仅对运行中的任务）
    try:
        for tid, t in auto_tasks.items():
            if t.get('status') == 'running':
                schedule_auto_task(tid)
    except Exception as e:
        add_log(0, 'error', f'恢复自动化任务调度失败: {str(e)}')
    
    # 默认监听本地，可通过 WEB_SERVER_HOST=0.0.0.0 放开访问（注意安全）
    app.run(host=host, port=port, debug=False, threaded=True)

