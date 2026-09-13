import fs from 'node:fs';

export const a = 1, b = () => 2;
export let mutable;
export function named() { return fs; }
export class Klass { m() {} }
export default async function () {}
export { a as alias };
export * from './other.js';
const local = 1;
export { local };
