# Full production-generator validation — unaligned device region

Date: 2026-11-03 JST  
Upstream pinned source: `seL4/seL4@15ec7bf82864e0505dc682051c0d688a946f5ece`  
CI: https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41601717828  
Test: `scripts/test_full_generator_unaligned.py`

## Mechanism

A Device Tree `reg` describing an unaligned device MMIO area is accepted by the normal seL4 build-tool pipeline. The ordinary production `hardware.yml` rule for `arm,pl310-cache` selects it as a kernel device. `KernelRegionGroup` uses `Region.align_size(page_bits)` to calculate mapped and reserved ranges. With base=0x1003, size=0x1000, rounding the base down but rounding size independently causes a computed region [0x1000,0x2000) that **does not contain the source [0x1003,0x2003)**.

The candidate computes `new_end=align_up(base+size)` and `new_size=new_end-new_base`, retaining the old zero-size behavior.

## Actual pipeline evidence

DTS -> `dtc` DTB -> upstream `FdtParser` -> `HardwareYaml` / `KernelRegionGroup` -> `hardware_gen.py --c-header` -> parsed `kernel_device_reserved_regions` (not a mocked generator).

| Case | Original device | Baseline reservation | Candidate reservation | Expectation |
|---|---|---|---|---|
| unaligned-cross-page | [0x1003,0x2003) | [0x1000,0x2000) | [0x1000,0x3000) | candidate covers; baseline does not |
| aligned-control | [0x1000,0x2000) | [0x1000,0x2000) | unchanged | no difference |
| unaligned-within-page | [0x1003,0x1023) | [0x1000,0x2000) | unchanged | no difference |
| unaligned-cross-two-page | [0x1ff0,0x2020) | [0x1000,0x2000) | [0x1000,0x3000) | candidate covers; baseline does not |

All 4 generated-header integration assertions PASS. Existing 20 selected actual platform DTS + overlays also generated and yielded **0 changes** in this CI. Actual supported-platform incidence has not been demonstrated. No QEMU/device boot or security breach has been demonstrated.

## History and duplication

`Region.align_size` formula dates to initial hardware generator rewrite in 2019 (`75f2c54b42`). Merged upstream PR [#1804](https://github.com/seL4/seL4/pull/1804) (2026-10-26) introduced separated full-device reserved ranges using this helper; the old formula itself was not added by that PR. A text query of upstream PRs found no direct alignment-formula fix, but a final duplicate search against HEAD should precede filing.

## Decision

**Research Gate: PASS** for a reproducible **production build-tool correctness/interval-calculation bug**, with a feasible minimal patch and negative controls. **Do not characterize as demonstrated hardware damage, hang, memory-safety CVE, or platform-wide impact.** Upstream scope suggested: narrow `align_size` fix + regression test; review caller side effects, overlaps and zero-size before submitting. No upstream PR created.
