'use strict';
const fs = require('fs');
const http = require('http');
const crypto = require('crypto');
const path = require('path');

const directory = '/opt/nodebb-registry';
const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'manifest.json')));
const routes = new Map();
const expected = {
  compatible: ['/api/v1/plugins?version=4.1.0', 'compatible.json'],
  all: ['/api/v1/plugins', 'all.json'],
  trending: ['/api/v1/analytics/top/week', 'trending.json'],
  markdown: ['/api/v1/plugins/nodebb-plugin-markdown', 'markdown.json'],
};
for (const record of manifest.assessment.records) {
  const declaration = expected[record.kind];
  if (!declaration || record.file !== declaration[1] || routes.has(declaration[0]) ||
      record.url !== `https://packages.nodebb.org${declaration[0]}`) {
    throw Error('Snapshot route differs from reviewed declaration');
  }
  const filename = path.join(directory, record.file);
  if (!fs.lstatSync(filename).isFile()) throw Error('Snapshot must be a regular file');
  const body = fs.readFileSync(filename);
  const sha256 = crypto.createHash('sha256').update(body).digest('hex');
  if (body.length !== record.bytes || sha256 !== record.sha256) throw Error('Snapshot hash mismatch');
  routes.set(declaration[0], {body, sha256});
}
if (routes.size !== 4) throw Error('Incomplete registry snapshot inventory');

http.createServer((req, res) => {
  const snapshot = routes.get(req.url);
  const allowed = req.method === 'GET' || req.method === 'HEAD';
  const status = !allowed ? 405 : snapshot ? 200 : 404;
  const body = status === 200 ? snapshot.body : Buffer.from(JSON.stringify({error: 'unsupported registry request'}));
  res.writeHead(status, {'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': body.length, 'Cache-Control': 'no-store',
    ...(status === 405 ? {Allow: 'GET, HEAD'} : {})});
  res.end(req.method === 'HEAD' ? undefined : body);
  console.log(JSON.stringify({time: new Date().toISOString(), method: req.method,
    url: req.url, status, user_agent: req.headers['user-agent'] || '',
    sha256: status === 200 ? snapshot.sha256 : null}));
}).listen(8766, '127.0.0.1', () => {
  console.log(JSON.stringify({ready: true, condition: manifest.proposed_service.label,
    bind: '127.0.0.1', port: 8766, routes: routes.size}));
});
