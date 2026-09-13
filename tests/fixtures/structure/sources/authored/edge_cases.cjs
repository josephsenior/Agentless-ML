'use strict';

const path = require('path');
var legacy = 1, other = function () { return 2; };
let counter = 0;

function* gen() { yield 1; }
async function load(url) { return fetch(url); }

const arrow = async (x) => x * 2;
const objectLiteral = {
  name: 'x',
  'quoted-key': 1,
  42: 'answer',
  method() { return 1; },
  arrowProp: () => 2,
  nested: { deep: true },
  [computed]: 3,
  shorthand,
  get getter() { return 1; },
  set setter(v) {},
  async asyncMethod() {},
  *generatorMethod() {},
};

class Base {
  static count = 0;
  #secret = 1;
  field = () => this.#secret;
  constructor(a) { this.a = a; }
  static create() { return new Base(); }
  get value() { return this.a; }
  #privateMethod() {}
}

class Derived extends Base {
  run() { return super.value; }
}

module.exports = Derived;
module.exports.helper = function helper() {};
exports.value = 42;
exports.config = { enabled: true, toggle() {} };
Base.prototype.extra = function () {};

(function iife() {})();
if (counter) { function hoisted() {} }
