# Koota tracking-query overflow: upstream report draft

Status: documented locally; no upstream issue has been submitted.

## Proposed issue

Title: Tracking query can hang when the target trait uses bit 30

At commit `9c434858b2b522002f8c5eb4a554fa8836a7cf3c`, the initial tracking-query
population loop in `packages/core/src/query/query.ts:372` scans a bitmask with:

```ts
for (let bit = 1; bit <= mask; bit <<= 1) {
```

For `mask = 1073741824` (`2**30`), a matching entity can reach the end of the
loop body at that bit. The next signed shift produces `-2147483648`, then zero.
Both remain less than the positive mask, and subsequent shifts of zero remain
zero. Query execution never returns.

The trait allocator permits this bit: `incrementWorldBitflag` rolls over only
when the next flag reaches `2**31`. This is therefore a valid allocation state.

Minimal standalone reproduction, requiring no aspect implementation:

```ts
import { it } from 'vitest';
import { createWorld, trait, createChanged } from '../src';

it('queries a changed trait at bit 30', () => {
    const world = createWorld();
    for (let i = 0; i < 29; i++) world.onAdd(trait(), () => {});
    const Target = trait({ x: 0 });
    world.onAdd(Target, () => {});
    const Changed = createChanged();
    const entity = world.spawn(Target);
    entity.set(Target, { x: 1 });
    world.query(Changed(Target));
});
```

Place this under `packages/core/tests/` and use an external process timeout:
this is a synchronous loop, so an ordinary asynchronous test timeout may not
interrupt it. Expected behavior is a terminating query containing the changed
entity. The uninstrumented loop instead continues indefinitely.

Verification used the repository's pinned image with Node/Vitest dependencies.
In a disposable copy, a diagnostic check that throws when `bit <= 0` captured
`bit=-2147483648 mask=1073741824 worldTraits=31`. This was reproduced without
applying the generated candidate patch. The tripwire detects the overflow;
it does not repair the loop.

## Treatment in our evaluation

A defect in the repository under repair does not alone invalidate a repair task.
The generated Koota patch's retained aspect registrations expose this existing
loop bug. We retain its official timeout, the original selected prediction and
all diagnostic evidence. We have not patched the benchmark environment or
excluded the task after seeing its result.

If an environment correction or exclusion is proposed, agree that policy with
Professor Zhang first. An exclusion needs a documented reason independent of
which system failed. A corrected environment needs a versioned setup applied
consistently to both systems, with original results retained separately.
These are evaluation decisions, not changes to make silently during a run.

The synthetic reproduction above can be reported upstream separately. It does
not reproduce or quote the benchmark's held-out test file.

[Diagnostic evidence](../../experiments/pilots/deepswe_small_v2/koota_sample_two_stall_2026-11-09.md).
