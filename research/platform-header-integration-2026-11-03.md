# Real-platform header generation: baseline vs alignment candidate

**Date:** 2026-11-03 JST  
**Pinned upstream:** `seL4/seL4@15ec7bf82864e0505dc682051c0d688a946f5ece`  
**Verified CI:** https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41579095957  
**Comparison script:** `scripts/compare_real_platform_headers.py`

## Outcome

- Selected 20 actual DTS + platform overlay combinations from the pinned seL4 repository.
- Compiled each DTS + overlay into a DTB with `dtc`, then generated C headers through upstream `hardware_gen.py`.
- Compared baseline unmodified `tools/hardware/memory.py` against the candidate `Region.align_size()` change under the **same DTB/config**.
- **20/20 successful header generations; 0/20 headers changed.**
- Includes RPi4 8 GB memory-size overlay to supply valid physical memory definitions; initial integration attempt omitted it and thus failed to generate that platform.
- Baseline/candidate headers, `summary.json`, and any diffs are attached as short-retention CI artifacts.
- No QEMU kernel boot, runtime device isolation test or proof verification was performed.

## Interpreting the outcome

This does **not** disprove the independently reproduced mathematical undercoverage of `Region.align_size` for misaligned bases. It does show that the bug did not change generated headers for these 20 configured platforms. In particular, current selected real-world hardware data may be aligned such that the faulty case is not exercised.

**No evidence yet of a current supported-platform boot or memory-safety impact.** Do not claim a vulnerability or upstream-ready production fix based solely on synthetic inputs.

## Reproduction caveats and next gate

- Selected combinations are not an exhaustive list of all supported seL4 configurations, variants, memory sizes, or build flags.
- Generated-header equality does not establish safety of hypothetical unaligned device configurations.
- Before proposing an upstream PR: audit other callers of `align_size`, add a realistic controlled non-aligned DTB/device rule that passes the *full* `hardware_gen.py` pipeline, and determine whether the kernel has a supported-platform use case for the resulting correction.
- Without a concrete reachable scenario, classify as a low-priority helper robustness improvement rather than a demonstrated production defect.

## Gate

**Helper invariant: reproduced. Real-platform impact (20 selected configurations): not observed. Upstream PR: hold.**
