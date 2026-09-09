import type { Input } from "./input";

export interface Reader {
    read(input: string): number;
    ready?: boolean;
}

export type ID = string | number;
export enum State { Idle, Ready }

export default class Counter<T> {
    private value: number = 0;
    constructor(value: number) { this.value = value; }
    add = (amount: number): number => this.value + amount;
    static create(): Counter<number> { return new Counter(0); }
    get size(): number { return this.value; }
}

export const add = (a: number, b: number): number => a + b;
export async function fetchValue(id: ID): Promise<string> {
    // Braces in comments and templates must not change the span: }
    return `café {${id}}`;
}

const api = {
    run(input: number) { return input + 1; },
    stop: () => 0,
    label: "ready"
};

declare function external(input: string): number;
