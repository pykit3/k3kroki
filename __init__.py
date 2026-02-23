"""k3kroki converts diagrams to images via the free kroki.io HTTP API — no local tools needed."""

from importlib.metadata import version

__version__ = version("k3kroki")
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
