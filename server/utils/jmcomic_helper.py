"""JMComic 环境配置辅助工具"""
import os
import tempfile
from typing import Any, Dict, Optional
import yaml


def setup_jmcomic_env(
    username: str = "",
    password: str = "",
    zip_password: str = "",
    download_dir: str = ""
) -> None:
    """配置 JMComic 环境变量和 DSL 替换器。
    
    Args:
        username: 禁漫账号
        password: 禁漫密码
        zip_password: 压缩密码
        download_dir: 下载目录
    """
    os.environ["JM_USERNAME"] = username
    os.environ["JM_PASSWORD"] = password
    os.environ["ZIP_PASSWORD"] = zip_password
    if download_dir:
        os.environ["DOWNLOAD_DIR"] = os.path.abspath(download_dir)
    
    # 配置 DSL 替换器
    def env_replacer(match):
        var_name = match[1] if hasattr(match, 'group') else match[1]
        return os.getenv(var_name, "")
    
    from jmcomic import JmcomicText
    JmcomicText.dsl_replacer.add_dsl_and_replacer(
        r'\$\{(.*?)\}',
        env_replacer
    )


class TempConfigFile:
    """临时配置文件上下文管理器，确保清理。"""
    
    def __init__(self, base_config_path: str, modifications: Optional[Dict[str, Any]] = None):
        """初始化临时配置文件。
        
        Args:
            base_config_path: 基础配置文件路径
            modifications: 需要修改的配置项
        """
        self.base_config_path = base_config_path
        self.modifications = modifications or {}
        self.temp_path: Optional[str] = None
        self.temp_fd: Optional[int] = None
    
    def __enter__(self) -> str:
        """创建临时配置文件并返回路径。"""
        # 读取基础配置
        with open(self.base_config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 应用修改
        for key_path, value in self.modifications.items():
            keys = key_path.split('.')
            current = config_data
            
            # 遍历路径，处理嵌套结构
            for i, key in enumerate(keys[:-1]):
                # 判断是列表索引还是字典键
                if isinstance(current, list):
                    # 列表索引
                    key = int(key)
                    current = current[key]
                else:
                    # 字典键
                    if key not in current:
                        current[key] = {}
                    current = current[key]
            
            # 处理最后一个键
            final_key = keys[-1]
            
            # 如果当前对象是列表，转换为整数索引
            if isinstance(current, list):
                final_key = int(final_key)
            
            # 如果值为 None，则删除该键
            if value is None:
                if isinstance(current, list):
                    if 0 <= final_key < len(current):
                        current.pop(final_key)
                elif final_key in current:
                    del current[final_key]
            else:
                current[final_key] = value
        
        # 创建临时文件
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix='.yml', text=True)
        
        # 写入配置
        with os.fdopen(self.temp_fd, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)
            self.temp_fd = None  # 已关闭
        
        return self.temp_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """清理临时文件。"""
        # 关闭文件描述符（如果还未关闭）
        if self.temp_fd is not None:
            try:
                os.close(self.temp_fd)
            except OSError:
                pass
        
        # 删除临时文件
        if self.temp_path and os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
            except OSError:
                pass


__all__ = [
    'setup_jmcomic_env',
    'TempConfigFile',
]

