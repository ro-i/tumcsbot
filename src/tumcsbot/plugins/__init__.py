from importlib import import_module as _import_module
from pkgutil import iter_modules as _iter_modules
from os.path import dirname as _dirname
from typing import Any

_: Any

# Import all modules to the current namespace.
for _, _module_name, _ in _iter_modules([_dirname(__file__)]):
    globals()[_module_name] = _import_module('.' + _module_name, package = __package__)
