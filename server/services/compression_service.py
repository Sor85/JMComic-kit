#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩服务模块

提供完整的压缩功能：
- 支持 ZIP 和 7z 两种格式
- 支持 album（整本）和 photo（分章）两种压缩级别
- 支持密码加密
- 支持压缩后删除原文件
"""
import os
import shutil
from typing import Dict, Any, List, Optional
from server.utils import add_log


def compress_album(album_dir: str, output_path: str, password: Optional[str] = None, 
                   format: str = 'zip', delete_original: bool = False) -> bool:
    """
    压缩整个本子目录
    
    Args:
        album_dir: 本子目录路径
        output_path: 输出压缩文件路径
        password: 压缩密码（可选）
        format: 压缩格式 'zip' 或 '7z'
        delete_original: 是否删除原文件
        
    Returns:
        是否压缩成功
    """
    if not os.path.exists(album_dir):
        return False
    
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if format == '7z':
            _compress_to_7z(album_dir, output_path, password)
        else:
            _compress_to_zip(album_dir, output_path, password)
        
        # 压缩成功后删除原文件
        if delete_original and os.path.exists(output_path):
            shutil.rmtree(album_dir)
        
        return True
    except Exception as e:
        print(f"压缩失败: {str(e)}")
        return False


def compress_photo(photo_dir: str, output_path: str, password: Optional[str] = None,
                   format: str = 'zip', delete_original: bool = False) -> bool:
    """
    压缩单个章节目录
    
    Args:
        photo_dir: 章节目录路径
        output_path: 输出压缩文件路径
        password: 压缩密码（可选）
        format: 压缩格式 'zip' 或 '7z'
        delete_original: 是否删除原文件
        
    Returns:
        是否压缩成功
    """
    return compress_album(photo_dir, output_path, password, format, delete_original)


def _compress_to_zip(source_dir: str, output_path: str, password: Optional[str] = None):
    """使用 ZIP 格式压缩"""
    if password:
        try:
            import pyzipper
            with pyzipper.AESZipFile(output_path, 'w', compression=pyzipper.ZIP_DEFLATED) as zipf:
                zipf.setencryption(pyzipper.WZ_AES, nbits=128)
                zipf.setpassword(password.encode('utf-8'))
                _add_dir_to_archive(zipf, source_dir, source_dir)
        except ImportError:
            raise ImportError("需要安装 pyzipper 库来支持加密 ZIP: pip install pyzipper")
    else:
        import zipfile
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            _add_dir_to_archive(zipf, source_dir, source_dir)


def _compress_to_7z(source_dir: str, output_path: str, password: Optional[str] = None):
    """使用 7z 格式压缩"""
    try:
        import py7zr
        filters = [{'id': py7zr.FILTER_LZMA2}]
        
        with py7zr.SevenZipFile(output_path, 'w', password=password, 
                                filters=filters, header_encryption=True if password else False) as archive:
            archive.writeall(source_dir, arcname=os.path.basename(source_dir))
    except ImportError:
        raise ImportError("需要安装 py7zr 库来支持 7z: pip install py7zr")


def _add_dir_to_archive(archive, source_dir: str, base_dir: str):
    """递归添加目录到压缩包"""
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, base_dir)
            archive.write(file_path, arcname)


def compress_task_downloads(task_id: int, download_dir: str, compression_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    压缩任务下载的文件
    
    Args:
        task_id: 任务ID
        download_dir: 下载目录
        compression_config: 压缩配置
            - enabled: bool 是否启用压缩
            - format: str 压缩格式 'zip' 或 '7z'
            - level: str 压缩级别 'album' 或 'photo'
            - password: str 压缩密码（可选）
            - delete_original: bool 是否删除原文件
            
    Returns:
        压缩结果字典 {'success': bool, 'files': List[str], 'message': str}
    """
    if not compression_config.get('enabled', False):
        return {'success': True, 'files': [], 'message': '未启用压缩'}
    
    format_type = compression_config.get('format', 'zip')
    level = compression_config.get('level', 'album')
    password = compression_config.get('password')
    delete_original = compression_config.get('delete_original', False)
    
    compressed_files = []
    errors = []
    
    add_log(task_id, 'info', f'开始压缩下载文件，格式: {format_type}, 级别: {level}')
    
    try:
        if not os.path.exists(download_dir):
            return {'success': False, 'files': [], 'message': '下载目录不存在'}
        
        # 获取所有需要压缩的目录
        if level == 'album':
            # 整本压缩：压缩 download_dir 下的每个本子目录
            albums = [d for d in os.listdir(download_dir) 
                     if os.path.isdir(os.path.join(download_dir, d))]
            
            for album_name in albums:
                album_path = os.path.join(download_dir, album_name)
                output_name = f"{album_name}.{format_type}"
                output_path = os.path.join(download_dir, output_name)
                
                add_log(task_id, 'info', f'压缩本子: {album_name}')
                
                if compress_album(album_path, output_path, password, format_type, delete_original):
                    compressed_files.append(output_path)
                    add_log(task_id, 'success', f'压缩完成: {output_name}')
                else:
                    errors.append(f'压缩失败: {album_name}')
                    add_log(task_id, 'error', f'压缩失败: {album_name}')
        
        elif level == 'photo':
            # 分章压缩：压缩每个章节目录
            for root, dirs, files in os.walk(download_dir):
                # 只压缩包含图片文件的叶子目录
                if files and not dirs:
                    photo_dir = root
                    photo_name = os.path.basename(photo_dir)
                    parent_dir = os.path.dirname(photo_dir)
                    output_name = f"{photo_name}.{format_type}"
                    output_path = os.path.join(parent_dir, output_name)
                    
                    add_log(task_id, 'info', f'压缩章节: {photo_name}')
                    
                    if compress_photo(photo_dir, output_path, password, format_type, delete_original):
                        compressed_files.append(output_path)
                        add_log(task_id, 'success', f'压缩完成: {output_name}')
                    else:
                        errors.append(f'压缩失败: {photo_name}')
                        add_log(task_id, 'error', f'压缩失败: {photo_name}')
        
        # 生成结果消息
        if errors:
            message = f'压缩完成，但有 {len(errors)} 个失败: {", ".join(errors[:3])}'
            add_log(task_id, 'warning', message)
        else:
            message = f'压缩成功，共 {len(compressed_files)} 个文件'
            add_log(task_id, 'success', message)
        
        return {
            'success': len(errors) == 0,
            'files': compressed_files,
            'message': message,
            'errors': errors
        }
    
    except Exception as e:
        error_msg = f'压缩过程出错: {str(e)}'
        add_log(task_id, 'error', error_msg)
        return {'success': False, 'files': compressed_files, 'message': error_msg, 'errors': errors}


__all__ = ['compress_album', 'compress_photo', 'compress_task_downloads']

