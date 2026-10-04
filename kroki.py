"""Convert diagrams to images via the kroki.io HTTP API with local SVG→bitmap fallback.

Note:
    Excalidraw is **not** supported. The kroki.io excalidraw backend is
    unreliable (its internal renderer frequently refuses connections),
    making it impossible to produce stable output.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image
from resvg_py import svg_to_bytes

DEFAULT_BASE_URL = "https://kroki.io"

DIAGRAM_TYPES: frozenset[str] = frozenset(
    {
        "actdiag",
        "blockdiag",
        "bpmn",
        "bytefield",
        "c4plantuml",
        "d2",
        "dbml",
        "ditaa",
        "erd",
        "graphviz",
        "mermaid",
        "nomnoml",
        "nwdiag",
        "packetdiag",
        "pikchr",
        "plantuml",
        "rackdiag",
        "seqdiag",
        "structurizr",
        "svgbob",
        "symbolator",
        "tikz",
        "umlet",
        "vega",
        "vegalite",
        "wavedrom",
        "wireviz",
    }
)

OUTPUT_FORMATS: frozenset[str] = frozenset({"svg", "png", "jpeg", "pdf", "webp"})

_EXT_TO_FORMAT: dict[str, str] = {
    ".svg": "svg",
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".pdf": "pdf",
    ".webp": "webp",
}

_BITMAP_FORMATS: frozenset[str] = frozenset({"png", "jpeg", "webp"})


def _fetch_kroki(base_url: str, diagram_type: str, output_format: str, data: bytes, timeout: float) -> bytes:
    """Send a request to the kroki API and return response bytes."""
    url = f"{base_url.rstrip('/')}/{diagram_type}/{output_format}"
    headers = {
        "Content-Type": "text/plain",
        "User-Agent": "k3kroki/0.1",
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise KrokiAPIError(exc.code, body) from exc
    except urllib.error.URLError as exc:
        raise KrokiNetworkError(str(exc.reason)) from exc
    except OSError as exc:
        # urllib wraps only the errors raised while sending the request; a
        # timeout or reset while reading the response arrives unwrapped.
        raise KrokiNetworkError(str(exc)) from exc


def _svg_to_bitmap(svg_bytes: bytes, output_format: str) -> bytes:
    """Render SVG bytes to a bitmap format using resvg (SVG→PNG) and Pillow (PNG→JPEG/WebP)."""
    png_bytes = svg_to_bytes(svg_string=svg_bytes.decode("utf-8"), dpi=192)
    if output_format == "png":
        return png_bytes

    img = Image.open(io.BytesIO(png_bytes))
    buf = io.BytesIO()
    if output_format == "jpeg":
        img = img.convert("RGB")
    img.save(buf, format=output_format.upper(), quality=90)
    return buf.getvalue()


class KrokiError(Exception):
    """Base exception for k3kroki."""


class UnsupportedDiagramError(KrokiError, ValueError):
    """Raised when the diagram type is not supported."""


class UnsupportedFormatError(KrokiError, ValueError):
    """Raised when the output format is not supported."""


class KrokiAPIError(KrokiError):
    """Raised when the kroki API returns a non-2xx response."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Kroki API error {status_code}: {body}")


class KrokiNetworkError(KrokiError):
    """Raised on network-level failures (DNS, timeout, connection refused)."""


def convert(
    diagram_type: str,
    source: str,
    output_format: str = "svg",
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
) -> bytes:
    """Send diagram source to kroki and return rendered image bytes.

    Args:
        diagram_type: Diagram language (e.g. ``"graphviz"``, ``"mermaid"``).
        source: Diagram source text.
        output_format: One of ``"svg"``, ``"png"``, ``"jpeg"``, ``"pdf"``, ``"webp"``.
        base_url: Kroki server URL. Defaults to ``https://kroki.io``.
        timeout: HTTP timeout in seconds.

    Returns:
        Raw bytes of the rendered image.

    Raises:
        UnsupportedDiagramError: If *diagram_type* is not recognised.
        UnsupportedFormatError: If *output_format* is not recognised.
        KrokiAPIError: If the server returns a non-2xx status.
        KrokiNetworkError: On connection / DNS / timeout failures.
    """
    diagram_type = diagram_type.lower()
    output_format = output_format.lower()

    if diagram_type not in DIAGRAM_TYPES:
        raise UnsupportedDiagramError(f"Unsupported diagram type: {diagram_type!r}")
    if output_format not in OUTPUT_FORMATS:
        raise UnsupportedFormatError(f"Unsupported output format: {output_format!r}")

    data = source.encode("utf-8")

    try:
        return _fetch_kroki(base_url, diagram_type, output_format, data, timeout)
    except KrokiAPIError as exc:
        if output_format not in _BITMAP_FORMATS or "Unsupported output format" not in exc.body:
            raise

    svg_bytes = _fetch_kroki(base_url, diagram_type, "svg", data, timeout)
    return _svg_to_bitmap(svg_bytes, output_format)


def convert_to_file(
    diagram_type: str,
    source: str,
    output_path: str,
    output_format: str | None = None,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
) -> None:
    """Render a diagram and write the result to *output_path*.

    If *output_format* is ``None`` it is inferred from the file extension
    (``.svg``, ``.png``, ``.jpg``/``.jpeg``, ``.pdf``).

    Args:
        diagram_type: Diagram language.
        source: Diagram source text.
        output_path: Destination file path.
        output_format: Explicit format, or ``None`` to infer from extension.
        base_url: Kroki server URL.
        timeout: HTTP timeout in seconds.
    """
    if output_format is None:
        ext = Path(output_path).suffix.lower()
        output_format = _EXT_TO_FORMAT.get(ext)
        if output_format is None:
            raise UnsupportedFormatError(f"Cannot infer format from extension: {ext!r}")

    data = convert(diagram_type, source, output_format, base_url=base_url, timeout=timeout)
    Path(output_path).write_bytes(data)
