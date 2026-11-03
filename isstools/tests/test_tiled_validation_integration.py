"""Exercise real plugin client dispatch and validation against a fake HTTP server.

Run with ``python -m unittest isstools.tests.test_tiled_validation_integration``
in an environment containing bluesky-tiled-plugins and httpx.
"""

import importlib.util
import sys
import types
import unittest
from unittest.mock import patch


HAS_PLUGIN = importlib.util.find_spec('bluesky_tiled_plugins') is not None


@unittest.skipUnless(HAS_PLUGIN, 'bluesky-tiled-plugins is not installed')
class ValidationIntegrationTest(unittest.TestCase):
    def test_real_subscription_dispatches_stop_after_run_creation(self):
        import httpx
        from threading import Event
        from tiled.client.container import Container
        from tiled.utils import OneShotCachedMap
        from isstools.tiled_access import wait_for_completed_run

        uid = '4125cbf7-dcf7-4c5d-b7bd-e955364ff037'
        root = 'https://example.test/api/v1/metadata/iss/migration'
        run_url = f'{root}/{uid}'
        state = {'created': False, 'stopped': False, 'replay': None}
        receiving = Event()
        released = Event()
        context = types.SimpleNamespace(http_client=None)
        context.server_info = types.SimpleNamespace(authentication=types.SimpleNamespace(providers=[]))
        context.api_key = None

        def item(key, url, metadata):
            return {'id': key, 'links': {'self': url}, 'attributes': {
                'structure_family': 'container', 'metadata': metadata, 'specs': [],
                'structure': {'contents': None},
            }}

        class FakeHTTP:
            def get(self, url, **kwargs):
                if url == run_url and not state['created']:
                    return httpx.Response(404, request=httpx.Request('GET', url))
                metadata = {'start': {'uid': uid}, 'stop': {'run_start': uid} if state['stopped'] else None}
                return httpx.Response(200, json={'data': item(uid, run_url, metadata)},
                                      request=httpx.Request('GET', url))

        class FakeSocket:
            def __init__(self, http_client, uri):
                self.messages = iter([b'schema', b'created', b'stop'])

            def connect(self, auth_header, start, max_size):
                state['replay'] = start

            def recv(self, timeout=None):
                message = next(self.messages, None)
                if message == b'schema':
                    receiving.set()
                    if not released.wait(2):
                        raise TimeoutError('test did not release stream')
                return message

            def close(self):
                released.set()

        def parse_update(subscription, data, schema):
            if data == b'created':
                state['created'] = True
                return types.SimpleNamespace(type='container-child-created', key=uid, metadata={}, sequence=1)
            state['stopped'] = True
            return types.SimpleNamespace(type='container-child-metadata-updated', key=uid,
                                         metadata={'stop': {'run_start': uid}}, sequence=2)

        dispatch = OneShotCachedMap({'container': lambda: Container})
        context.http_client = FakeHTTP()
        catalog = Container(context, item=item('migration', root, {}), structure_clients=dispatch)

        # Release only after the second metadata lookup, so this covers the
        # actual asynchronous callback dispatch after an initially missing run.
        original_get = context.http_client.get
        lookups = []
        def get_with_release(url, **kwargs):
            result = original_get(url, **kwargs)
            if url == run_url:
                lookups.append(url)
                if len(lookups) == 2:
                    self.assertTrue(receiving.wait(2))
                    released.set()
            return result
        context.http_client.get = get_with_release

        with patch('tiled.client.stream._RegularWebsocketWrapper', FakeSocket), \
             patch('tiled.client.stream._auth_header', return_value=(None, None), create=True), \
             patch('tiled.client.stream.parse_schema', return_value={}), \
             patch('tiled.client.stream.parse_update', side_effect=parse_update):
            # ContainerSubscription constructs its URL from the Tiled context.
            context.api_uri = httpx.URL('https://example.test/api/v1/')
            catalog._item['attributes']['ancestors'] = ['iss']
            run = wait_for_completed_run(catalog, uid, timeout=3)

        self.assertEqual(run.metadata['stop']['run_start'], uid)
        self.assertIsNone(state['replay'])
        self.assertGreaterEqual(len(lookups), 3)

    def test_validation_repairs_shape_before_legacy_lookup(self):
        import httpx
        from tiled.client.container import Container
        from tiled.client.composite import CompositeClient
        from tiled.utils import OneShotCachedMap
        from isstools.tiled_access import prepare_run_for_processing

        uid = '4125cbf7-dcf7-4c5d-b7bd-e955364ff037'
        root_url = 'https://example.test/api/v1/metadata/iss/migration'
        run_url = f'{root_url}/{uid}'
        state = {'shape': [1, 100000], 'events': []}

        def item(key, url, *, specs=(), metadata=None, contents=None):
            return {'id': key, 'links': {'self': url, 'search': f'{url}/search'}, 'attributes': {
                'structure_family': 'container', 'metadata': metadata or {},
                'specs': list(specs), 'structure': {'contents': contents},
                'sorting': [{'key': '_', 'direction': 1}],
            }}

        def run_item():
            data_url = f'{run_url}/apb_stream/apb_stream'
            data = {'id': 'apb_stream', 'links': {'self': data_url}, 'attributes': {
                'structure_family': 'array', 'metadata': {}, 'specs': [],
                'structure': {'shape': list(state['shape'])},
            }}
            stream = item('apb_stream', f'{run_url}/apb_stream', specs=[{'name': 'composite', 'version': '1.0'}],
                          contents={'apb_stream': data})
            return item(uid, run_url, specs=[{'name': 'BlueskyRun', 'version': '3.0'}],
                        metadata={'start': {'uid': uid, 'experiment': 'fly_scan'},
                                  'stop': {'run_start': uid}},
                        contents={'apb_stream': stream})

        def catalog_item():
            return item('migration', root_url,
                        specs=[{'name': 'CatalogOfBlueskyRuns', 'version': '3.0'}],
                        contents={uid: run_item()})

        class FakeHTTP:
            def get(self, url, **kwargs):
                state['events'].append(('get', url))
                if url == f'{run_url}/apb_stream/search':
                    stream = run_item()['attributes']['structure']['contents']['apb_stream']
                    data = list(stream['attributes']['structure']['contents'].values())
                    return httpx.Response(200, json={'data': data, 'links': {'next': None}},
                                          request=httpx.Request('GET', url))
                if 'search' in url:
                    raise AssertionError(f'Unexpected search: {url}')
                if url not in (root_url, run_url, f'{run_url}/apb_stream'):
                    raise AssertionError(f'Unexpected lookup: {url}')
                if url == root_url:
                    result = catalog_item()
                elif url == f'{run_url}/apb_stream':
                    result = run_item()['attributes']['structure']['contents']['apb_stream']
                else:
                    result = run_item()
                return httpx.Response(200, json={'data': result}, request=httpx.Request('GET', url))

            def post(self, url, **kwargs):
                state['events'].append(('validate', kwargs['params']))
                self_test.assertEqual(url, run_url.replace('/api/v1/metadata/', '/custom/validate/'))
                state['shape'] = [33000, 1]
                return httpx.Response(200, json={'valid': True, 'notes': []},
                                      request=httpx.Request('POST', url))

        class FakeArray:
            def __init__(self, context, *, item, **kwargs):
                self.context = context
                self.item = item

            def read(self):
                shape = self.item['attributes']['structure']['shape']
                state['events'].append(('read', shape))
                if shape != state['shape']:
                    raise ValueError(f'Cannot reshape {state["shape"]} to {shape}')
                return shape

        self_test = self
        context = types.SimpleNamespace(http_client=FakeHTTP())
        original_dispatch = OneShotCachedMap({'BlueskyRun': lambda: Container, 'array': lambda: FakeArray,
                                              'container': lambda: Container, 'composite': lambda: CompositeClient})
        original = Container(context, item=catalog_item(), structure_clients=original_dispatch)

        # The plugin's v1 adapter imports databroker lazily; use a stub to
        # inspect the fresh v2 catalog without requiring the beamline stack.
        broker_module = types.ModuleType('databroker')
        v1_module = types.ModuleType('databroker.v1')
        class Broker:
            def __init__(self, catalog):
                self.catalog = catalog
        v1_module.Broker = Broker
        broker_module.v1 = v1_module
        with patch.dict(sys.modules, {'databroker': broker_module, 'databroker.v1': v1_module}):
            run, legacy = prepare_run_for_processing(original, uid)
            refreshed_run = legacy.catalog[uid]
            result = refreshed_run['apb_stream']['data']['apb_stream'].read()

        self.assertEqual(result, [33000, 1])
        original_run = original.item['attributes']['structure']['contents'][uid]
        original_array = original_run['attributes']['structure']['contents']['apb_stream']['attributes']['structure']['contents']['apb_stream']
        self.assertEqual(original_array['attributes']['structure']['shape'], [1, 100000])
        self.assertEqual(original_dispatch['BlueskyRun'], Container)
        self.assertEqual(state['events'][:3], [
            ('get', run_url), ('validate', {'fix': True, 'read': True}), ('get', root_url),
        ])
        self.assertEqual(state['events'][-1], ('read', [33000, 1]))
        self.assertEqual(run.metadata['start']['uid'], uid)


if __name__ == '__main__':
    unittest.main()
