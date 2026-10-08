"""Access bundled UI files and tables without importing setuptools at runtime."""

import atexit
from contextlib import ExitStack
from copy import deepcopy
from functools import lru_cache
from importlib.resources import as_file, files
import json


_resource_contexts = ExitStack()
atexit.register(_resource_contexts.close)


@lru_cache(maxsize=None)
def resource_path(name):
    """Return a filename that stays available for the lifetime of the process."""
    resource = files("isstools").joinpath(name)
    return str(_resource_contexts.enter_context(as_file(resource)))


@lru_cache(maxsize=None)
def _load_json(name):
    with files("isstools").joinpath(name).open(encoding="utf-8") as stream:
        return json.load(stream)


def load_json(name):
    """Read a bundled table once; give each caller an independent copy."""
    return deepcopy(_load_json(name))
