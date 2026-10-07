"""Serve verified public snapshots over real, container-local HTTPS only."""

import argparse
import hashlib
import json
from pathlib import Path
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path('/opt/pwntools-services')
ROUTES = {
    ('pypi.org', '/simple/pwntools/'): ('pypi.json', 'application/vnd.pypi.simple.v1+json'),
    ('httpbingo.org', '/robots.txt'): ('robots.txt', 'text/plain; charset=utf-8'),
}


def load_snapshots(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    records = {record['file']: record for record in manifest['snapshots']}
    if len(manifest['snapshots']) != len(ROUTES) or set(records) != {value[0] for value in ROUTES.values()}:
        raise ValueError('Unexpected snapshot inventory')
    bodies = {}
    for filename, record in records.items():
        data = (root / filename).read_bytes()
        if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError('Snapshot mismatch: ' + filename)
        bodies[filename] = data
    versions = json.loads(bodies['pypi.json'])['versions']
    if not versions or not all(isinstance(version, str) for version in versions):
        raise ValueError('Invalid public version list')
    return bodies


def handler(bodies):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            host = self.headers.get('Host', '').lower().split(':')[0]
            route = ROUTES.get((host, self.path))
            code = 200
            if route is None:
                code = 404
            elif host == 'pypi.org' and 'application/vnd.pypi.simple.v1+json' not in self.headers.get('Accept', ''):
                code = 406
            if code != 200:
                self.send_error(code)
            else:
                filename, content_type = route
                body = bodies[filename]
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            print(json.dumps({'host': host, 'path': self.path, 'method': 'GET', 'status': code,
                              'snapshot': route[0] if route else None}), flush=True)

        def log_message(self, *args):
            pass
    return Handler


def check(cert):
    import requests
    bodies = load_snapshots(ROOT)
    for (host, path), (filename, _) in ROUTES.items():
        headers = {'Accept': 'application/vnd.pypi.simple.v1+json'}
        response = requests.get('https://' + host + path, headers=headers, verify=cert, timeout=3)
        response.raise_for_status()
        if response.content != bodies[filename]:
            raise ValueError('Service bytes differ from public snapshot')
    # Removing explicit trust must fail; never use verify=False.
    try:
        requests.get('https://httpbingo.org/robots.txt', verify=requests.certs.where(), timeout=3)
    except requests.exceptions.SSLError:
        pass
    else:
        raise ValueError('Diagnostic certificate unexpectedly trusted by default')
    response = requests.get('https://httpbingo.org/unsupported', verify=cert, timeout=3)
    if response.status_code != 404:
        raise ValueError('Unsupported path did not fail')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cert', required=True)
    parser.add_argument('--key')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        check(args.cert)
        return
    if not args.key:
        parser.error('--key is required for the server')
    server = ThreadingHTTPServer(('127.0.0.1', 443), handler(load_snapshots(ROOT)))
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(args.cert, args.key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
