import http.server
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_iso


class DownloadHTTPTests(unittest.TestCase):
    def test_interrupted_transfer_resumes_over_http(self):
        body = b"abcdef" * 1000
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                offset = int(self.headers.get("Range", "bytes=0-")[6:-1])
                requests.append(offset)
                self.send_response(206 if offset else 200)
                self.send_header("Content-Length", str(len(body) - offset))
                if offset:
                    self.send_header("Content-Range", f"bytes {offset}-{len(body)-1}/{len(body)}")
                self.end_headers()
                self.wfile.write(body[offset:] if offset else body[:1000])
                self.close_connection = True

        with tempfile.TemporaryDirectory() as directory:
            server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            original = urllib.request.urlopen

            def transport(request, timeout=None):
                local = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/", headers=dict(request.header_items()))
                response = original(local, timeout=timeout)
                response.geturl = lambda: "https://test.invalid/file"
                return response

            target = Path(directory) / "download"
            try:
                with patch("build_iso.urllib.request.urlopen", side_effect=transport):
                    with self.assertRaisesRegex(ValueError, "incomplet"):
                        build_iso.download("https://test.invalid/file", target)
                    self.assertFalse(target.exists())
                    self.assertEqual(Path(str(target) + ".part").stat().st_size, 1000)
                    build_iso.download("https://test.invalid/file", target)
                self.assertEqual(target.read_bytes(), body)
                self.assertEqual(requests, [0, 1000])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
