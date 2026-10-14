'use strict';

// Keep Mocha's normal JSON results and record the loaded test inventory before
// hooks run. With bail enabled, an ordinary end event can still be incomplete.
const fs = require('fs');
const JSONReporter = require('/app/node_modules/mocha/lib/reporters/json');
const auditPath = '/tmp/nodebb-completion.json';
const rawKey = test => JSON.stringify([test.file || '', test.fullTitle()]);

module.exports = class CompletionReporter extends JSONReporter {
  constructor(runner, options) {
    super(runner, {...options, reporterOption: {...options.reporterOption, output: '/tmp/nodebb-raw.json'}});
    const audit = {
      schema_version: 1, run_started: false, run_ended: false,
      aborted: false, planned: [], ended: [], hook_failures: [],
      dynamically_added: 0,
    };
    const identities = new WeakMap();
    const occurrences = new Map();
    const observedSuites = new WeakSet();
    const save = () => fs.writeFileSync(auditPath, JSON.stringify(audit, null, 2));
    const register = test => {
      if (identities.has(test)) return identities.get(test);
      const raw = rawKey(test);
      const occurrence = (occurrences.get(raw) || 0) + 1;
      occurrences.set(raw, occurrence);
      const fullTitle = `${test.fullTitle()} [occurrence ${occurrence}]`;
      const identity = {file: test.file || '', fullTitle, rawFullTitle: test.fullTitle()};
      identities.set(test, identity);
      audit.planned.push(JSON.stringify([identity.file, identity.fullTitle]));
      audit.runner_total = audit.planned.length;
      if (audit.run_started) audit.dynamically_added++;
      return identity;
    };
    const observe = suite => {
      if (observedSuites.has(suite)) return;
      observedSuites.add(suite);
      suite.tests.forEach(register);
      suite.suites.forEach(observe);
      suite.on('test', register);
      suite.on('suite', observe);
    };
    observe(runner.suite);
    const originals = {tests: [], passes: [], failures: [], pending: []};
    save();
    runner.once('start', () => {
      audit.run_started = true;
      audit.initial_runner_total = runner.total;
      audit.initial_planned_tests = audit.planned.length;
      save();
    });
    runner.on('test end', test => {
      const identity = register(test);
      audit.ended.push(JSON.stringify([identity.file, identity.fullTitle]));
      originals.tests.push(test);
    });
    runner.on('pass', test => originals.passes.push(test));
    runner.on('pending', test => originals.pending.push(test));
    runner.on('fail', (test, error) => {
      originals.failures.push(test);
      if (test.type !== 'test') {
        audit.hook_failures.push({key: rawKey(test), message: String(error && error.message)});
      }
    });
    runner.once('end', () => {
      audit.run_ended = true;
      audit.aborted = Boolean(runner._abort);
      audit.stats_tests = runner.stats.tests;
      // JSONReporter has already written the unmodified report. Build a second
      // report with identities tied to the actual test objects, not display
      // names, so repeated names and late registrations cannot collapse cases.
      const report = {...runner.testResults};
      for (const field of Object.keys(originals)) {
        report[field] = report[field].map((entry, index) => {
          const identity = identities.get(originals[field][index]);
          return identity ? {...entry, ...identity} : entry;
        });
      }
      fs.writeFileSync(options.reporterOption.output, JSON.stringify(report, null, 2));
      save();
    });
  }
};
