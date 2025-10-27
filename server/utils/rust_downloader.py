"""
Rust 下载器集成模块

提供 Python 调用 Rust 下载器的接口
"""
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ImageTask:
    """图片下载任务"""
    url: str
    path: str
    headers: Dict[str, str]
    scramble_id: Optional[int] = None


@dataclass
class DownloadResult:
    """下载结果"""
    success: int
    failed: int
    failed_urls: List[str]


def get_rust_downloader_path() -> Optional[str]:
    """获取 Rust 下载器可执行文件路径"""
    system = platform.system().lower()
    
    # 确定二进制文件名
    if system == "windows":
        binary_name = "jmcomic-downloader-windows.exe"
    elif system == "linux":
        binary_name = "jmcomic-downloader-linux"
    elif system == "darwin":
        binary_name = "jmcomic-downloader-macos"
    else:
        return None
    
    # 查找二进制文件
    project_root = Path(__file__).parent.parent.parent
    binary_path = project_root / "bin" / binary_name
    
    if binary_path.exists():
        return str(binary_path)
    
    return None


def is_rust_downloader_available() -> bool:
    """检查 Rust 下载器是否可用"""
    return get_rust_downloader_path() is not None


def download_images_with_rust(
    images: List[ImageTask],
    concurrent: int = 50,
    retry: int = 3,
    timeout: int = 30,
    progress_callback: Optional[callable] = None
) -> DownloadResult:
    """
    使用 Rust 下载器下载图片
    
    Args:
        images: 图片任务列表
        concurrent: 并发数
        retry: 重试次数
        timeout: 超时时间（秒）
        progress_callback: 进度回调函数
    
    Returns:
        DownloadResult: 下载结果
    
    Raises:
        RuntimeError: 如果 Rust 下载器不可用或执行失败
    """
    downloader_path = get_rust_downloader_path()
    if not downloader_path:
        raise RuntimeError("Rust downloader not available")
    
    # 创建临时 manifest 文件
    manifest_data = {
        "images": [
            {
                "url": img.url,
                "path": img.path,
                "headers": img.headers,
                "scramble_id": img.scramble_id
            }
            for img in images
        ]
    }
    
    with tempfile.NamedTemporaryFile(
        mode='w', 
        suffix='.json', 
        delete=False,
        encoding='utf-8'
    ) as f:
        manifest_path = f.name
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)
    
    try:
        # 构建命令行参数
        cmd = [
            downloader_path,
            "--manifest", manifest_path,
            "--concurrent", str(concurrent),
            "--retry", str(retry),
            "--timeout", str(timeout),
        ]
        
        # 调试日志：输出manifest文件信息
        print(f"[Rust Downloader] Manifest file: {manifest_path}")
        print(f"[Rust Downloader] Task count: {len(images)}")
        print(f"[Rust Downloader] Command: {' '.join(cmd)}")
        
        # 执行下载器
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # 实时读取进度和错误输出
        result_json = None
        stderr_lines = []
        
        # 读取 stdout
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            
            print(f"[Rust Downloader STDOUT] {line}")  # 调试输出
            
            # 解析进度信息
            if line.startswith("PROGRESS:"):
                try:
                    progress_data = json.loads(line[9:])
                    if progress_callback:
                        progress_callback(progress_data)
                except json.JSONDecodeError as e:
                    print(f"[Rust Downloader] Failed to parse progress: {e}")
            
            # 解析最终结果
            elif line.startswith("RESULT:"):
                try:
                    result_json = json.loads(line[7:])
                    print(f"[Rust Downloader] Result: {result_json}")  # 调试输出
                except json.JSONDecodeError as e:
                    print(f"[Rust Downloader] Failed to parse result: {e}")
        
        # 读取 stderr
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"[Rust Downloader STDERR] {stderr_output}")
            stderr_lines = stderr_output.strip().split('\n')
        
        # 等待进程结束
        return_code = process.wait()
        print(f"[Rust Downloader] Exit code: {return_code}")
        
        if return_code != 0 and return_code != 1:  # 1 表示部分失败
            raise RuntimeError(f"Rust downloader failed (exit code {return_code}): {stderr_output}")
        
        # 解析结果
        if result_json:
            return DownloadResult(
                success=result_json["success"],
                failed=result_json["failed"],
                failed_urls=result_json.get("failed_urls", [])
            )
        else:
            # 如果没有收到结果，返回失败
            print(f"[Rust Downloader] No result received!")
            return DownloadResult(
                success=0,
                failed=len(images),
                failed_urls=[img.url for img in images]
            )
    
    finally:
        # 清理临时文件（调试时可以注释掉以检查 manifest）
        try:
            # 在调试模式下保留 manifest 文件
            if os.environ.get('DEBUG_RUST_DOWNLOADER'):
                print(f"[Rust Downloader] Manifest file kept at: {manifest_path}")
            else:
                os.unlink(manifest_path)
        except Exception as e:
            print(f"[Rust Downloader] Failed to clean up manifest: {e}")


def build_image_tasks_from_jmcomic(
    photo: Any,
    option: Any
) -> List[ImageTask]:
    """
    从 jmcomic Photo 对象构建图片任务列表
    
    Args:
        photo: jmcomic Photo 对象
        option: jmcomic Option 对象
    
    Returns:
        List[ImageTask]: 图片任务列表
    """
    tasks = []
    
    # 获取图片列表
    for img_detail in photo:
        # 获取图片 URL
        img_url = img_detail.img_url
        
        # 获取保存路径
        img_dir = option.dir_rule.get_image_dir(img_detail)
        img_name = img_detail.filename
        if option.download.image.suffix:
            # 替换后缀
            base_name = os.path.splitext(img_name)[0]
            img_name = f"{base_name}{option.download.image.suffix}"
        
        img_path = os.path.join(img_dir, img_name)
        
        # 构建请求头
        headers = {}
        if hasattr(option, 'client') and hasattr(option.client, 'headers'):
            headers = dict(option.client.headers)
        
        tasks.append(ImageTask(
            url=img_url,
            path=img_path,
            headers=headers
        ))
    
    return tasks


__all__ = [
    "ImageTask",
    "DownloadResult",
    "is_rust_downloader_available",
    "download_images_with_rust",
    "build_image_tasks_from_jmcomic",
    "get_rust_downloader_path",
]

