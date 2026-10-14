/* Run only in the pinned read-only container with a disposable /tmp.
 * No npm command, repository code, lifecycle script or public test is executed.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const source = '/app/node_modules';
const target = '/tmp/dependency-assessment/node_modules';

function inventory(root) {
  const digest = crypto.createHash('sha256');
  const result = { files: 0, links: 0, bytes: 0, externalLinks: [] };
  function walk(directory) {
    for (const name of fs.readdirSync(directory).sort()) {
      const filename = path.join(directory, name);
      const stat = fs.lstatSync(filename);
      const relative = path.relative(root, filename);
      if (stat.isDirectory()) {
        walk(filename);
      } else if (stat.isSymbolicLink()) {
        result.links++;
        const link = fs.readlinkSync(filename);
        digest.update(JSON.stringify(['link', relative, link]) + '\n');
        const resolved = fs.realpathSync(filename);
        if (!resolved.startsWith(root + '/')) result.externalLinks.push({ relative, link, resolved });
      } else if (stat.isFile()) {
        result.files++;
        result.bytes += stat.size;
        const sha256 = crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
        digest.update(JSON.stringify(['file', relative, stat.mode & 0o777, stat.size, sha256]) + '\n');
      } else {
        throw Error('unsupported dependency entry: ' + relative);
      }
    }
  }
  walk(root);
  return { ...result, sha256: digest.digest('hex') };
}

const started = Date.now();
const before = inventory(source);
if (before.externalLinks.length) throw Error('source dependency links escape tree');
fs.mkdirSync(path.dirname(target));
// Dropped capabilities deliberately forbid restoring the image's UID/GID.
// Keep content, modes and symlinks; the disposable copy belongs to this user.
execFileSync('cp', ['-a', '--no-preserve=ownership', source, target], { timeout: 120000 });
const copied = inventory(target);
if (copied.sha256 !== before.sha256 || copied.externalLinks.length) throw Error('copy differs or links escape');
for (const relative of ['.bin/acorn', 'acorn/package.json']) {
  const original = path.join(target, relative);
  const temporary = original + '.agentless-write-probe';
  fs.renameSync(original, temporary);
  fs.renameSync(temporary, original);
}
const probe = path.join(target, 'acorn/.agentless-write-probe');
fs.writeFileSync(probe, 'disposable write check', { flag: 'wx' });
fs.unlinkSync(probe);
const restored = inventory(target);
const after = inventory(source);
if (restored.sha256 !== before.sha256 || after.sha256 !== before.sha256) throw Error('source or restored copy changed');
const optionalRead = filename => fs.existsSync(filename) ? fs.readFileSync(filename, 'utf8').trim() : null;
console.log(JSON.stringify({
  condition: 'Offline writable dependency-copy diagnostic only',
  source: before, copy: copied, restoredCopyMatches: true, sourceUnchanged: true,
  binRenamePassed: true, packageRenamePassed: true, packageWritePassed: true,
  copyContainsHiddenLock: fs.existsSync(path.join(target, '.package-lock.json')),
  memoryPeakBytes: optionalRead('/sys/fs/cgroup/memory.peak'),
  memoryMaxBytes: optionalRead('/sys/fs/cgroup/memory.max'),
  scratch: execFileSync('df', ['-k', '/tmp'], { encoding: 'utf8' }).trim(),
  elapsedSeconds: (Date.now() - started) / 1000,
  npmInstallRun: false, publicTestsRun: false, imageBuilt: false,
}, null, 2));
