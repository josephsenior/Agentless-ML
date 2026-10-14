'use strict';
const fs = require('fs');
const crypto = require('crypto');
const assert = require('assert');

async function main() {
  const manifest = JSON.parse(fs.readFileSync('/opt/nodebb-registry/manifest.json'));
  const origin = 'http://127.0.0.1:8766';
  const headers = {'User-Agent': 'agentless-registry-verifier'};
  for (let attempt = 0; ; attempt++) {
    try {
      const response = await fetch(`${origin}/api/v1/analytics/top/week`, {headers});
      assert.strictEqual(response.status, 200);
      await response.arrayBuffer();
      break;
    } catch (error) {
      if (attempt >= 49) throw error;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
  const checks = [];
  for (const record of manifest.assessment.records) {
    const endpoint = record.url.slice('https://packages.nodebb.org'.length);
    const response = await fetch(origin + endpoint, {headers});
    const body = Buffer.from(await response.arrayBuffer());
    const digest = crypto.createHash('sha256').update(body).digest('hex');
    assert.strictEqual(response.status, 200);
    assert.match(response.headers.get('content-type'), /^application\/json/);
    assert.strictEqual(body.length, record.bytes);
    assert.strictEqual(digest, record.sha256);
    const head = await fetch(origin + endpoint, {method: 'HEAD', headers});
    assert.strictEqual(head.status, 200);
    assert.strictEqual(Number(head.headers.get('content-length')), record.bytes);
    assert.strictEqual((await head.arrayBuffer()).byteLength, 0);
    checks.push({endpoint, get_sha256: digest, bytes: body.length, head_verified: true});
  }
  for (const [method, endpoint, status] of [
    ['GET', '/unknown', 404], ['GET', '/api/v1/plugins?version=999.0.0', 404],
    ['GET', '/api/v1/plugins/unknown', 404], ['POST', '/api/v1/plugin/usage', 405],
  ]) {
    const response = await fetch(origin + endpoint, {method, headers});
    assert.strictEqual(response.status, status);
    await response.arrayBuffer();
    checks.push({method, endpoint, status});
  }
  const result = {verified: true, condition: manifest.proposed_service.label, checks};
  fs.writeFileSync('/tmp/registry-verification.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
