"""Helpers for reading runs after asynchronous Tiled ingestion."""

import time
from datetime import datetime

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


def wait_for_completed_run(catalog, uid, timeout=120, poll_interval=0.5):
    """Wait for the run and its persisted stop document, then return it.

    The RunEngine stop callback can precede both run creation and the writer's
    final flush. Only missing runs are retried; authentication and network
    errors are reported immediately.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            run = catalog[uid]
        except KeyError:
            run = None
        if run is not None:
            run.refresh()
            if run.metadata.get('stop'):
                return run
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f'Timed out waiting for Tiled run {uid} to finish')
        time.sleep(min(poll_interval, remaining))


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


def prepare_run_for_processing(catalog, uid, timeout=120, poll_interval=0.5):
    """Wait for ingestion, validate external assets, and build a fresh legacy view."""
    catalog = processing_catalog(catalog)
    run = wait_for_completed_run(catalog, uid, timeout=timeout, poll_interval=poll_interval)
    if 'experiment' in run.metadata['start']:
        if not run.validate(raise_on_error=True):
            raise RuntimeError(f'Tiled validation failed for run {uid}')
        # Validation may change shapes on the server. Discard inlined child
        # metadata before constructing the v2/v1 processing view.
        catalog.refresh()
    return run, catalog.v2.v1
