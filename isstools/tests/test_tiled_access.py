from datetime import datetime
import sys
from threading import Event
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from tiled.utils import OneShotCachedMap

from isstools import tiled_access
from isstools.tiled_access import search_proposal_runs, wait_for_completed_run


class Catalog:
    def __init__(self, runs=(), subscription=None):
        self.runs = list(runs)
        self.queries = []
        self.subscription = subscription
        self.subscribed = False

    def __getitem__(self, uid):
        result = self.runs.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def search(self, query):
        self.queries.append(query)
        return self

    def subscribe(self):
        self.subscribed = True
        return self.subscription


class Run:
    def __init__(self, stop):
        self.metadata = {'start': {'uid': 'abc'}, 'stop': stop}
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1


class CallbackRegistry:
    def add_callback(self, callback):
        self.callback = callback


class Subscription:
    def __init__(self, action=None):
        self.child_created = CallbackRegistry()
        self.child_metadata_updated = CallbackRegistry()
        self.stream_closed = CallbackRegistry()
        self.action = action
        self.disconnected = Event()
        self.starts = []

    def start(self, start=None):
        self.starts.append(start)
        self._connected_event.set()
        if self.action:
            self.action(self)
        self.disconnected.wait(2)

    def disconnect(self, wait=True):
        assert wait is False
        self.disconnected.set()

    def emit(self, key='abc', stop=True, created=False):
        registry = self.child_created if created else self.child_metadata_updated
        registry.callback(SimpleNamespace(key=key, metadata={'stop': {'run_start': key}} if stop else {}))


def test_completed_run_does_not_subscribe():
    completed = Run({'run_start': 'abc'})
    catalog = Catalog([completed])
    assert wait_for_completed_run(catalog, 'abc') is completed
    assert not catalog.subscribed


@pytest.mark.parametrize('initial', [KeyError('abc'), Run(None)])
def test_waits_for_matching_stop_notification(initial):
    completed = Run({'run_start': 'abc'})
    subscription = Subscription(lambda sub: (
        sub.emit(key='other'), sub.emit(stop=False, created=True), sub.emit(stop=False), sub.emit()
    ))
    catalog = Catalog([initial, KeyError('abc'), completed], subscription)
    assert wait_for_completed_run(catalog, 'abc', timeout=1) is completed
    assert subscription.starts == [None]
    assert subscription.disconnected.wait(1)


def test_run_finishes_during_connection():
    completed = Run({'run_start': 'abc'})
    subscription = Subscription()
    catalog = Catalog([KeyError('abc'), completed], subscription)
    assert wait_for_completed_run(catalog, 'abc', timeout=1) is completed
    assert subscription.disconnected.wait(1)


def test_run_created_already_complete():
    completed = Run({'run_start': 'abc'})
    subscription = Subscription(lambda sub: sub.emit(created=True))
    catalog = Catalog([KeyError('abc'), KeyError('abc'), completed], subscription)
    assert wait_for_completed_run(catalog, 'abc', timeout=1) is completed


def test_unrelated_notifications_timeout():
    subscription = Subscription(lambda sub: (sub.emit(key='other'), sub.emit(stop=False)))
    catalog = Catalog([KeyError('abc'), KeyError('abc')], subscription)
    with pytest.raises(TimeoutError, match='abc'):
        wait_for_completed_run(catalog, 'abc', timeout=0.05)
    assert subscription.disconnected.wait(1)


def test_websocket_connection_error():
    def fail(subscription):
        raise PermissionError('websocket denied')
    subscription = Subscription(fail)
    catalog = Catalog([KeyError('abc'), KeyError('abc')], subscription)
    with pytest.raises(PermissionError, match='websocket denied'):
        wait_for_completed_run(catalog, 'abc', timeout=1)
    assert subscription.disconnected.wait(1)


def test_timeout_when_connection_never_finishes():
    class StalledSubscription(Subscription):
        def start(self, start=None):
            self.disconnected.wait(2)
    subscription = StalledSubscription()
    catalog = Catalog([KeyError('abc'), KeyError('abc')], subscription)
    with pytest.raises(TimeoutError, match='abc'):
        wait_for_completed_run(catalog, 'abc', timeout=0.05)
    assert subscription.disconnected.wait(1)


def test_timeout_does_not_wait_for_blocked_disconnect():
    release = Event()
    entered = Event()

    class BlockingSubscription(Subscription):
        def start(self, start=None):
            release.wait(2)

        def disconnect(self, wait=True):
            entered.set()
            release.wait(2)
            super().disconnect(wait=wait)

    subscription = BlockingSubscription()
    catalog = Catalog([KeyError('abc'), KeyError('abc')], subscription)
    try:
        with pytest.raises(TimeoutError, match='abc'):
            wait_for_completed_run(catalog, 'abc', timeout=0.05)
        assert entered.wait(1)
        assert not subscription.disconnected.is_set()
    finally:
        release.set()
    assert subscription.disconnected.wait(1)


def test_lookup_failure_disconnects():
    subscription = Subscription()
    catalog = Catalog([KeyError('abc'), PermissionError('read denied')], subscription)
    with pytest.raises(PermissionError, match='read denied'):
        wait_for_completed_run(catalog, 'abc')
    assert subscription.disconnected.wait(1)


def test_stream_close_reports_failure():
    subscription = Subscription(lambda sub: sub.stream_closed.callback(sub))
    catalog = Catalog([KeyError('abc'), KeyError('abc')], subscription)
    with pytest.raises(RuntimeError, match='subscription closed'):
        wait_for_completed_run(catalog, 'abc', timeout=1)
    assert subscription.disconnected.wait(1)


