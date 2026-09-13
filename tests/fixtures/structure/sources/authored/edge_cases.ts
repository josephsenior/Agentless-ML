import type { Foo } from './foo';

export interface Props<T> extends Foo {
  readonly id: string;
  optional?: number;
  method(x: T): void;
  (call: string): number;
  new (ctor: string): Props<T>;
  [index: string]: unknown;
}

export type Union = 'a' | 'b';
type Mapped<T> = { [K in keyof T]: T[K] };

export enum Color { Red, Green = 'green' }
const enum Flags { A = 1 << 0 }

declare module 'external' {
  export function ext(): void;
}
declare global {
  interface Window { app: unknown }
}
declare const VERSION: string;
declare function declared(x: number): string;
export declare class DeclaredClass { method(): void; }

namespace Legacy {
  export const inside = 1;
}

export function overload(x: string): string;
export function overload(x: number): number;
export function overload(x: any) { return x; }

export abstract class Shape<T = number> {
  abstract area(): T;
  protected abstract name: string;
  private static instances = 0;
  public readonly id: string = '';
  declare brand: 'shape';
  constructor(private readonly size: number) {}
  handler = (event: Event): void => { console.log(event); };
  get perimeter(): number { return 0; }
}

export const typed: Record<string, () => void> = {
  run: () => {},
  stop() {},
};

export default {
  name: 'component',
  setup() { return {}; },
};

let cast = <number>(VERSION as unknown);
const satisfiesCheck = { a: 1 } satisfies Record<string, number>;
