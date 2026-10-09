"""k3kroki converts diagrams to images via the free kroki.io HTTP API — no local tools needed."""

__name__ = "k3kroki"

from .kroki import (
    DEFAULT_BASE_URL,
    DIAGRAM_TYPES,
    OUTPUT_FORMATS,
    KrokiAPIError,
    KrokiError,
    KrokiNetworkError,
    UnsupportedDiagramError,
    UnsupportedFormatError,
    convert,
    convert_to_file,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DIAGRAM_TYPES",
    "OUTPUT_FORMATS",
    "KrokiAPIError",
    "KrokiError",
    "KrokiNetworkError",
    "UnsupportedDiagramError",
    "UnsupportedFormatError",
    "convert",
    "convert_to_file",
]


def __getattr__(name: str) -> str:
    # importlib.metadata takes about 20 ms to import, so it is loaded only
    # when __version__ is read
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib.metadata import version

    return version("k3kroki")
