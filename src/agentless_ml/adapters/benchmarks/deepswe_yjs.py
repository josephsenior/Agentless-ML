"""Reporting only: lib0 still owns discovery, filtering, seeds and repetitions."""

YJS_REPORTER = r"""
import { runTests as originalRunTests, skip } from 'lib0/testing'
import { writeFileSync } from 'node:fs'

// Compare the actual class, just as lib0.run does; an unrelated error named
// SkipError must not turn a failed test into a skip.
let SkipError
try { skip() } catch (error) { SkipError = error.constructor }

export const runTests = async (modules) => {
  const tests = []
  const wrapped = {}
  for (const moduleName of Object.keys(modules)) {
    wrapped[moduleName] = {}
    for (const name of Object.keys(modules[moduleName])) {
      const fn = modules[moduleName][name]
      if (!fn || !(name.startsWith('test') || name.startsWith('benchmark'))) {
        wrapped[moduleName][name] = fn
        continue
      }
      // Uninvoked tests were filtered by lib0: never count them as passing.
      const result = { suite: moduleName, name, status: 'skipped' }
      tests.push(result)
      wrapped[moduleName][name] = async (tc) => {
        try {
          await fn(tc)
          result.status = 'passed'
        } catch (error) {
          result.status = error.constructor === SkipError ? 'skipped' : 'failed'
          throw error
        }
      }
    }
  }
  const success = await originalRunTests(wrapped)
  // Only a completed original run earns a report. Import/setup errors must
  // not leave a partial passing inventory behind.
  writeFileSync('/tmp/ctrf.json', JSON.stringify({ results: { tests } }))
  return success
}
"""

YJS_PREPARE = r"""
const fs = require('node:fs')
const source = fs.readFileSync('tests/index.js', 'utf8')
const pattern = /import\s*\{\s*runTests\s*\}\s*from\s*['"]lib0\/testing['"]/g
if ([...source.matchAll(pattern)].length !== 1) {
  throw new Error('Yjs public entry point changed; review its reporting adapter')
}
fs.writeFileSync('tests/.agentless-entry.mjs', source.replace(pattern,
  "import { runTests } from './.agentless-reporter.mjs'"))
"""
