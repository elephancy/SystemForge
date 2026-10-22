"""Run with NGINX_BINARY=/path/to/nginx python -m unittest discover -s tests -p test_nginx_headers.py."""
import http.client
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest


class NginxHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get("NGINX_BINARY") or shutil.which("nginx")
        if not binary:
            raise RuntimeError("nginx is required for the runtime header regression")
        cls.temporary = tempfile.TemporaryDirectory(prefix="systemforge-nginx-")
        cls.root = Path(cls.temporary.name)
        (cls.root / "logs").mkdir()
        html = cls.root / "html"
        (html / "assets").mkdir(parents=True)
        fixtures = {"index.html": "<!doctype html>fixture", "offline.html": "offline",
                    "assets/app.js": "console.log('fixture')", "manifest.webmanifest": "{}",
                    "asset-manifest.json": "{}", "asset-precache.json": "{}",
                    "robots.txt": "User-agent: *", "sitemap.xml": "<urlset/>"}
        for name, text in fixtures.items():
            (html / name).write_text(text)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            cls.port = listener.getsockname()[1]
        source = (Path(__file__).resolve().parents[1] / "deploy/nginx.conf").read_text()
        mime = cls.root / "mime.types"
        mime.write_text("types { text/html html; application/javascript js; text/plain txt; application/xml xml; }")
        source = source.replace("worker_processes auto;", "worker_processes 1;")
        source = source.replace("pid /tmp/nginx.pid;", f"pid {cls.root}/nginx.pid;")
        source = source.replace("/etc/nginx/mime.types", str(mime))
        source = source.replace("/usr/share/nginx/html", str(html))
        source = source.replace("listen 8080;", f"listen 127.0.0.1:{cls.port};")
        for name in ["client_temp", "proxy_temp", "fastcgi_temp", "uwsgi_temp", "scgi_temp"]:
            source = source.replace(f"/tmp/{name}", str(cls.root / name))
        config = cls.root / "nginx.conf"
        config.write_text(source)
        # The fixture runs as the current non-root caller, or UID1000 when invoked by root.
        role = {}
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            for path in [cls.root, *cls.root.rglob("*")]:
                os.chown(path, 1000, 1000)
            role = {"user": 1000, "group": 1000, "extra_groups": []}
        cls.output = (cls.root / "process.log").open("wb")
        if role:
            os.chown(cls.root / "process.log", 1000, 1000)
        cls.process = subprocess.Popen([binary, "-p", str(cls.root) + "/", "-c", str(config),
                                        "-g", "daemon off;"], stdout=cls.output,
                                       stderr=cls.output, **role)
        for _ in range(100):
            if cls.process.poll() is not None:
                raise RuntimeError("nginx fixture failed to start")
            try:
                connection = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=.2)
                connection.request("GET", "/health")
                connection.getresponse().read()
                connection.close()
                return
            except OSError:
                time.sleep(.02)
        cls.process.terminate()
        cls.process.wait(timeout=5)
        raise RuntimeError("nginx fixture did not become ready")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.output.close()
        cls.temporary.cleanup()

    def test_route_cache_policy_and_security_headers(self):
        spa = "public, max-age=0, must-revalidate, no-transform"
        cdn = "public, max-age=300, stale-while-revalidate=60, stale-if-error=86400"
        cases = [
            ("/health", 200, None, None, None),
            ("/assets/app.js", 200, "public, max-age=31536000, immutable", None, None),
            ("/assets/missing.js", 404, None, None, None),
            ("/manifest.webmanifest", 200, "public, max-age=3600", None, None),
            ("/asset-manifest.json", 200, "no-cache", None, None),
            ("/asset-precache.json", 200, "no-cache", None, None),
            ("/robots.txt", 200, None, None, None),
            ("/sitemap.xml", 200, None, None, None),
            ("/lab", 200, spa, cdn, None),
            ("/scenario/fixture", 200, spa, cdn, "noindex, follow"),
            ("/scenario/fixture?mode=view", 200, spa, cdn, "noindex, follow"),
            ("/scenario/fixture/extra", 404, spa, cdn, None),
            ("/unknown-route", 404, spa, cdn, None),
            ("/offline.html", 404, "no-store, no-transform", None, None),
        ]
        for path, status, cache, edge, robots in cases:
            with self.subTest(path=path):
                connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
                connection.request("GET", path)
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, status)
                self.assertEqual(response.getheader("Cache-Control"), cache)
                self.assertEqual(response.getheader("Cloudflare-CDN-Cache-Control"), edge)
                self.assertEqual(response.getheader("X-Robots-Tag"), robots)
                self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                self.assertEqual(response.getheader("Referrer-Policy"), "strict-origin-when-cross-origin")
                if path == "/health":
                    self.assertEqual(response.getheader("Content-Type"), "text/plain")
                connection.close()


if __name__ == "__main__":
    unittest.main()
