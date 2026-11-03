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
