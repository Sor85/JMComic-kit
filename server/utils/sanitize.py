from typing import Any, Dict, List, Union

SENSITIVE_TOKENS = ("password", "passwd", "secret", "token", "apikey", "api_key", "key")

def _is_sensitive_key(key: str) -> bool:
    lk = key.lower()
    return any(tok in lk for tok in SENSITIVE_TOKENS)

def strip_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """浅层脱敏（保留非敏感键）。"""
    return {k: v for k, v in data.items() if not _is_sensitive_key(k)}

JSONLike = Union[Dict[str, Any], List[Any], Any]

def deep_strip_sensitive(obj: JSONLike) -> JSONLike:
    """深度递归脱敏：
    - 删除所有 key 名包含敏感词的键（如 password, token, api_key 等）
    - 对列表与字典递归处理
    - 返回新对象，不修改原对象
    """
    if isinstance(obj, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in obj.items():
            if _is_sensitive_key(k):
                continue
            sanitized[k] = deep_strip_sensitive(v)
        return sanitized
    if isinstance(obj, list):
        return [deep_strip_sensitive(v) for v in obj]
    return obj

__all__ = ["strip_sensitive", "deep_strip_sensitive", "SENSITIVE_TOKENS"]


