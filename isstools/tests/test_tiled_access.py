from datetime import datetime

import pytest

from isstools.tiled_access import search_proposal_runs, wait_for_completed_run


class Catalog:
    def __init__(self, runs=()):
        self.runs = list(runs)
        self.queries = []

    def __getitem__(self, uid):
        result = self.runs.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def search(self, query):
        self.queries.append(query)
        return self


class Run:
    def __init__(self, stop):
        self.metadata = {'start': {'uid': 'abc'}, 'stop': stop}
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1


def test_wait_for_creation_and_persisted_stop():
    pending = Run(None)
    completed = Run({'run_start': 'abc'})
    catalog = Catalog([KeyError('abc'), pending, completed])
    assert wait_for_completed_run(catalog, 'abc', timeout=1, poll_interval=0) is completed
    assert pending.refreshes == completed.refreshes == 1


def test_wait_timeout_and_unrelated_errors():
    with pytest.raises(TimeoutError, match='abc'):
        wait_for_completed_run(Catalog([KeyError('abc')]), 'abc', timeout=0)
    with pytest.raises(PermissionError):
        wait_for_completed_run(Catalog([PermissionError('denied')]), 'abc', timeout=0)


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
