'use strict';
const assert = require('assert');

describe('completion reporter fixture', function () {
  before(function () {
    if (process.env.REPORTER_FIXTURE_MODE === 'hook') throw Error('fixture hook failure');
    if (process.env.REPORTER_FIXTURE_MODE === 'dynamic') {
      const Mocha = require('/app/node_modules/mocha');
      this.test.parent.addTest(new Mocha.Test('added after run start', function () {}));
    }
  });
  it('passes', function () {});
  it('is pending', function () { this.skip(); });
  it('can fail', function () {
    assert.notStrictEqual(process.env.REPORTER_FIXTURE_MODE, 'bail');
  });
  it('must run for complete coverage', function () {});
  if (process.env.REPORTER_FIXTURE_MODE === 'duplicate') {
    it('repeated name', function () {});
    it('repeated name', function () {});
  }
});
