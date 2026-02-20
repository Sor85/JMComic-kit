"""
日志配置化回归测试。
验证环境变量覆盖、默认值与非法值回退行为。
"""

import importlib
import os
import unittest
from unittest.mock import patch


class LogsEnvConfigTests(unittest.TestCase):
    def test_env_overrides_log_limits_on_module_reload(self):
        with patch.dict(os.environ, {
            'MAX_LOGS_PER_TASK': '3',
            'MAX_LOGS_ON_DISK': '7',
            'WAL_COMPACT_BATCH_SIZE': '2',
        }, clear=False):
            module = importlib.import_module('server.utils.logs')
            module = importlib.reload(module)

            self.assertEqual(3, module.MAX_LOGS_PER_TASK)
            self.assertEqual(7, module.MAX_LOGS_ON_DISK)
            self.assertEqual(2, module.WAL_COMPACT_BATCH_SIZE)

    def test_defaults_remain_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ('MAX_LOGS_PER_TASK', 'MAX_LOGS_ON_DISK', 'WAL_COMPACT_BATCH_SIZE'):
                os.environ.pop(key, None)

            module = importlib.import_module('server.utils.logs')
            module = importlib.reload(module)

            self.assertEqual(200, module.MAX_LOGS_PER_TASK)
            self.assertEqual(20000, module.MAX_LOGS_ON_DISK)
            self.assertEqual(100, module.WAL_COMPACT_BATCH_SIZE)

    def test_invalid_env_values_fallback_to_defaults(self):
        with patch.dict(os.environ, {
            'MAX_LOGS_PER_TASK': 'abc',
            'MAX_LOGS_ON_DISK': '-1',
            'WAL_COMPACT_BATCH_SIZE': '0',
        }, clear=False):
            module = importlib.import_module('server.utils.logs')
            module = importlib.reload(module)

            self.assertEqual(200, module.MAX_LOGS_PER_TASK)
            self.assertEqual(20000, module.MAX_LOGS_ON_DISK)
            self.assertEqual(100, module.WAL_COMPACT_BATCH_SIZE)


if __name__ == '__main__':
    unittest.main()