def test_missing_stop_after_notification_fails():
    subscription = Subscription(lambda sub: sub.emit())
    catalog = Catalog([KeyError('abc'), KeyError('abc'), Run(None)], subscription)
    with pytest.raises(RuntimeError, match='no persisted stop'):
        wait_for_completed_run(catalog, 'abc', timeout=1)
    assert subscription.disconnected.wait(1)


@pytest.mark.parametrize('cycle,start,end', [
    (1, datetime(2026, 1, 1), datetime(2026, 5, 1)),
    (2, datetime(2026, 5, 1), datetime(2026, 9, 1)),
    (3, datetime(2026, 9, 1), datetime(2027, 1, 1)),
])
def test_proposal_search_uses_full_cycle(cycle, start, end):
    catalog = Catalog()
    assert search_proposal_runs(catalog, 2026, cycle, 123) is catalog
    lower, upper, proposal = catalog.queries
    assert (lower.key, lower.operator.value, lower.value) == ('time', 'ge', start.timestamp())
    assert (upper.key, upper.operator.value, upper.value) == ('time', 'lt', end.timestamp())
    assert (proposal.key, proposal.value) == ('proposal', '123')


def test_processing_catalog_uses_plugin_dispatch_without_changing_shared_client(monkeypatch):
    plugin = ModuleType('bluesky_tiled_plugins')
    clients = ModuleType('bluesky_tiled_plugins.clients')
    run_module = ModuleType('bluesky_tiled_plugins.clients.bluesky_run')
    stream_module = ModuleType('bluesky_tiled_plugins.clients.bluesky_event_stream')
    catalog_module = ModuleType('bluesky_tiled_plugins.clients.catalog_of_bluesky_runs')

    class PluginRun:
        def __init__(self, context, *, item, structure_clients, **kwargs):
            self.context = context
            self.structure_clients = structure_clients

    class PluginCatalog:
        def __init__(self, context, *, item, structure_clients):
            self.context = context
            self.item = item
            self.structure_clients = structure_clients

    run_module.BlueskyRun = PluginRun
    stream_module.BlueskyEventStream = type('PluginStream', (), {})
    catalog_module.CatalogOfBlueskyRuns = PluginCatalog
    for module in (plugin, clients, run_module, stream_module, catalog_module):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    legacy_run = type('LegacyRun', (), {})
    legacy_stream = type('LegacyStream', (), {})
    original = OneShotCachedMap({'BlueskyRun': lambda: legacy_run,
                                 'BlueskyEventStream': lambda: legacy_stream,
                                 'array': lambda: list})
    source = SimpleNamespace(context=object(), item={'id': 'migration'}, structure_clients=original)
    result = tiled_access.processing_catalog(source)

    run = result.structure_clients['BlueskyRun'](source.context,
          item={'attributes': {'specs': [{'name': 'BlueskyRun', 'version': '3.0'}]}},
          structure_clients=result.structure_clients)
    assert isinstance(run, PluginRun)
    assert run.context is source.context
    assert result.structure_clients['BlueskyEventStream'] is stream_module.BlueskyEventStream
    assert result.structure_clients['array'] is list
    assert original['BlueskyRun'] is legacy_run
    assert original['BlueskyEventStream'] is legacy_stream


def test_prepare_validates_then_refreshes_legacy_view(monkeypatch):
    events = []
    run = Mock()
    run.metadata = {'start': {'uid': 'abc', 'experiment': 'fly_scan'}, 'stop': {'run_start': 'abc'}}
    run.validate.side_effect = lambda **kwargs: events.append(('validate', kwargs)) or True
    catalog = Mock()
    catalog.refresh.side_effect = lambda: events.append(('refresh',))
    catalog.v2.v1 = object()
    monkeypatch.setattr(tiled_access, 'processing_catalog', lambda client: catalog)
    monkeypatch.setattr(tiled_access, 'wait_for_completed_run',
                        lambda client, uid, **kwargs: events.append(('wait', uid)) or run)

    actual_run, legacy = tiled_access.prepare_run_for_processing(object(), 'abc')
    assert (actual_run, legacy) == (run, catalog.v2.v1)
    assert events == [('wait', 'abc'), ('validate', {'raise_on_error': True}), ('refresh',)]


@pytest.mark.parametrize('outcome', [False, ValueError('bad asset')])
def test_validation_failure_prevents_legacy_lookup(monkeypatch, outcome):
    run = Mock()
    run.metadata = {'start': {'experiment': 'fly_scan'}}
    if isinstance(outcome, Exception):
        run.validate.side_effect = outcome
    else:
        run.validate.return_value = outcome
    catalog = Mock()
    monkeypatch.setattr(tiled_access, 'processing_catalog', lambda client: catalog)
    monkeypatch.setattr(tiled_access, 'wait_for_completed_run', lambda *args, **kwargs: run)
    with pytest.raises((RuntimeError, ValueError)):
        tiled_access.prepare_run_for_processing(object(), 'abc')
    catalog.refresh.assert_not_called()
    assert 'v2' not in catalog.__dict__.get('_mock_children', {})


def test_service_runs_do_not_require_validation(monkeypatch):
    run = Mock()
    run.metadata = {'start': {'uid': 'abc'}}
    catalog = Mock()
    monkeypatch.setattr(tiled_access, 'processing_catalog', lambda client: catalog)
    monkeypatch.setattr(tiled_access, 'wait_for_completed_run', lambda *args, **kwargs: run)
    tiled_access.prepare_run_for_processing(object(), 'abc')
    run.validate.assert_not_called()
    catalog.refresh.assert_not_called()
