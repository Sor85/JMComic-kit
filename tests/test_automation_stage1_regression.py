"""
自动化阶段一回归测试。
覆盖状态映射、single-flight 与调度恢复关键路径。
"""

import importlib.util
import sys
import types
import unittest
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from server.state import (
    AUTO_TASK_DESIRED_DISABLED,
    AUTO_TASK_DESIRED_ENABLED,
    AUTO_TASK_RUNTIME_ERROR,
    AUTO_TASK_RUNTIME_IDLE,
    AUTO_TASK_RUNTIME_SCHEDULED,
    auto_execution_lock,
    auto_executions,
    auto_task_lock,
    auto_task_running_ids,
    auto_task_stop_flags,
    auto_task_stop_lock,
    auto_tasks,
    clear_auto_task_running,
    is_auto_task_stopped,
    normalize_auto_task_state,
    set_auto_task_stop_flag,
    try_mark_auto_task_running,
)


@contextmanager
def _patched_apscheduler_modules():
    apscheduler_pkg = types.ModuleType('apscheduler')
    apscheduler_schedulers_pkg = types.ModuleType('apscheduler.schedulers')
    apscheduler_schedulers_base_pkg = types.ModuleType('apscheduler.schedulers.base')
    apscheduler_triggers_pkg = types.ModuleType('apscheduler.triggers')
    apscheduler_triggers_cron_pkg = types.ModuleType('apscheduler.triggers.cron')

    class _FakeBaseScheduler:
        pass

    class _FakeCronTrigger:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    apscheduler_schedulers_base_pkg.BaseScheduler = _FakeBaseScheduler
    apscheduler_triggers_cron_pkg.CronTrigger = _FakeCronTrigger

    module_map = {
        'apscheduler': apscheduler_pkg,
        'apscheduler.schedulers': apscheduler_schedulers_pkg,
        'apscheduler.schedulers.base': apscheduler_schedulers_base_pkg,
        'apscheduler.triggers': apscheduler_triggers_pkg,
        'apscheduler.triggers.cron': apscheduler_triggers_cron_pkg,
    }
    original = {name: sys.modules.get(name) for name in module_map}
    try:
        sys.modules.update(module_map)
        yield
    finally:
        for name, previous in original.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


@contextmanager
def _patched_flask_module():
    flask_pkg = types.ModuleType('flask')

    class _FakeBlueprint:
        def __init__(self, _name, _import_name):
            self.name = _name
            self.import_name = _import_name

        def route(self, _rule, methods=None):
            def _decorator(func):
                return func

            return _decorator

    class _FakeArgs(dict):
        def get(self, key, default=None, type=None):
            value = super().get(key, default)
            if type is not None and value is not None:
                try:
                    return type(value)
                except (TypeError, ValueError):
                    return default
            return value

    class _FakeRequest:
        def __init__(self):
            self._json_data = {}
            self.args = _FakeArgs()

        def set_json_data(self, payload):
            self._json_data = payload

        def get_json(self, silent=True):
            return self._json_data

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def get_json(self):
            return self._payload

    def _fake_jsonify(payload):
        return _FakeResponse(payload)

    request_obj = _FakeRequest()
    flask_pkg.Blueprint = _FakeBlueprint
    flask_pkg.jsonify = _fake_jsonify
    flask_pkg.request = request_obj

    original = sys.modules.get('flask')
    try:
        sys.modules['flask'] = flask_pkg
        yield request_obj
    finally:
        if original is None:
            sys.modules.pop('flask', None)
        else:
            sys.modules['flask'] = original


