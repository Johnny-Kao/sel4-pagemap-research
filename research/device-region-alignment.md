# Device region alignment — research branch

## Scope

This branch investigates a possible undercoverage bug in `tools/hardware/memory.py` of upstream `seL4/seL4`. This is separate from earlier Page_Map collision research. Do not interpret older Page_Map notes as a new security finding; upstream RFC [seL4/rfcs#34](https://github.com/seL4/rfcs/pull/34) documents the intentional architecture-specific behavior.

## Reproduced helper-level observation

For a half-open region `[base, base+size)` and a page-alignment quantum, independently rounding down `base` and rounding up `size` does not always produce an aligned region covering the original.

Example (4 KiB pages):
- Input: `[0x1003, 0x2003)`
- Observed from current `Region.align_size(12)`: `[0x1000, 0x2000)`
- Covering interval: `[0x1000, 0x3000)`

## Verification gates

1. Pin the upstream seL4 source SHA and import `Region` from the actual source.
2. Add a property regression checking `aligned.base <= original.base` and `aligned.end >= original.end` for nonnegative sizes, including zero-size edge semantics.
3. Trace real callers including `KernelRegionGroup` and device-region header generation. Show whether the mismatch reaches a supported platform.
4. Before drafting a fix, inspect adjacent previously merged [seL4/seL4#1804](https://github.com/seL4/seL4/pull/1804) and check whether callers depend on current alignment semantics.
5. Compare a minimal changed implementation against existing tests and focused, cheap synthetic tests. Do not claim a security vulnerability without evidence of an authority-boundary impact.

No upstream source code is changed by this note. No production PR is open.
