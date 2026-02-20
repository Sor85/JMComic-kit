"""
日志持久化回归测试。
覆盖重启恢复与高日志量场景下的数据保留行为。
"""

import importlib
import os
import tempfile
import unittest
from copy import deepcopy

logs_module = importlib.import_module('server.utils.logs')


class LogsPersistenceRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_dir = logs_module.DATA_DIR
        self.original_logs_file = logs_module.LOGS_FILE
        self.original_logs_wal_file = logs_module.LOGS_WAL_FILE
        self.original_max_logs = logs_module.max_logs
        self.original_max_logs_per_task = logs_module.MAX_LOGS_PER_TASK
        self.original_max_logs_on_disk = logs_module.MAX_LOGS_ON_DISK
        self.original_wal_compact_batch_size = logs_module.WAL_COMPACT_BATCH_SIZE
        self.original_last_log_id = logs_module._last_log_id
        self.original_pending_wal_entries = logs_module._pending_wal_entries
        self.original_logs_snapshot = deepcopy(logs_module.logs)

        logs_module.DATA_DIR = self.temp_dir.name
        logs_module.LOGS_FILE = os.path.join(self.temp_dir.name, 'logs.json')
        logs_module.LOGS_WAL_FILE = os.path.join(self.temp_dir.name, 'logs.wal.jsonl')
        logs_module.max_logs = 1000
        logs_module.MAX_LOGS_PER_TASK = 200
        logs_module.MAX_LOGS_ON_DISK = 20000
        logs_module.WAL_COMPACT_BATCH_SIZE = 100
        logs_module._last_log_id = None
        logs_module._pending_wal_entries = 0
        logs_module.logs.clear()

    def tearDown(self):
        logs_module.logs.clear()
        logs_module.logs.extend(self.original_logs_snapshot)
        logs_module.DATA_DIR = self.original_data_dir
        logs_module.LOGS_FILE = self.original_logs_file
        logs_module.LOGS_WAL_FILE = self.original_logs_wal_file
        logs_module.max_logs = self.original_max_logs
        logs_module.MAX_LOGS_PER_TASK = self.original_max_logs_per_task
        logs_module.MAX_LOGS_ON_DISK = self.original_max_logs_on_disk
        logs_module.WAL_COMPACT_BATCH_SIZE = self.original_wal_compact_batch_size
        logs_module._last_log_id = self.original_last_log_id
        logs_module._pending_wal_entries = self.original_pending_wal_entries
        self.temp_dir.cleanup()

    def test_add_log_persists_without_manual_save(self):
        logs_module.add_log(101, 'info', 'persist-me')

        logs_module.logs.clear()
        loaded = logs_module.load_logs()

        self.assertTrue(
            any(
                item.get('task_id') == 101 and item.get('message') == 'persist-me'
                for item in loaded
            )
        )

    def test_memory_trim_does_not_drop_persistent_history(self):
        logs_module.max_logs = 3
        for idx in range(1, 6):
            logs_module.add_log(202, 'info', f'log-{idx}')

        in_memory_count = sum(1 for item in logs_module.logs if item.get('task_id') == 202)
        persisted = logs_module.load_logs()
        persisted_count = sum(1 for item in persisted if item.get('task_id') == 202)

        self.assertEqual(3, in_memory_count)
        self.assertEqual(5, persisted_count)

    def test_clear_logs_updates_persistent_storage(self):
        logs_module.add_log(303, 'info', 'will-be-cleared')
        self.assertTrue(logs_module.load_logs())

        logs_module.clear_logs()

        self.assertEqual([], logs_module.load_logs())

    def test_delete_task_logs_removes_only_target_task_from_disk(self):
        logs_module.add_log(1, 'info', 'task-1')
        logs_module.add_log(2, 'info', 'task-2')

        logs_module.delete_task_logs(1)
        loaded = logs_module.load_logs()

        self.assertFalse(any(item.get('task_id') == 1 for item in loaded))
        self.assertTrue(any(item.get('task_id') == 2 for item in loaded))

    def test_per_task_limit_applies_on_disk(self):
        logs_module.MAX_LOGS_PER_TASK = 3
        for idx in range(1, 8):
            logs_module.add_log(404, 'info', f'pt-{idx}')

        loaded = logs_module.load_logs()
        task_logs = [item for item in loaded if item.get('task_id') == 404]

        self.assertEqual(3, len(task_logs))
        self.assertEqual(['pt-7', 'pt-6', 'pt-5'], [item.get('message') for item in task_logs])

    def test_global_disk_limit_keeps_latest(self):
        logs_module.MAX_LOGS_ON_DISK = 5
        logs_module.MAX_LOGS_PER_TASK = 20

        for idx in range(1, 9):
            task_id = 1 if idx % 2 else 2
            logs_module.add_log(task_id, 'info', f'g-{idx}')

        loaded = logs_module.load_logs()

        self.assertEqual(5, len(loaded))
        self.assertEqual(['g-8', 'g-7', 'g-6', 'g-5', 'g-4'], [item.get('message') for item in loaded])

    def test_add_log_raises_when_wal_write_fails(self):
        original_append = logs_module._append_wal_entry

        def _raise_write_error(_entry):
            raise OSError('disk full')

        logs_module._append_wal_entry = _raise_write_error
        try:
            with self.assertRaises(OSError):
                logs_module.add_log(909, 'error', 'should-fail')
        finally:
            logs_module._append_wal_entry = original_append

        loaded = logs_module.load_logs()
        self.assertFalse(any(item.get('message') == 'should-fail' for item in loaded))

    def test_wal_compaction_applies_retention(self):
        logs_module.MAX_LOGS_PER_TASK = 2
        logs_module.MAX_LOGS_ON_DISK = 3
        logs_module.WAL_COMPACT_BATCH_SIZE = 3

        logs_module.add_log(1, 'info', 'a1')
        logs_module.add_log(1, 'info', 'a2')
        logs_module.add_log(1, 'info', 'a3')
        logs_module.add_log(2, 'info', 'b1')

        loaded = logs_module.load_logs()

        self.assertEqual(3, len(loaded))
        self.assertEqual(['b1', 'a3', 'a2'], [item.get('message') for item in loaded])

    def test_load_logs_compacts_wal_without_duplicates(self):
        logs_module.WAL_COMPACT_BATCH_SIZE = 9999

        logs_module.add_log(7, 'info', 'keep-once')
        first_loaded = logs_module.load_logs()
        second_loaded = logs_module.load_logs()

        self.assertEqual(1, len(first_loaded))
        self.assertEqual(1, len(second_loaded))
        self.assertEqual('keep-once', second_loaded[0].get('message'))


if __name__ == '__main__':
    unittest.main()
