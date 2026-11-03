# seL4 #1843 — Split mapping / reservation repair experiment

Date: 2026-11-03. Status: **RESEARCH VALIDATED; upstream deferred**.
Repository: `Johnny-Kao/sel4-pagemap-research`
Branch: `research/device-region-alignment`
Pinned seL4 checkout: `15ec7bf82864e0505dc682051c0d688a946f5ece`

## Decision and scope

User chose to preserve 2019-era MMIO mapping output when valid, correct only the 2026 full-device reservation calculation, and refuse a hardware-generator input that would leave required mapped MMIO bytes inaccessible. This is a **research candidate**, not an upstream PR. No issue, PR, source edit, or other action was performed in seL4/seL4. The actual edits to upstream files during CI occur only in disposable checkout and are restored after tests.

The intent is to avoid requiring all existing Device Tree addresses to become page-aligned, and avoid expanding existing kernel MMIO frames when only a reservation correction is necessary. Full downstream safety cannot be guaranteed for a **new triggering** hardware layout because correcting the reservation intentionally removes a page from potential Device Untyped allocation.

## Source-level candidate

Change only `tools/hardware/utils/rule.py::KernelRegionGroup.__init__`:

```python
from hardware.utils import align_up

# Whole-device reservation uses the original physical range, before size truncation.
aligned_start = (region.base >> page_bits) << page_bits
aligned_end = align_up(region.base + region.size, page_bits)
self.reserved = Region(aligned_start, aligned_end - aligned_start, region.owner)

# Preserve 2019 mapping behavior for compatible layouts.
region.size = min(max_size, region.size)
aligned = region.align_size(page_bits)
if region.size and aligned.base + aligned.size < region.base + region.size:
    raise ValueError("kernel device mapping does not cover its configured MMIO range: ...")

self.size = aligned.size
self.base = aligned.base
self.regions = aligned.make_chunks(1 << page_bits)
self.labels[kernel_name] = region.base - aligned.base
```

The tested candidate is built automatically inside `scripts/test_split_mapping_reservation_candidate.py`; the illustrative code above is not a production patch. This preserves `Region.align_size` and `hardware.utils.align_up` unchanged.

### Important boundary

This guard does **not** repair a genuinely undercovered legacy kernel mapping; it rejects the configuration at generator time. Making such a new layout boot correctly still requires either more mapped pages or a configuration-specific change consistent with physical hardware. The reservation correction **does** cover the full original device extent, which can change ownership of the newly included physical page. Future design should consider zero-size semantics, conditional macros, user:true sharing, overlaps with neighboring kernel devices, and a potential cap-difference validation on realistic board input. These were not all exhaustively verified.

## Actual A/B GitHub Actions

- Passing run: https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41649721956
- Research test: https://github.com/Johnny-Kao/sel4-pagemap-research/blob/research/device-region-alignment/scripts/test_split_mapping_reservation_candidate.py

Tested with the **real pinned hardware_gen.py**:
1. `reservation-only-cross` — device [0x1003,0x2003), short kernel mapping prefix 0x20: unchanged mapped frames; reserved region grows [0x1000,0x2000) → [0x1000,0x3000).
2. `mapped-cross-rejected` — device same, full 4K kernel mapping requirement: generator stops with explicit mapping undercoverage error, instead of generating incomplete output.
3. `unaligned-short` — no change.
4. `aligned-full` — no change.
5. `start-near-boundary` — device [0x1fe0,0x2010), mapped prefix 0x20 ends exactly at page boundary: mapped frames unchanged, reservation grows one page.
6. Real DTS+overlay platforms: **20/20 generated C headers byte-identical** to pinned upstream. No claims about other boards or real boot. This is a targeted platform sample.

An earlier test iteration used a genuinely undercovered 32-byte mapped prefix while wrongly expecting acceptance; the tested guard rejected it correctly. Fixture was corrected to put the mapped prefix fully inside its original mapped page, and the complete workflow subsequently passed.

## Findings in user terms

- 2019 mapping for already-working platforms preserved, no new mapping page.
- 2026 reservation correctness improved for kernel-owned original device ranges.
- New triggering hardware with MMIO *mapping* problem must fail fast. New triggering hardware with *reservation-only* problem gains an additional reserved page; the change can affect downstream authorization.
- No need for an upstream PR now. This remains internal research; the user will decide if and when to submit upstream.
- No claim of real CPU/GPU freeze, actual vulnerability, or all-platform compatibility.

**Status: VALIDATED RESEARCH CANDIDATE; upstream not opened.**
