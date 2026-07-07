from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy
from skimage.metrics import structural_similarity as ssim

import k3kroki
from k3kroki.kroki import (
    DEFAULT_BASE_URL,
    DIAGRAM_TYPES,
    OUTPUT_FORMATS,
    KrokiAPIError,
    KrokiNetworkError,
    UnsupportedDiagramError,
    UnsupportedFormatError,
    _EXT_TO_FORMAT,
    convert,
    convert_to_file,
)

DATA_DIR = Path(__file__).parent / "data"


def _mock_urlopen_response(response_data: bytes = b"<svg/>"):
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _image_ssim(want_path: Path, got_path: Path) -> float:
    from PIL import Image as PILImage

    want_img = PILImage.open(want_path).convert("RGB")
    got_img = PILImage.open(got_path).convert("RGB")

    if want_img.size != got_img.size:
        got_img = got_img.resize(want_img.size, PILImage.LANCZOS)

    img1 = numpy.asarray(want_img)
    img2 = numpy.asarray(got_img)
    return ssim(img1, img2, channel_axis=2, data_range=255)


class TestConstants(unittest.TestCase):
    def test_diagram_types_is_frozenset(self):
        self.assertIsInstance(DIAGRAM_TYPES, frozenset)

    def test_well_known_types_present(self):
        for t in ("graphviz", "mermaid", "plantuml", "d2", "ditaa", "erd"):
            self.assertIn(t, DIAGRAM_TYPES)

    def test_output_formats(self):
        self.assertEqual(OUTPUT_FORMATS, frozenset({"svg", "png", "jpeg", "pdf", "webp"}))

    def test_default_base_url(self):
        self.assertEqual(DEFAULT_BASE_URL, "https://kroki.io")


