# seL4 #1843 — six-point root-cause evidence review

Date: 2026-11-03
Scope: research only; no upstream PR or issue submission.
Baseline: seL4/seL4 @ `15ec7bf82864e0505dc682051c0d688a946f5ece`.
Related review: https://github.com/seL4/seL4/pull/1843#pullrequestreview-5750586264

## 1. Exact root cause (source-confirmed)

`hardware.utils.align_up(num, bits)` computes `ceil(num / (1<<bits)) * (1<<bits)`; `align_down` similarly rounds an integer down. For nonnegative values and nonnegative bits, neither helper's arithmetic is independently incorrect.

In `tools/hardware/memory.py`, `Region.align_size()` constructs a new interval using `align_down(base)` and `align_up(size)` *separately*. This loses the offset subtracted from the base. If the intended contract is an aligned **covering** interval, it must use `align_up(base + size) - align_down(base)` for nonempty intervals.

This is a caller-level interval composition/contract error, not demonstrated to be a flaw in the shared integer `align_up` primitive. Reviewer's alternative location should be discussed respectfully, not simply accepted or dismissed.

## 2. Necessary/sufficient trigger (mathematical)

Let page size `Q=2**bits`, `o=base % Q`, and `r=size % Q`, with `size>0` and nonnegative addresses. Existing interval undercovers exactly when:
- `o>0`, AND
- `r==0` OR `o+r>Q`.

When it fails, the newly rounded end is **one full page** later than the baseline end; the source interval physically extends by at most `Q-1` bytes past the baseline boundary.

Example: `base=0x1003, size=0x1000, Q=0x1000`; original interval `[0x1003,0x2003)`; baseline `[0x1000,0x2000)`; covering interval `[0x1000,0x3000)`.

A nonzero unaligned base alone is insufficient when a short region fits before the first end boundary.

## 3. Production reachability (demonstrated up to generated header)

Upstream source connects Device Tree `reg` -> `WrappedNode.get_regions()` -> `DeviceRule.get_regions()` -> `KernelRegionGroup` -> `Region.align_size()` -> generated `kernel_device_reserved_regions`.

Prior research run https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41601717828 used the real `hardware_gen.py` pipeline and synthetic DTBs with the upstream `arm,pl310-cache` rule. Four test cases passed, including a baseline reservation ending too early in two positive cases.

These data **do not** show that an officially shipped/supported hardware DTS has the triggering address/size combination, or that the resulting kernel actually distributed an affected page.

## 4. Apparent architecture discrepancy (distinct mechanisms)

`tools/hardware/utils/__init__.py:align_up(num,bits)` is a power-of-two bit-boundary helper used by the hardware generator.

`libsel4/tools/syscall_stub_gen.py:align_up(x,a)` accepts an alignment **quantity** and is used for syscall argument bit packing, not for device reservation. Its `if x % a == 0` branch handles multiples including zero, but this does **not** imply the other helper mishandles zero (for nonnegative bits, hardware `align_up(0,bits)==0`).

ARM/RISC-V device-reservation changes in seL4 #1804 must be kept separate from prior Page_Map collision differences between x86_64, AArch64, RISC-V. Do not claim #1843 is independently a CPU-specific arithmetic difference.

## 5. Correct repair location and contract questions (partly open)

A local `Region.align_size` covering-range fix directly repairs the known interval invariant, but can affect BOTH `KernelRegionGroup.reserved` and the mapped `self.regions`; a shared `align_up` semantic change could affect all its callers and is not justified by the known integer examples.

Before recommending upstream code, inspect the intended handling of `size==0`, address-space limits, caller assumptions, config-specific page sizes, reserve/mapping overlaps, and whether to split mapped vs reserved contracts. The PR candidate preserved zero length but silently moves the empty region base downward; this policy is not yet formally validated.

## 6. Evidence limits / next discriminating test

Prior research: 20/20 selected real-platform generated headers unchanged (https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41579095957). This is a negative control, not proof of broad safety.

Next decisive check: inventory all supported DTS + platform overlays for triggering `(base,size,page_bits)` at kernel-device rules; where possible, inject a valid QEMU-supported DTB and compare **actual** reserved-region / device-Untyped issuance before vs after, without asserting a boot crash or isolation breach until observed. Compare mapped vs reserved separately.

**Interim classification:** reproducible production-generator *synthetic-input* interval undercoverage; actual supported-platform incidence and kernel/runtime harm not established. Issue-first approach requested by reviewer; no new PR should be submitted until the remaining causal gap is addressed.
