#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV文件管理路由
处理收藏夹CSV文件的列表和读取
"""

import os
import csv
from datetime import datetime
from flask import Blueprint, jsonify
from server.utils.validators import validate_path_safety

csv_bp = Blueprint('csv', __name__)

# CSV文件目录
CSV_DIR = './export/'


@csv_bp.route('/csv/list', methods=['GET'])
def list_csv_files():
    """
    列出所有CSV文件
    返回文件名、大小、修改时间等信息，按修改时间降序排序
    """
    try:
        if not os.path.exists(CSV_DIR):
            return jsonify([])
        
        files = []
        for filename in os.listdir(CSV_DIR):
            if filename.lower().endswith('.csv'):
                filepath = os.path.join(CSV_DIR, filename)
                try:
                    stat = os.stat(filepath)
                    files.append({
                        'filename': filename,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'modified_timestamp': stat.st_mtime
                    })
                except Exception as e:
                    # 跳过无法读取的文件
                    continue
        
        # 按修改时间降序排序（最新的在前）
        files.sort(key=lambda x: x['modified_timestamp'], reverse=True)
        
        # 移除timestamp字段（仅用于排序）
        for f in files:
            del f['modified_timestamp']
        
        return jsonify(files)
    
    except Exception as e:
        return jsonify({'error': f'读取文件列表失败: {str(e)}'}), 500


@csv_bp.route('/csv/read/<filename>', methods=['GET'])
def read_csv_file(filename):
    """
    读取指定CSV文件，提取本子ID
    
    Args:
        filename: CSV文件名
    
    Returns:
        JSON: { 'ids': [...], 'count': N }
    """
    try:
        # 安全检查：防止路径遍历攻击
        if not validate_path_safety(filename):
            return jsonify({'error': '文件名包含非法字符'}), 400
        
        # 确保文件是CSV格式
        if not filename.lower().endswith('.csv'):
            return jsonify({'error': '只支持CSV文件'}), 400
        
        csv_path = os.path.join(CSV_DIR, filename)
        
        # 检查文件是否存在
        if not os.path.exists(csv_path):
            return jsonify({'error': f'文件不存在: {filename}'}), 404
        
        # 读取CSV文件，提取ID
        ids = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # 检查是否有数据
                if not reader.fieldnames:
                    return jsonify({'error': 'CSV文件格式错误：没有表头'}), 400
                
                for row in reader:
                    # 提取ID列（按优先级尝试不同的列名）
                    aid = None
                    for col_name in ['id', 'aid', 'album_id', 'ID', 'AID']:
                        if col_name in row and row[col_name]:
                            aid = row[col_name]
                            break
                    
                    # 如果没有找到ID列，使用第一列
                    if not aid and row:
                        aid = list(row.values())[0]
                    
                    # 清理和验证ID
                    if aid:
                        aid = str(aid).strip()
                        # 移除可能的JM前缀
                        if aid.upper().startswith('JM'):
                            aid = aid[2:].strip()
                        # 只保留数字ID
                        if aid and aid.isdigit():
                            ids.append(aid)
        
        except UnicodeDecodeError:
            # 尝试使用其他编码
            try:
                with open(csv_path, 'r', encoding='gbk') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        aid = None
                        for col_name in ['id', 'aid', 'album_id', 'ID', 'AID']:
                            if col_name in row and row[col_name]:
                                aid = row[col_name]
                                break
                        if not aid and row:
                            aid = list(row.values())[0]
                        if aid:
                            aid = str(aid).strip()
                            if aid.upper().startswith('JM'):
                                aid = aid[2:].strip()
                            if aid and aid.isdigit():
                                ids.append(aid)
            except Exception as e:
                return jsonify({'error': f'读取文件失败（编码错误）: {str(e)}'}), 400
        
        # 去重并保持顺序
        unique_ids = list(dict.fromkeys(ids))
        
        if not unique_ids:
            return jsonify({
                'ids': [],
                'count': 0,
                'message': 'CSV文件中没有找到有效的本子ID'
            })
        
        return jsonify({
            'ids': unique_ids,
            'count': len(unique_ids),
            'filename': filename
        })
    
    except Exception as e:
        return jsonify({'error': f'读取文件失败: {str(e)}'}), 500