class TestValidation(unittest.TestCase):
    def test_unsupported_diagram_type(self):
        with self.assertRaises(UnsupportedDiagramError):
            convert("not_a_real_type", "source")

    def test_unsupported_output_format(self):
        with self.assertRaises(UnsupportedFormatError):
            convert("graphviz", "source", "gif")

    def test_diagram_type_case_insensitive(self):
        with patch("k3kroki.kroki.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_urlopen_response()
            convert("Graphviz", "digraph{a->b}", "SVG")

            req = mock_urlopen.call_args[0][0]
            self.assertIn("/graphviz/svg", req.full_url)


class TestConvertMocked(unittest.TestCase):
    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_url_construction(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response()
        convert("mermaid", "graph TD; A-->B", "png")

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://kroki.io/mermaid/png")

    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_custom_base_url(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response()
        convert("graphviz", "digraph{}", "svg", base_url="http://localhost:8000")

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "http://localhost:8000/graphviz/svg")

    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_trailing_slash_stripped(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response()
        convert("graphviz", "digraph{}", "svg", base_url="https://kroki.io/")

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://kroki.io/graphviz/svg")

    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_content_type_header(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response()
        convert("graphviz", "digraph{a->b}", "svg")

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Content-type"), "text/plain")

    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_post_body_is_utf8_encoded(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response()
        source = 'digraph { label="日本語" }'
        convert("graphviz", source, "svg")

        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.data, source.encode("utf-8"))

    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_returns_bytes(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response(b"\x89PNG")
        result = convert("graphviz", "digraph{}", "png")
        self.assertEqual(result, b"\x89PNG")

    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_timeout_passed(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen_response()
        convert("graphviz", "digraph{}", "svg", timeout=5.0)
        self.assertEqual(mock_urlopen.call_args[1]["timeout"], 5.0)


class TestSvgFallbackMocked(unittest.TestCase):
    """Test the SVG→bitmap fallback path using mocks."""

    @patch("k3kroki.kroki._svg_to_bitmap")
    @patch("k3kroki.kroki._fetch_kroki")
    def test_fallback_on_unsupported_format(self, mock_fetch, mock_bitmap):
        mock_fetch.side_effect = [
            KrokiAPIError(400, "Unsupported output format: png"),
            b"<svg>mock</svg>",
        ]
        mock_bitmap.return_value = b"\x89PNG-mock"

        result = convert("d2", "x -> y", "png")

        self.assertEqual(result, b"\x89PNG-mock")
        self.assertEqual(mock_fetch.call_count, 2)
        self.assertEqual(mock_fetch.call_args_list[1][0][2], "svg")
        mock_bitmap.assert_called_once_with(b"<svg>mock</svg>", "png")

    @patch("k3kroki.kroki._fetch_kroki")
    def test_non_format_api_error_propagates(self, mock_fetch):
        mock_fetch.side_effect = KrokiAPIError(400, "syntax error in diagram")

        with self.assertRaises(KrokiAPIError) as ctx:
            convert("graphviz", "bad", "png")

        self.assertIn("syntax error", ctx.exception.body)

    @patch("k3kroki.kroki._fetch_kroki")
    def test_fallback_not_triggered_for_svg(self, mock_fetch):
        mock_fetch.side_effect = KrokiAPIError(400, "Unsupported output format: svg")

        with self.assertRaises(KrokiAPIError):
            convert("d2", "x -> y", "svg")

        mock_fetch.assert_called_once()


class TestErrorWrapping(unittest.TestCase):
    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_http_error_becomes_api_error(self, mock_urlopen):
        import urllib.error

        exc = urllib.error.HTTPError("url", 400, "Bad Request", {}, MagicMock(read=lambda: b"syntax error"))
        mock_urlopen.side_effect = exc

        with self.assertRaises(KrokiAPIError) as ctx:
            convert("graphviz", "bad source", "svg")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("syntax error", ctx.exception.body)

    @patch("k3kroki.kroki.urllib.request.urlopen")
    def test_url_error_becomes_network_error(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Name or service not known")

        with self.assertRaises(KrokiNetworkError):
            convert("graphviz", "digraph{}", "svg")


class TestConvertToFileMocked(unittest.TestCase):
    @patch("k3kroki.kroki.convert")
    def test_writes_bytes_to_file(self, mock_convert):
        mock_convert.return_value = b"<svg>test</svg>"

        with tempfile.TemporaryDirectory() as tdir:
            path = str(Path(tdir) / "out.svg")
            convert_to_file("graphviz", "digraph{}", path)

            self.assertEqual(Path(path).read_bytes(), b"<svg>test</svg>")
            mock_convert.assert_called_once_with(
                "graphviz", "digraph{}", "svg", base_url=DEFAULT_BASE_URL, timeout=30.0
            )

    @patch("k3kroki.kroki.convert")
    def test_infers_format_from_extension(self, mock_convert):
        mock_convert.return_value = b"\x89PNG"

        with tempfile.TemporaryDirectory() as tdir:
            for ext, fmt in _EXT_TO_FORMAT.items():
                path = str(Path(tdir) / f"out{ext}")
                convert_to_file("graphviz", "digraph{}", path)
                self.assertEqual(mock_convert.call_args[0][2], fmt)

    @patch("k3kroki.kroki.convert")
    def test_explicit_format_overrides_extension(self, mock_convert):
        mock_convert.return_value = b"data"

        with tempfile.TemporaryDirectory() as tdir:
            path = str(Path(tdir) / "out.svg")
            convert_to_file("graphviz", "digraph{}", path, output_format="png")
            self.assertEqual(mock_convert.call_args[0][2], "png")

    def test_unknown_extension_raises(self):
        with self.assertRaises(UnsupportedFormatError):
            convert_to_file("graphviz", "digraph{}", "/tmp/out.bmp")


class TestExceptionHierarchy(unittest.TestCase):
    def test_unsupported_diagram_is_value_error(self):
        self.assertTrue(issubclass(UnsupportedDiagramError, ValueError))
        self.assertTrue(issubclass(UnsupportedDiagramError, k3kroki.KrokiError))

    def test_unsupported_format_is_value_error(self):
        self.assertTrue(issubclass(UnsupportedFormatError, ValueError))
        self.assertTrue(issubclass(UnsupportedFormatError, k3kroki.KrokiError))

    def test_api_error_is_kroki_error(self):
        self.assertTrue(issubclass(KrokiAPIError, k3kroki.KrokiError))

    def test_network_error_is_kroki_error(self):
        self.assertTrue(issubclass(KrokiNetworkError, k3kroki.KrokiError))


class TestImageOutput(unittest.TestCase):
    """Tests that hit kroki.io and compare rendered images against expected outputs."""

    def _assert_bitmap(self, diagram_type: str, fmt: str) -> None:
        source = (DATA_DIR / diagram_type / "input").read_text()
        got_bytes = convert(diagram_type, source, fmt)

        got_path = DATA_DIR / diagram_type / f"got.{fmt}"
        got_path.write_bytes(got_bytes)
        try:
            sim = _image_ssim(DATA_DIR / diagram_type / f"want.{fmt}", got_path)
            self.assertGreater(sim, 0.75)
        finally:
            got_path.unlink(missing_ok=True)

    def test_convert_png(self):
        for t in ("graphviz", "mermaid", "plantuml", "d2", "svgbob"):
            with self.subTest(diagram_type=t):
                self._assert_bitmap(t, "png")

    def test_convert_webp(self):
        for t in ("d2", "svgbob", "graphviz"):
            with self.subTest(diagram_type=t):
                self._assert_bitmap(t, "webp")

    def test_convert_svg(self):
        for t in ("graphviz", "mermaid", "plantuml", "d2", "svgbob"):
            want_path = DATA_DIR / t / "want.svg"
            if not want_path.exists():
                continue

            with self.subTest(diagram_type=t):
                source = (DATA_DIR / t / "input").read_text()
                got = convert(t, source, "svg")
                self.assertIn(b"<svg", want_path.read_bytes())
                self.assertIn(b"<svg", got)

    def test_convert_to_file(self):
        cases = [
            ("graphviz", "png"),
            ("mermaid", "png"),
            ("plantuml", "png"),
            ("d2", "svg"),
            ("d2", "png"),
            ("d2", "webp"),
            ("svgbob", "svg"),
            ("svgbob", "png"),
            ("svgbob", "webp"),
        ]
        for diagram_type, fmt in cases:
            want_path = DATA_DIR / diagram_type / f"want.{fmt}"
            if not want_path.exists():
                continue

            with self.subTest(diagram_type=diagram_type, fmt=fmt):
                source = (DATA_DIR / diagram_type / "input").read_text()
                got_path = DATA_DIR / diagram_type / f"got.{fmt}"

                convert_to_file(diagram_type, source, str(got_path), fmt)
                try:
                    if fmt == "svg":
                        self.assertIn(b"<svg", got_path.read_bytes())
                    else:
                        sim = _image_ssim(want_path, got_path)
                        self.assertGreater(sim, 0.75)
                finally:
                    got_path.unlink(missing_ok=True)
