#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 生成服务模块

提供完整的 PDF 生成功能：
- 支持 album（整本）和 photo（分章）两种生成级别
- 支持密码加密
- 支持生成后删除原图片
"""
import os
import io
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path
from server.utils import add_log


def generate_album_pdf(album_dir: str, output_path: str, password: Optional[str] = None,
                       delete_original: bool = False) -> bool:
    """
    将整本本子的所有图片合并为一个 PDF
    
    Args:
        album_dir: 本子目录路径
        output_path: 输出 PDF 文件路径
        password: PDF 密码（可选）
        delete_original: 是否删除原图片
        
    Returns:
        是否生成成功
    """
    if not os.path.exists(album_dir):
        return False
    
    try:
        # 递归收集所有图片文件
        images = []
        for root, dirs, files in os.walk(album_dir):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                if _is_image_file(file_path):
                    images.append(file_path)
        
        if not images:
            print(f"未找到图片文件: {album_dir}")
            return False
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 生成 PDF
        _convert_images_to_pdf(images, output_path, password)
        
        # 生成成功后删除原图片
        if delete_original and os.path.exists(output_path):
            shutil.rmtree(album_dir)
        
        return True
    except Exception as e:
        print(f"PDF 生成失败: {str(e)}")
        return False


def generate_photo_pdf(photo_dir: str, output_path: str, password: Optional[str] = None,
                       delete_original: bool = False) -> bool:
    """
    将单个章节的图片合并为一个 PDF
    
    Args:
        photo_dir: 章节目录路径
        output_path: 输出 PDF 文件路径
        password: PDF 密码（可选）
        delete_original: 是否删除原图片
        
    Returns:
        是否生成成功
    """
    if not os.path.exists(photo_dir):
        return False
    
    try:
        # 收集章节目录下的所有图片
        images = []
        for file in sorted(os.listdir(photo_dir)):
            file_path = os.path.join(photo_dir, file)
            if os.path.isfile(file_path) and _is_image_file(file_path):
                images.append(file_path)
        
        if not images:
            print(f"未找到图片文件: {photo_dir}")
            return False
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 生成 PDF
        _convert_images_to_pdf(images, output_path, password)
        
        # 生成成功后删除原图片
        if delete_original and os.path.exists(output_path):
            shutil.rmtree(photo_dir)
        
        return True
    except Exception as e:
        print(f"PDF 生成失败: {str(e)}")
        return False


def _is_image_file(file_path: str) -> bool:
    """判断文件是否为图片"""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
    return Path(file_path).suffix.lower() in valid_extensions


def _convert_images_to_pdf(images: List[str], output_path: str, password: Optional[str] = None):
    """
    将图片列表转换为 PDF
    
    Args:
        images: 图片文件路径列表
        output_path: 输出 PDF 路径
        password: 密码（可选）
    """
    try:
        import img2pdf
    except ImportError:
        raise ImportError("需要安装 img2pdf 库来支持 PDF 生成: pip install img2pdf")
    
    # 使用 img2pdf 转换图片为 PDF
    pdf_bytes = img2pdf.convert(images, producer="JMComic-kit", creator="JMComic-kit")
    
    # 如果需要密码保护
    if password:
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            try:
                from PyPDF2 import PdfReader, PdfWriter
            except ImportError:
                raise ImportError("需要安装 pypdf 或 PyPDF2 库来支持 PDF 加密: pip install pypdf")
        
        # 读取生成的 PDF
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        
        # 复制所有页面
        for page in reader.pages:
            writer.add_page(page)
        
        # 添加密码
        writer.encrypt(password)
        
        # 写入加密的 PDF
        with open(output_path, 'wb') as f:
            writer.write(f)
    else:
        # 直接写入 PDF
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)


def generate_task_pdfs(task_id: int, download_dir: str, pdf_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    为任务生成 PDF
    
    Args:
        task_id: 任务 ID
        download_dir: 下载目录
        pdf_config: PDF 配置
            - enabled: bool 是否启用 PDF 生成
            - level: str 生成级别 'album' 或 'photo'
            - password: str PDF 密码（可选）
            - delete_original: bool 是否删除原图片
            
    Returns:
        生成结果字典 {'success': bool, 'files': List[str], 'message': str}
    """
    if not pdf_config.get('enabled', False):
        return {'success': True, 'files': [], 'message': '未启用 PDF 生成'}
    
    level = pdf_config.get('level', 'album')
    password = pdf_config.get('password')
    delete_original = pdf_config.get('delete_original', False)
    
    pdf_files = []
    errors = []
    
    add_log(task_id, 'info', f'开始生成 PDF，级别: {level}')
    
    try:
        if not os.path.exists(download_dir):
            return {'success': False, 'files': [], 'message': '下载目录不存在'}
        
        # 获取所有需要处理的目录
        if level == 'album':
            # 整本 PDF：为每个本子目录生成一个 PDF
            albums = [d for d in os.listdir(download_dir)
                     if os.path.isdir(os.path.join(download_dir, d))]
            
            for album_name in albums:
                album_path = os.path.join(download_dir, album_name)
                output_name = f"{album_name}.pdf"
                output_path = os.path.join(download_dir, output_name)
                
                add_log(task_id, 'info', f'生成本子 PDF: {album_name}')
                
                if generate_album_pdf(album_path, output_path, password, delete_original):
                    pdf_files.append(output_path)
                    add_log(task_id, 'success', f'PDF 生成完成: {output_name}')
                else:
                    errors.append(f'PDF 生成失败: {album_name}')
                    add_log(task_id, 'error', f'PDF 生成失败: {album_name}')
        
        elif level == 'photo':
            # 分章 PDF：为每个章节目录生成一个 PDF
            for root, dirs, files in os.walk(download_dir):
                # 只处理包含图片文件的叶子目录
                if files and not dirs:
                    # 检查是否包含图片
                    has_images = any(_is_image_file(os.path.join(root, f)) for f in files)
                    if not has_images:
                        continue
                    
                    photo_dir = root
                    photo_name = os.path.basename(photo_dir)
                    parent_dir = os.path.dirname(photo_dir)
                    output_name = f"{photo_name}.pdf"
                    output_path = os.path.join(parent_dir, output_name)
                    
                    add_log(task_id, 'info', f'生成章节 PDF: {photo_name}')
                    
                    if generate_photo_pdf(photo_dir, output_path, password, delete_original):
                        pdf_files.append(output_path)
                        add_log(task_id, 'success', f'PDF 生成完成: {output_name}')
                    else:
                        errors.append(f'PDF 生成失败: {photo_name}')
                        add_log(task_id, 'error', f'PDF 生成失败: {photo_name}')
        
        # 生成结果消息
        if errors:
            message = f'PDF 生成完成，但有 {len(errors)} 个失败: {", ".join(errors[:3])}'
            add_log(task_id, 'warning', message)
        else:
            message = f'PDF 生成成功，共 {len(pdf_files)} 个文件'
            add_log(task_id, 'success', message)
        
        return {
            'success': len(errors) == 0,
            'files': pdf_files,
            'message': message,
            'errors': errors
        }
    
    except Exception as e:
        error_msg = f'PDF 生成过程出错: {str(e)}'
        add_log(task_id, 'error', error_msg)
        return {'success': False, 'files': pdf_files, 'message': error_msg, 'errors': errors}


__all__ = ['generate_album_pdf', 'generate_photo_pdf', 'generate_task_pdfs']