@contextmanager
def _patched_automation_dependencies():
    automation_pkg = types.ModuleType('server.services.automation')
    automation_pkg.execute_auto_sync = lambda *_args, **_kwargs: None
    automation_pkg.schedule_task = lambda *_args, **_kwargs: True
    automation_pkg.unschedule_task = lambda *_args, **_kwargs: True

    validators_pkg = types.ModuleType('server.utils.validators')
    validators_pkg.validate_cron_expression = lambda _cron: (True, '')
    validators_pkg.validate_path_safety = lambda _path: True
    validators_pkg.validate_speed_limit = lambda _speed: (True, 0, '')

    logs_pkg = types.ModuleType('server.utils.logs')
    logs_pkg.add_log = lambda *_args, **_kwargs: None
    logs_pkg.get_logs = lambda *_args, **_kwargs: []

    sanitize_pkg = types.ModuleType('server.utils.sanitize')

    def _deep_strip_sensitive(payload):
        if isinstance(payload, dict):
            return {
                k: _deep_strip_sensitive(v)
                for k, v in payload.items()
                if 'password' not in k.lower()
            }
        if isinstance(payload, list):
            return [_deep_strip_sensitive(v) for v in payload]
        return payload

    sanitize_pkg.deep_strip_sensitive = _deep_strip_sensitive

    storage_pkg = types.ModuleType('server.utils.storage')
    storage_pkg.save_all_auto_executions = lambda *_args, **_kwargs: None
    storage_pkg.save_auto_tasks = lambda *_args, **_kwargs: None

    module_map = {
        'server.services.automation': automation_pkg,
        'server.utils.validators': validators_pkg,
        'server.utils.logs': logs_pkg,
        'server.utils.sanitize': sanitize_pkg,
        'server.utils.storage': storage_pkg,
    }
    original = {name: sys.modules.get(name) for name in module_map}

    try:
        sys.modules.update(module_map)
        yield
    finally:
        for name, previous in original.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _load_scheduler_module():
    scheduler_path = Path(__file__).resolve().parents[1] / 'server/services/automation/scheduler.py'
    with _patched_apscheduler_modules():
        spec = importlib.util.spec_from_file_location('automation_scheduler', scheduler_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def _load_automation_routes_module():
    routes_path = Path(__file__).resolve().parents[1] / 'server/routes/automation_routes.py'
    with _patched_apscheduler_modules(), _patched_flask_module() as request_obj, _patched_automation_dependencies():
        spec = importlib.util.spec_from_file_location('automation_routes_module', routes_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module, request_obj


scheduler_module = _load_scheduler_module()
automation_routes_module, automation_request = _load_automation_routes_module()


def _iso_utc_now():
    return datetime.now().astimezone().isoformat()


class _FakeJob:
    def __init__(self, next_run_time):
        self.next_run_time = next_run_time


class _FakeScheduler:
    def __init__(self):
        self.jobs = {}
        self.add_job_calls = []

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def remove_job(self, job_id):
        self.jobs.pop(job_id, None)

    def add_job(self, **kwargs):
        self.add_job_calls.append(kwargs)
        self.jobs[kwargs['id']] = _FakeJob(datetime.now() + timedelta(minutes=5))


class AutomationStageOneRegressionTests(unittest.TestCase):
    def setUp(self):
        self.running_backup = set(auto_task_running_ids)
        auto_task_running_ids.clear()
        with auto_task_stop_lock:
            self.stop_flags_backup = set(auto_task_stop_flags)
            auto_task_stop_flags.clear()
        self.request_args_backup = automation_request.args
        automation_request.args = automation_request.args.__class__()
        with auto_task_lock:
            self.auto_tasks_backup = deepcopy(auto_tasks)
            auto_tasks.clear()
        with auto_execution_lock:
            self.auto_executions_backup = deepcopy(auto_executions)
            auto_executions.clear()

    def tearDown(self):
        auto_task_running_ids.clear()
        auto_task_running_ids.update(self.running_backup)
        with auto_task_stop_lock:
            auto_task_stop_flags.clear()
            auto_task_stop_flags.update(self.stop_flags_backup)
        automation_request.args = self.request_args_backup
        with auto_task_lock:
            auto_tasks.clear()
            auto_tasks.update(self.auto_tasks_backup)
        with auto_execution_lock:
            auto_executions.clear()
            auto_executions.update(self.auto_executions_backup)

    def test_normalize_auto_task_state_from_legacy_status(self):
        normalized_running = normalize_auto_task_state({'id': 1, 'status': 'running'})
        normalized_stopped = normalize_auto_task_state({'id': 2, 'status': 'stopped'})

        self.assertEqual(normalized_running['desired_status'], AUTO_TASK_DESIRED_ENABLED)
        self.assertEqual(normalized_running['runtime_status'], AUTO_TASK_RUNTIME_IDLE)
        self.assertEqual(normalized_running['status'], 'running')
        self.assertIsNone(normalized_running['current_execution_id'])

        self.assertEqual(normalized_stopped['desired_status'], AUTO_TASK_DESIRED_DISABLED)
        self.assertEqual(normalized_stopped['runtime_status'], AUTO_TASK_RUNTIME_IDLE)
        self.assertEqual(normalized_stopped['status'], 'stopped')
        self.assertIsNone(normalized_stopped['current_execution_id'])

    def test_single_flight_running_marker(self):
        auto_task_id = 42
        clear_auto_task_running(auto_task_id)

        first = try_mark_auto_task_running(auto_task_id)
        second = try_mark_auto_task_running(auto_task_id)

        clear_auto_task_running(auto_task_id)
        third = try_mark_auto_task_running(auto_task_id)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(third)

    def test_schedule_task_respects_desired_status_disabled(self):
        scheduler = _FakeScheduler()
        auto_task = {
            'id': 100,
            'name': 'disabled-task',
            'cron': '*/10 * * * *',
            'desired_status': AUTO_TASK_DESIRED_DISABLED,
            'runtime_status': AUTO_TASK_RUNTIME_SCHEDULED,
            'next_run': '2099-01-01T00:00:00',
        }

        result = scheduler_module.schedule_task(scheduler, auto_task, lambda _task_id: None)

        self.assertFalse(result)
        self.assertEqual(auto_task['runtime_status'], AUTO_TASK_RUNTIME_IDLE)
        self.assertIsNone(auto_task['next_run'])
        self.assertEqual(auto_task['status'], 'stopped')
        self.assertEqual(len(scheduler.add_job_calls), 0)

    def test_schedule_task_sets_scheduler_guards_and_runtime(self):
        scheduler = _FakeScheduler()
        auto_task = {
            'id': 101,
            'name': 'enabled-task',
            'cron': '*/10 * * * *',
            'desired_status': AUTO_TASK_DESIRED_ENABLED,
            'runtime_status': AUTO_TASK_RUNTIME_IDLE,
            'next_run': None,
        }

        result = scheduler_module.schedule_task(scheduler, auto_task, lambda _task_id: None)

        self.assertTrue(result)
        self.assertEqual(len(scheduler.add_job_calls), 1)
        add_job_call = scheduler.add_job_calls[0]
        self.assertEqual(add_job_call['id'], 'auto_task_101')
        self.assertEqual(add_job_call['max_instances'], 1)
        self.assertTrue(add_job_call['coalesce'])
        self.assertEqual(auto_task['runtime_status'], AUTO_TASK_RUNTIME_SCHEDULED)
        self.assertEqual(auto_task['status'], 'running')
        self.assertIsNotNone(auto_task['next_run'])

    def test_schedule_auto_task_does_not_overwrite_desired_status_on_race(self):
        with auto_task_lock:
            auto_tasks[9200] = normalize_auto_task_state(
                {
                    'id': 9200,
                    'name': 'task-race',
                    'cron': '*/5 * * * *',
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'next_run': None,
                }
            )

        original_scheduler = automation_routes_module._scheduler
        original_schedule_task = automation_routes_module.schedule_task
        original_unschedule_task = automation_routes_module.unschedule_task
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks

        unschedule_calls = []

        def _fake_schedule_task(_scheduler, task_snapshot, _runner):
            task_snapshot['runtime_status'] = AUTO_TASK_RUNTIME_SCHEDULED
            task_snapshot['status'] = 'running'
            task_snapshot['next_run'] = '2099-01-01T00:00:00'
            with auto_task_lock:
                task = auto_tasks.get(task_snapshot['id'])
                if task:
                    task['desired_status'] = AUTO_TASK_DESIRED_DISABLED
                    task['runtime_status'] = AUTO_TASK_RUNTIME_IDLE
                    task['status'] = 'stopped'
                    task['next_run'] = None
            return True

        def _fake_unschedule_task(scheduler, task_id):
            unschedule_calls.append((scheduler, task_id))
            return True

        automation_routes_module._scheduler = object()
        automation_routes_module.schedule_task = _fake_schedule_task
        automation_routes_module.unschedule_task = _fake_unschedule_task
        automation_routes_module._persist_auto_tasks = lambda: None

        try:
            result = automation_routes_module.schedule_auto_task(9200)
        finally:
            automation_routes_module._scheduler = original_scheduler
            automation_routes_module.schedule_task = original_schedule_task
            automation_routes_module.unschedule_task = original_unschedule_task
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks

        self.assertFalse(result)
        with auto_task_lock:
            task = auto_tasks[9200]
            self.assertEqual(task['desired_status'], AUTO_TASK_DESIRED_DISABLED)
            self.assertEqual(task['runtime_status'], AUTO_TASK_RUNTIME_IDLE)
            self.assertEqual(task['status'], 'stopped')
            self.assertIsNone(task['next_run'])
        self.assertEqual(len(unschedule_calls), 1)
        self.assertEqual(unschedule_calls[0][1], 9200)

    def test_schedule_auto_task_does_not_overwrite_running_runtime_on_race(self):
        with auto_task_lock:
            auto_tasks[9201] = normalize_auto_task_state(
                {
                    'id': 9201,
                    'name': 'task-race-runtime',
                    'cron': '*/5 * * * *',
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        original_scheduler = automation_routes_module._scheduler
        original_schedule_task = automation_routes_module.schedule_task
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks

        def _fake_schedule_task(_scheduler, task_snapshot, _runner):
            task_snapshot['runtime_status'] = AUTO_TASK_RUNTIME_SCHEDULED
            task_snapshot['status'] = 'running'
            task_snapshot['next_run'] = '2099-01-01T00:00:00'
            with auto_task_lock:
                task = auto_tasks.get(task_snapshot['id'])
                if task:
                    task['runtime_status'] = 'running'
                    task['current_execution_id'] = 321
            return True

        automation_routes_module._scheduler = object()
        automation_routes_module.schedule_task = _fake_schedule_task
        automation_routes_module._persist_auto_tasks = lambda: None

        try:
            result = automation_routes_module.schedule_auto_task(9201)
        finally:
            automation_routes_module._scheduler = original_scheduler
            automation_routes_module.schedule_task = original_schedule_task
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks

        self.assertTrue(result)
        with auto_task_lock:
            task = auto_tasks[9201]
            self.assertEqual(task['runtime_status'], 'running')
            self.assertEqual(task['current_execution_id'], 321)
            self.assertEqual(task['next_run'], '2099-01-01T00:00:00')

    def test_recover_scheduled_auto_tasks_only_recover_enabled(self):
        with auto_task_lock:
            auto_tasks[1] = normalize_auto_task_state(
                {'id': 1, 'name': 'legacy-enabled', 'cron': '*/5 * * * *', 'status': 'running'}
            )
            auto_tasks[2] = normalize_auto_task_state(
                {'id': 2, 'name': 'legacy-disabled', 'cron': '*/5 * * * *', 'status': 'stopped'}
            )

        original_schedule_auto_task = automation_routes_module.schedule_auto_task
        called_task_ids = []

        def _fake_schedule_auto_task(task_id):
            called_task_ids.append(task_id)
            with auto_task_lock:
                task = auto_tasks.get(task_id)
                if task:
                    task['runtime_status'] = AUTO_TASK_RUNTIME_SCHEDULED
                    task['status'] = 'running'
            return True

        automation_routes_module.schedule_auto_task = _fake_schedule_auto_task
        try:
            recovered = automation_routes_module.recover_scheduled_auto_tasks()
        finally:
            automation_routes_module.schedule_auto_task = original_schedule_auto_task

        self.assertEqual(recovered, 1)
        self.assertEqual(called_task_ids, [1])
        self.assertEqual(auto_tasks[1]['desired_status'], AUTO_TASK_DESIRED_ENABLED)
        self.assertEqual(auto_tasks[1]['runtime_status'], AUTO_TASK_RUNTIME_SCHEDULED)
        self.assertEqual(auto_tasks[2]['desired_status'], AUTO_TASK_DESIRED_DISABLED)

    def test_create_auto_task_rejects_non_integer_batch_fields(self):
        automation_request.set_json_data(
            {
                'name': 't1',
                'username': 'u1',
                'password': 'p1',
                'cron': '*/10 * * * *',
                'download_dir': './download/',
                'batch_albums_count': 'abc',
                'batch_interval_minutes': 30,
            }
        )
        response, status_code = automation_routes_module.create_auto_task()
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '每批下载数量必须是整数')

        automation_request.set_json_data(
            {
                'name': 't2',
                'username': 'u2',
                'password': 'p2',
                'cron': '*/10 * * * *',
                'download_dir': './download/',
                'batch_albums_count': 50,
                'batch_interval_minutes': 'not-int',
            }
        )
        response, status_code = automation_routes_module.create_auto_task()
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '批次间隔必须是整数')

    def test_create_auto_task_rejects_non_boolean_run_now(self):
        automation_request.set_json_data(
            {
                'name': 't3',
                'username': 'u3',
                'password': 'p3',
                'cron': '*/10 * * * *',
                'download_dir': './download/',
                'run_now': 'false',
            }
        )
        response, status_code = automation_routes_module.create_auto_task()
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'run_now 必须是布尔值')

    def test_create_auto_task_rejects_boolean_speed_limit(self):
        automation_request.set_json_data(
            {
                'name': 't4',
                'username': 'u4',
                'password': 'p4',
                'cron': '*/10 * * * *',
                'download_dir': './download/',
                'speed_limit': False,
            }
        )
        response, status_code = automation_routes_module.create_auto_task()
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '速度限制参数错误: 速度值必须为数字')

    def test_create_auto_task_rejects_non_object_json(self):
        automation_request.set_json_data(['bad'])
        response, status_code = automation_routes_module.create_auto_task()
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '请求体必须是 JSON 对象')

    def test_update_auto_task_rejects_non_integer_batch_fields(self):
        with auto_task_lock:
            auto_tasks[9001] = normalize_auto_task_state(
                {
                    'id': 9001,
                    'name': 'task-9001',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'stopped',
                    'desired_status': AUTO_TASK_DESIRED_DISABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        automation_request.set_json_data(
            {
                'batch_albums_count': 'abc',
            }
        )
        response, status_code = automation_routes_module.update_auto_task(9001)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '每批下载数量必须是整数')

        automation_request.set_json_data(
            {
                'batch_interval_minutes': 'oops',
            }
        )
        response, status_code = automation_routes_module.update_auto_task(9001)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '批次间隔必须是整数')

    def test_update_auto_task_rejects_boolean_speed_limit(self):
        with auto_task_lock:
            auto_tasks[9004] = normalize_auto_task_state(
                {
                    'id': 9004,
                    'name': 'task-9004',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'status': 'stopped',
                    'desired_status': AUTO_TASK_DESIRED_DISABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        automation_request.set_json_data({'speed_limit': False})
        response, status_code = automation_routes_module.update_auto_task(9004)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '速度限制参数错误: 速度值必须为数字')

    def test_update_auto_task_rejects_invalid_desired_status(self):
        with auto_task_lock:
            auto_tasks[9002] = normalize_auto_task_state(
                {
                    'id': 9002,
                    'name': 'task-9002',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'stopped',
                    'desired_status': AUTO_TASK_DESIRED_DISABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        automation_request.set_json_data({'desired_status': 'invalid'})
        response, status_code = automation_routes_module.update_auto_task(9002)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'desired_status 必须是 enabled 或 disabled')

    def test_update_auto_task_rejects_non_object_json(self):
        with auto_task_lock:
            auto_tasks[9003] = normalize_auto_task_state(
                {
                    'id': 9003,
                    'name': 'task-9003',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'status': 'stopped',
                    'desired_status': AUTO_TASK_DESIRED_DISABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        automation_request.set_json_data(['bad'])
        response, status_code = automation_routes_module.update_auto_task(9003)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], '请求体必须是 JSON 对象')

    def test_update_auto_task_rolls_back_when_schedule_fails_without_concurrent_change(self):
        with auto_task_lock:
            auto_tasks[9300] = normalize_auto_task_state(
                {
                    'id': 9300,
                    'name': 'task-9300',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        original_schedule_auto_task = automation_routes_module.schedule_auto_task
        original_unschedule_task = automation_routes_module.unschedule_task
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks
        original_validate_cron_expression = automation_routes_module.validate_cron_expression
        original_validate_path_safety = automation_routes_module.validate_path_safety

        persisted = []

        automation_routes_module.schedule_auto_task = lambda *_args, **_kwargs: False
        automation_routes_module.unschedule_task = lambda *_args, **_kwargs: True

        def _fake_persist_auto_tasks():
            with auto_task_lock:
                persisted.append(deepcopy(auto_tasks.get(9300)))

        automation_routes_module._persist_auto_tasks = _fake_persist_auto_tasks
        automation_routes_module.validate_cron_expression = lambda _cron: (True, '')
        automation_routes_module.validate_path_safety = lambda _path: True

        try:
            automation_request.set_json_data({'name': 'updated-name', 'desired_status': AUTO_TASK_DESIRED_ENABLED})
            response, status_code = automation_routes_module.update_auto_task(9300)
            self.assertEqual(status_code, 500)
            self.assertEqual(response.get_json()['error'], '任务更新成功，但调度失败')
            with auto_task_lock:
                task = auto_tasks[9300]
                self.assertEqual(task['name'], 'task-9300')
            self.assertTrue(persisted)
            self.assertEqual(persisted[-1]['name'], 'task-9300')
        finally:
            automation_routes_module.schedule_auto_task = original_schedule_auto_task
            automation_routes_module.unschedule_task = original_unschedule_task
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks
            automation_routes_module.validate_cron_expression = original_validate_cron_expression
            automation_routes_module.validate_path_safety = original_validate_path_safety

    def test_update_auto_task_returns_409_when_schedule_fails_with_concurrent_change(self):
        with auto_task_lock:
            auto_tasks[9301] = normalize_auto_task_state(
                {
                    'id': 9301,
                    'name': 'task-9301',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        original_schedule_auto_task = automation_routes_module.schedule_auto_task
        original_unschedule_task = automation_routes_module.unschedule_task
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks
        original_validate_cron_expression = automation_routes_module.validate_cron_expression
        original_validate_path_safety = automation_routes_module.validate_path_safety

        def _fake_schedule_auto_task(task_id):
            if task_id == 9301:
                with auto_task_lock:
                    task = auto_tasks.get(task_id)
                    if task:
                        task['name'] = 'concurrent-write'
                return False
            return True

        automation_routes_module.schedule_auto_task = _fake_schedule_auto_task
        automation_routes_module.unschedule_task = lambda *_args, **_kwargs: True
        automation_routes_module._persist_auto_tasks = lambda: None
        automation_routes_module.validate_cron_expression = lambda _cron: (True, '')
        automation_routes_module.validate_path_safety = lambda _path: True

        try:
            automation_request.set_json_data({'name': 'updated-name', 'desired_status': AUTO_TASK_DESIRED_ENABLED})
            response, status_code = automation_routes_module.update_auto_task(9301)
            self.assertEqual(status_code, 409)
            self.assertEqual(response.get_json()['error'], '任务更新失败，检测到并发修改，请重试')
            with auto_task_lock:
                task = auto_tasks[9301]
                self.assertEqual(task['name'], 'concurrent-write')
        finally:
            automation_routes_module.schedule_auto_task = original_schedule_auto_task
            automation_routes_module.unschedule_task = original_unschedule_task
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks
            automation_routes_module.validate_cron_expression = original_validate_cron_expression
            automation_routes_module.validate_path_safety = original_validate_path_safety

    def test_update_auto_task_preserves_runtime_fields_on_schedule_failure(self):
        with auto_task_lock:
            auto_tasks[9302] = normalize_auto_task_state(
                {
                    'id': 9302,
                    'name': 'task-9302',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        original_schedule_auto_task = automation_routes_module.schedule_auto_task
        original_unschedule_task = automation_routes_module.unschedule_task
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks
        original_validate_cron_expression = automation_routes_module.validate_cron_expression
        original_validate_path_safety = automation_routes_module.validate_path_safety

        def _fake_schedule_auto_task(task_id):
            if task_id == 9302:
                with auto_task_lock:
                    task = auto_tasks.get(task_id)
                    if task:
                        task['runtime_status'] = 'running'
                        task['current_execution_id'] = 777
                        task['next_run'] = '2099-01-01T00:00:00'
                        task['status'] = 'running'
                return False
            return True

        automation_routes_module.schedule_auto_task = _fake_schedule_auto_task
        automation_routes_module.unschedule_task = lambda *_args, **_kwargs: True
        automation_routes_module._persist_auto_tasks = lambda: None
        automation_routes_module.validate_cron_expression = lambda _cron: (True, '')
        automation_routes_module.validate_path_safety = lambda _path: True

        try:
            automation_request.set_json_data({'name': 'updated-name', 'desired_status': AUTO_TASK_DESIRED_ENABLED})
            response, status_code = automation_routes_module.update_auto_task(9302)
            self.assertEqual(status_code, 500)
            self.assertEqual(response.get_json()['error'], '任务更新成功，但调度失败')
            with auto_task_lock:
                task = auto_tasks[9302]
                self.assertEqual(task['name'], 'task-9302')
                self.assertEqual(task['runtime_status'], 'running')
                self.assertEqual(task['current_execution_id'], 777)
                self.assertEqual(task['next_run'], '2099-01-01T00:00:00')
        finally:
            automation_routes_module.schedule_auto_task = original_schedule_auto_task
            automation_routes_module.unschedule_task = original_unschedule_task
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks
            automation_routes_module.validate_cron_expression = original_validate_cron_expression
            automation_routes_module.validate_path_safety = original_validate_path_safety

    def test_create_auto_task_response_is_sanitized(self):
        original_get_next_auto_task_id = automation_routes_module.get_next_auto_task_id
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks
        original_validate_cron_expression = automation_routes_module.validate_cron_expression
        original_validate_path_safety = automation_routes_module.validate_path_safety

        automation_routes_module.get_next_auto_task_id = lambda: 3001
        automation_routes_module._persist_auto_tasks = lambda: None
        automation_routes_module.validate_cron_expression = lambda _cron: (True, '')
        automation_routes_module.validate_path_safety = lambda _path: True

        try:
            automation_request.set_json_data(
                {
                    'name': 'task-sanitized',
                    'username': 'user',
                    'password': 'plain-password',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                }
            )
            response = automation_routes_module.create_auto_task()
            body = response.get_json()
            self.assertNotIn('password', body)
        finally:
            automation_routes_module.get_next_auto_task_id = original_get_next_auto_task_id
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks
            automation_routes_module.validate_cron_expression = original_validate_cron_expression
            automation_routes_module.validate_path_safety = original_validate_path_safety

    def test_run_auto_task_now_clears_stop_flag(self):
        with auto_task_lock:
            auto_tasks[9100] = normalize_auto_task_state(
                {
                    'id': 9100,
                    'name': 'task-run-now',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        set_auto_task_stop_flag(9100)
        self.assertTrue(is_auto_task_stopped(9100))

        class _FakeThread:
            def __init__(self, target=None, args=()):
                self.target = target
                self.args = args
                self.daemon = False

            def start(self):
                return None

        original_thread = automation_routes_module.threading.Thread
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks
        automation_routes_module.threading.Thread = _FakeThread
        automation_routes_module._persist_auto_tasks = lambda: None

        try:
            automation_request.set_json_data({})
            response = automation_routes_module.run_auto_task_now(9100)
            body = response.get_json()
            self.assertIn('task', body)
            self.assertFalse(is_auto_task_stopped(9100))
        finally:
            automation_routes_module.threading.Thread = original_thread
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks

    def test_update_auto_task_enable_clears_stop_flag(self):
        with auto_task_lock:
            auto_tasks[9102] = normalize_auto_task_state(
                {
                    'id': 9102,
                    'name': 'task-enable-clear-flag',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'status': 'stopped',
                    'desired_status': AUTO_TASK_DESIRED_DISABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        set_auto_task_stop_flag(9102)
        self.assertTrue(is_auto_task_stopped(9102))

        original_schedule_auto_task = automation_routes_module.schedule_auto_task
        original_validate_cron_expression = automation_routes_module.validate_cron_expression
        original_validate_path_safety = automation_routes_module.validate_path_safety
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks

        automation_routes_module.schedule_auto_task = lambda *_args, **_kwargs: True
        automation_routes_module.validate_cron_expression = lambda _cron: (True, '')
        automation_routes_module.validate_path_safety = lambda _path: True
        automation_routes_module._persist_auto_tasks = lambda: None

        try:
            automation_request.set_json_data({'desired_status': AUTO_TASK_DESIRED_ENABLED})
            response = automation_routes_module.update_auto_task(9102)
            body = response.get_json()
            self.assertEqual(body['message'], '任务已更新')
            self.assertFalse(is_auto_task_stopped(9102))
        finally:
            automation_routes_module.schedule_auto_task = original_schedule_auto_task
            automation_routes_module.validate_cron_expression = original_validate_cron_expression
            automation_routes_module.validate_path_safety = original_validate_path_safety
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks

    def test_run_auto_task_now_rolls_back_when_thread_start_fails(self):
        with auto_task_lock:
            auto_tasks[9101] = normalize_auto_task_state(
                {
                    'id': 9101,
                    'name': 'task-thread-fail',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        class _FailThread:
            def __init__(self, target=None, args=()):
                self.target = target
                self.args = args
                self.daemon = False

            def start(self):
                raise RuntimeError('start failed')

        original_thread = automation_routes_module.threading.Thread
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks
        automation_routes_module.threading.Thread = _FailThread
        automation_routes_module._persist_auto_tasks = lambda: None

        try:
            automation_request.set_json_data({})
            response, status_code = automation_routes_module.run_auto_task_now(9101)
            self.assertEqual(status_code, 500)
            self.assertEqual(response.get_json()['error'], '任务启动失败')
            with auto_task_lock:
                task = auto_tasks[9101]
                self.assertEqual(task.get('runtime_status'), AUTO_TASK_RUNTIME_IDLE)
                self.assertEqual(task.get('status'), 'running')
            self.assertFalse(is_auto_task_stopped(9101))
            self.assertFalse(9101 in auto_task_running_ids)
        finally:
            automation_routes_module.threading.Thread = original_thread
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks

    def test_stop_auto_task_rolls_back_when_unschedule_raises(self):
        with auto_task_lock:
            auto_tasks[9110] = normalize_auto_task_state(
                {
                    'id': 9110,
                    'name': 'task-stop-fail',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': '2099-01-01T00:00:00',
                }
            )

        original_scheduler = automation_routes_module._scheduler
        original_unschedule_task = automation_routes_module.unschedule_task
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks

        persisted = []

        automation_routes_module._scheduler = object()
        automation_routes_module.unschedule_task = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError('unschedule failed')
        )

        def _fake_persist_auto_tasks():
            with auto_task_lock:
                persisted.append(deepcopy(auto_tasks.get(9110)))

        automation_routes_module._persist_auto_tasks = _fake_persist_auto_tasks

        try:
            response, status_code = automation_routes_module.stop_auto_task(9110)
            self.assertEqual(status_code, 500)
            self.assertEqual(response.get_json()['error'], '任务停止失败，调度取消异常')
            with auto_task_lock:
                task = auto_tasks[9110]
                self.assertEqual(task['desired_status'], AUTO_TASK_DESIRED_ENABLED)
                self.assertEqual(task['runtime_status'], AUTO_TASK_RUNTIME_IDLE)
                self.assertEqual(task['next_run'], '2099-01-01T00:00:00')
            self.assertFalse(is_auto_task_stopped(9110))
            self.assertTrue(persisted)
        finally:
            automation_routes_module._scheduler = original_scheduler
            automation_routes_module.unschedule_task = original_unschedule_task
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks

    def test_delete_auto_task_returns_500_when_unschedule_raises(self):
        with auto_task_lock:
            auto_tasks[9111] = normalize_auto_task_state(
                {
                    'id': 9111,
                    'name': 'task-delete-fail',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        original_scheduler = automation_routes_module._scheduler
        original_unschedule_task = automation_routes_module.unschedule_task

        automation_routes_module._scheduler = object()
        automation_routes_module.unschedule_task = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError('unschedule failed')
        )

        try:
            response, status_code = automation_routes_module.delete_auto_task(9111)
            self.assertEqual(status_code, 500)
            self.assertEqual(response.get_json()['error'], '任务删除失败，调度取消异常')
            with auto_task_lock:
                self.assertIn(9111, auto_tasks)
        finally:
            automation_routes_module._scheduler = original_scheduler
            automation_routes_module.unschedule_task = original_unschedule_task

    def test_run_auto_sync_task_sets_error_when_executor_raises(self):
        with auto_task_lock:
            auto_tasks[9401] = normalize_auto_task_state(
                {
                    'id': 9401,
                    'name': 'task-executor-fail',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'speed_limit': 0,
                    'client_impl': 'api',
                    'image_suffix': '',
                    'dir_rule': 'Aauthoroname/Pindextitle',
                    'batch_albums_count': 50,
                    'batch_interval_minutes': 30,
                    'compression': {},
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': '2099-01-01T00:00:00',
                }
            )

        original_execute_auto_sync = automation_routes_module.execute_auto_sync
        original_persist_auto_tasks = automation_routes_module._persist_auto_tasks
        original_add_log = automation_routes_module.add_log

        persisted = []
        logs = []

        def _fake_execute_auto_sync(*_args, **_kwargs):
            raise RuntimeError('boom')

        def _fake_persist_auto_tasks():
            with auto_task_lock:
                persisted.append(deepcopy(auto_tasks.get(9401)))

        def _fake_add_log(*args, **kwargs):
            logs.append((args, kwargs))

        automation_routes_module.execute_auto_sync = _fake_execute_auto_sync
        automation_routes_module._persist_auto_tasks = _fake_persist_auto_tasks
        automation_routes_module.add_log = _fake_add_log

        try:
            automation_routes_module.run_auto_sync_task(9401, force_run=True, already_marked=False)
            with auto_task_lock:
                task = auto_tasks[9401]
                self.assertEqual(task.get('runtime_status'), AUTO_TASK_RUNTIME_ERROR)
                self.assertEqual(task.get('status'), 'running')
                self.assertIsNone(task.get('next_run'))
            self.assertTrue(persisted)
            self.assertFalse(9401 in auto_task_running_ids)
            self.assertTrue(logs)
        finally:
            automation_routes_module.execute_auto_sync = original_execute_auto_sync
            automation_routes_module._persist_auto_tasks = original_persist_auto_tasks
            automation_routes_module.add_log = original_add_log

    def test_get_auto_task_executions_handles_timezone_aware_start_time(self):
        with auto_task_lock:
            auto_tasks[9501] = normalize_auto_task_state(
                {
                    'id': 9501,
                    'name': 'task-timezone-aware',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        with auto_execution_lock:
            auto_executions[15001] = {
                'id': 15001,
                'auto_task_id': 9501,
                'start_time': _iso_utc_now(),
            }

        automation_request.args = automation_request.args.__class__({'time_range': '1', 'limit': '20'})
        response = automation_routes_module.get_auto_task_executions(9501)
        body = response.get_json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['id'], 15001)

    def test_get_auto_task_executions_rejects_out_of_range_params(self):
        with auto_task_lock:
            auto_tasks[9502] = normalize_auto_task_state(
                {
                    'id': 9502,
                    'name': 'task-range-check',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        automation_request.args = automation_request.args.__class__({'time_range': 'abc'})
        response, status_code = automation_routes_module.get_auto_task_executions(9502)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'time_range 必须是整数')

        automation_request.args = automation_request.args.__class__({'time_range': '0'})
        response, status_code = automation_routes_module.get_auto_task_executions(9502)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'time_range 必须大于 0')

        automation_request.args = automation_request.args.__class__({'time_range': str(24 * 31 + 1)})
        response, status_code = automation_routes_module.get_auto_task_executions(9502)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'time_range 超出允许范围')

        automation_request.args = automation_request.args.__class__({'limit': 'abc'})
        response, status_code = automation_routes_module.get_auto_task_executions(9502)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'limit 必须是整数')

        automation_request.args = automation_request.args.__class__({'limit': '0'})
        response, status_code = automation_routes_module.get_auto_task_executions(9502)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'limit 必须大于 0')

    def test_get_auto_task_executions_caps_limit(self):
        with auto_task_lock:
            auto_tasks[9503] = normalize_auto_task_state(
                {
                    'id': 9503,
                    'name': 'task-limit-cap',
                    'username': 'user',
                    'password': 'pass',
                    'cron': '*/10 * * * *',
                    'download_dir': './download/',
                    'status': 'running',
                    'desired_status': AUTO_TASK_DESIRED_ENABLED,
                    'runtime_status': AUTO_TASK_RUNTIME_IDLE,
                    'current_execution_id': None,
                    'next_run': None,
                }
            )

        with auto_execution_lock:
            for i in range(250):
                auto_executions[17000 + i] = {
                    'id': 17000 + i,
                    'auto_task_id': 9503,
                    'start_time': _iso_utc_now(),
                }

        automation_request.args = automation_request.args.__class__({'limit': '999'})
        response = automation_routes_module.get_auto_task_executions(9503)
        body = response.get_json()
        self.assertEqual(len(body), 200)

    def test_get_execution_detail_handles_non_iterable_downloaded_task_ids(self):
        with auto_execution_lock:
            auto_executions[17999] = {
                'id': 17999,
                'auto_task_id': 1,
                'status': 'completed',
                'downloaded_task_ids': 123,
            }

        response = automation_routes_module.get_execution_detail(17999)
        body = response.get_json()
        self.assertEqual(body['execution']['id'], 17999)
        self.assertEqual(body['related_tasks'], [])

    def test_get_execution_logs_rejects_non_integer_limit(self):
        with auto_execution_lock:
            auto_executions[18000] = {
                'id': 18000,
                'auto_task_id': 1,
                'status': 'completed',
            }

        automation_request.args = automation_request.args.__class__({'limit': 'abc'})
        response, status_code = automation_routes_module.get_execution_logs(18000)
        self.assertEqual(status_code, 400)
        self.assertEqual(response.get_json()['error'], 'limit 必须是整数')

    def test_get_execution_logs_formats_entries_with_missing_fields(self):
        with auto_execution_lock:
            auto_executions[18001] = {
                'id': 18001,
                'auto_task_id': 1,
                'status': 'completed',
            }

        original_get_logs = automation_routes_module.get_logs
        automation_routes_module.get_logs = lambda *_args, **_kwargs: [
            {'message': 'ok'},
            {'timestamp': '2026-02-19T12:34:56', 'level': 'success'},
            {'timestamp': 'bad-ts', 'level': 'info', 'message': 'edge'},
        ]

        try:
            automation_request.args = automation_request.args.__class__({'limit': '3'})
            response = automation_routes_module.get_execution_logs(18001)
            body = response.get_json()
            self.assertEqual(len(body), 3)
            self.assertIn('ok', body[-1])
        finally:
            automation_routes_module.get_logs = original_get_logs

    def test_delete_execution_keeps_memory_when_persist_fails(self):
        with auto_execution_lock:
            auto_executions[16001] = {
                'id': 16001,
                'auto_task_id': 1,
                'status': 'completed',
            }

        original_save_all_auto_executions = automation_routes_module.save_all_auto_executions
        automation_routes_module.save_all_auto_executions = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError('persist failed')
        )

        try:
            response, status_code = automation_routes_module.delete_execution(16001)
            self.assertEqual(status_code, 500)
            self.assertEqual(response.get_json()['error'], '执行记录删除失败，持久化未完成')
            with auto_execution_lock:
                self.assertIn(16001, auto_executions)
        finally:
            automation_routes_module.save_all_auto_executions = original_save_all_auto_executions


if __name__ == '__main__':
    unittest.main()
