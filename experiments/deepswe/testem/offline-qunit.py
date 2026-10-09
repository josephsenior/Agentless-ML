"""Labelled offline asset delivery. Never proxy or fabricate test results."""

import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PINS = {
    '/qunit/qunit-1.20.0.js': ('qunit-1.20.0.js', 112454,
        '576c7117981fae223d412e94e53a176c124f5e3a4dc321b9d56d58ae680015c0', 'application/javascript'),
    '/qunit/qunit-1.20.0.css': ('qunit-1.20.0.css', 5349,
        '98abc5dc3d67eb3a1f50eb861c7f888a9a5b43edaa8f29689c50d1841fb915fb', 'text/css'),
}


def verify_bytes(data, size, digest):
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Offline public asset does not match verified pin')


def load_assets(root=ROOT):
    assets = {}
    for route, (filename, size, digest, mime) in PINS.items():
        data = (root / filename).read_bytes()
        verify_bytes(data, size, digest)
        assets[route] = (data, digest, mime)
    return assets


def allowed_request(host, path):
    return host in ('code.jquery.com', 'code.jquery.com:80') and path in PINS


def make_server(assets):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.deliver(False)

        def do_HEAD(self):
            self.deliver(True)

        def deliver(self, head):
            host = self.headers.get('Host')
            if not allowed_request(host, self.path):
                self.send_error(404)
                return
            data, digest, mime = assets[self.path]
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Content-SHA256', digest)
            self.end_headers()
            if not head:
                self.wfile.write(data)
            print(json.dumps({'event': 'pinned_asset_response', 'method': self.command,
                'host': host, 'path': self.path, 'sha256': digest, 'bytes': len(data),
                'body_bytes_sent': 0 if head else len(data)}), flush=True)

        def log_message(self, format, *args):
            print(json.dumps({'event': 'http_log', 'message': format % args}), flush=True)

    return HTTPServer(('127.0.0.1', 80), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-files', action='store_true')
    options = parser.parse_args()
    assets = load_assets()
    if options.check_files:
        print(str(len(assets)) + ' pinned public assets verified; no service started')
        return
    with make_server(assets) as server:
        print(json.dumps({'condition': 'modified environment: offline public-asset delivery',
            'listen': '127.0.0.1:80', 'routes': list(assets)}), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
