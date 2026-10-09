// Diagnostic preload only. Observe launches and incoming requests without
// replacing arguments, environment, responses, assertions or process outcomes.
const fs = require('fs');
const cp = require('child_process');
const http = require('http');
const output = '/tmp/firefox-observer.jsonl';
function record(event) {
  fs.appendFileSync(output, JSON.stringify({time: Date.now(), ...event}) + '\n');
}
const spawn = cp.spawn;
cp.spawn = function (...args) {
  const child = Reflect.apply(spawn, this, args);
  if (String(args[0]).includes('firefox')) {
    const options = args[2] || {};
    const env = options.env || process.env;
    record({event: 'firefox_spawn', executable: args[0], args: args[1],
      cwd: options.cwd || process.cwd(), home: env.HOME,
      xdgCacheHome: env.XDG_CACHE_HOME, xdgConfigHome: env.XDG_CONFIG_HOME, pid: child.pid});
    for (const stream of ['stdout', 'stderr']) {
      if (child[stream]) child[stream].on('data', data =>
        record({event: 'firefox_' + stream, pid: child.pid, text: String(data)}));
    }
    child.on('exit', (code, signal) => record({event: 'firefox_exit', pid: child.pid, code, signal}));
    child.on('error', error => record({event: 'firefox_error', pid: child.pid, message: error.message}));
  }
  return child;
};
const emit = http.Server.prototype.emit;
http.Server.prototype.emit = function (event, ...args) {
  if (event === 'request' || event === 'upgrade') {
    const request = args[0];
    record({event: 'http_' + event, method: request.method, url: request.url,
      userAgent: request.headers['user-agent'], port: this.address()?.port});
  }
  return Reflect.apply(emit, this, [event, ...args]);
};
// Observe the real reporter's inputs and decisions. Always call the original
// method, retain its return value and never rewrite a reported result.
const Reporter = require(process.cwd() + '/lib/utils/reporter');
const report = Reporter.prototype.report;
Reporter.prototype.report = function (...args) {
  const returned = Reflect.apply(report, this, args);
  record({event: 'reporter_result', launcher: args[0], result: args[1],
    total: this.total, passed: this.passed, skipped: this.skipped, todo: this.todo});
  return returned;
};
const hasPassed = Reporter.prototype.hasPassed;
Reporter.prototype.hasPassed = function (...args) {
  const returned = Reflect.apply(hasPassed, this, args);
  record({event: 'reporter_has_passed', returned,
    total: this.total, passed: this.passed, skipped: this.skipped, todo: this.todo});
  return returned;
};
record({event: 'observer_loaded', node: process.version, home: process.env.HOME,
  observed: ['firefox_process', 'http', 'reporter_results', 'reporter_has_passed']});
