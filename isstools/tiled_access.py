"""Helpers for reading runs after asynchronous Tiled ingestion."""

import time
from datetime import datetime
from queue import Empty, Queue
from threading import Event, Thread

from tiled.queries import Key


def search_proposal_runs(catalog, year, cycle, proposal):
    """Search the whole four-month cycle, including its final day."""
    year, cycle = int(year), int(cycle)
    if cycle not in (1, 2, 3):
        raise ValueError(f'Invalid cycle: {cycle}')
    start = datetime(year, (cycle - 1) * 4 + 1, 1)
    end = datetime(year + 1, 1, 1) if cycle == 3 else datetime(year, cycle * 4 + 1, 1)
    return (catalog.search(Key('time') >= start.timestamp())
            .search(Key('time') < end.timestamp())
            .search(Key('proposal') == str(proposal)))


def wait_for_completed_run(catalog, uid, timeout=120):
    """Return a run after its Stop is persisted, using Tiled streaming.

    The RunEngine callback may precede the creation of the run itself. Connect
    the catalog subscription before rechecking the run, so no Stop update can
    be missed. Metadata notifications are followed by a fresh read.
    """
    deadline = None if timeout is None else time.monotonic() + timeout

    def read_run():
        try:
            run = catalog[uid]
        except KeyError:
            return None
        # A catalog may contain an inlined, stale snapshot of the run.
        run.refresh()
        return run

    run = read_run()
    if run is not None and run.metadata.get('stop'):
        return run

    subscription = catalog.subscribe()
    updates = Queue()
    connected = Event()

    def on_update(update):
        if update.key == uid and (update.metadata or {}).get('stop'):
            updates.put(('completed', None))

    def on_closed(_subscription):
        updates.put(('closed', None))
        connected.set()

    # Keep strong references to callbacks: Tiled's callback registry uses weakrefs.
    subscription.child_created.add_callback(on_update)
    subscription.child_metadata_updated.add_callback(on_update)
    subscription.stream_closed.add_callback(on_closed)

    def receive_updates():
        try:
            subscription.start()
        except Exception as exc:
            updates.put(('error', exc))
            connected.set()
        else:
            updates.put(('closed', None))
            connected.set()

    # start_in_thread() waits indefinitely on this event if connection fails.
    # Supply our own event so start() can run separately and either connection
    # failure or the deadline can wake the processing thread.
    subscription._connected_event = connected
    receiver = Thread(target=receive_updates, name=f'tiled-wait-{uid}', daemon=True)
    receiver.start()
    try:
        remaining = None if deadline is None else max(0, deadline - time.monotonic())
        if not connected.wait(remaining):
            raise TimeoutError(f'Timed out connecting to Tiled for run {uid}')
        # Connection is established: a fresh read covers updates that happened
        # before subscription, while subsequent updates are queued by callbacks.
        run = read_run()
        if run is not None and run.metadata.get('stop'):
            return run

        remaining = None if deadline is None else max(0, deadline - time.monotonic())
        try:
            kind, error = updates.get(timeout=remaining)
        except Empty:
            raise TimeoutError(f'Timed out waiting for Tiled run {uid} to finish') from None
        if kind == 'error':
            raise error
        if kind == 'closed':
            raise RuntimeError(f'Tiled subscription closed while waiting for run {uid}')

        run = read_run()
        if run is None or not run.metadata.get('stop'):
            raise RuntimeError(f'Tiled reported completion but run {uid} has no persisted stop')
        return run
    finally:
        # Tiled's disconnect(wait=False) may still block while a handshake or
        # executor shutdown completes. Keep cleanup off the processing thread.
        Thread(target=subscription.disconnect, kwargs={'wait': False},
               name=f'tiled-disconnect-{uid}', daemon=True).start()


def processing_catalog(catalog):
    """Use plugin SQL clients without changing the GUI's shared dispatch map."""
    from bluesky_tiled_plugins.clients.bluesky_event_stream import BlueskyEventStream
    from bluesky_tiled_plugins.clients.bluesky_run import BlueskyRun
    from bluesky_tiled_plugins.clients.catalog_of_bluesky_runs import CatalogOfBlueskyRuns
    from tiled.utils import OneShotCachedMap

    dispatch = OneShotCachedMap({
        key: lambda key=key: catalog.structure_clients[key]
        for key in catalog.structure_clients
    })
    dispatch.set('BlueskyRun', lambda: BlueskyRun)
    dispatch.set('BlueskyEventStream', lambda: BlueskyEventStream)
    return CatalogOfBlueskyRuns(catalog.context, item=catalog.item, structure_clients=dispatch)


def prepare_run_for_processing(catalog, uid, timeout=120):
    """Wait for ingestion, validate external assets, and build a fresh legacy view."""
    catalog = processing_catalog(catalog)
    run = wait_for_completed_run(catalog, uid, timeout=timeout)
    if 'experiment' in run.metadata['start']:
        if not run.validate(raise_on_error=True):
            raise RuntimeError(f'Tiled validation failed for run {uid}')
        # Validation may change shapes on the server. Discard inlined child
        # metadata before constructing the v2/v1 processing view.
        catalog.refresh()
    return run, catalog.v2.v1
