"""A converter to Numbers spreadsheets for 1Password 1PUX files."""

import importlib.metadata

__version__ = importlib.metadata.version("onepass2numbers")


def _get_version() -> str:
    return __version__
