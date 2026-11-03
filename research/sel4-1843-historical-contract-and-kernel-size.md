# seL4 #1843 — historical implicit contract and kernel_size anchoring

Research as of 2026-11-03. Upstream unmodified. Source inspection and a source-model regression; not a claim about contributor intentions or actual physical hardware failures.

## Findings

1. **Generic upstream Device Tree contract:** DTSpec 2.3.6 defines `reg` as address/length pairs. It does not impose a generic 4-KiB/device-page alignment requirement. This does not exclude stricter device-specific bindings. Reference: https://devicetree-org.github.io/devicetree-specification/ section 2.3.6.

2. **2019 original Python contract:** commit https://github.com/seL4/seL4/commit/75f2c54b42c2dbea56ca91ae6b029c3d3ad8eed4 introduced `Region.align_size` with separate `align_down(base)` and `align_up(size)`. It also introduced `KernelRegionGroup` that performs `region.size = min(max_size,region.size)` **before** `aligned = region.align_size(page_bits)`. Importantly, `self.labels[kernel_name] = region.base - aligned.base`: the intended register access points to the original DT base *within* the aligned page, i.e. non-page-aligned start addresses were at least contemplated by that offset machinery. This alone does not prove they were supported as an explicit guarantee.

3. **Historic documentation inconsistency:** the 2019 `tools/hardware_schema.yml` says `PAGE_ALIGN_UP(max(kernel_size,region_size))` even though the code uses `min(max_size,region.size)`. PR #1804 (merged 2026-10-26) corrects documentation to `min` and says explicitly that the kernel maps only an initial portion but must reserve the entire device, except where user-sharing is allowed. Historical docs are not infallible proof of the intended implementation contract. Source: https://github.com/seL4/seL4/pull/1804.

4. **Actual `kernel_size` anchor:** it is a byte count starting at the **original device base** obtained from `reg` after address translation; it is *not* a byte count starting at the rounded-down page base. Exact source:
```python
region.size = min(max_size, region.size)
aligned = region.align_size(page_bits)
self.labels[kernel_name] = region.base - aligned.base
```
Consequently, the intended prefix in physical addresses is `[base, base + min(kernel_size,original_size))`. Page mapping must cover this prefix if mapping is promised. For `base=0x1003, kernel_size=0x1000, original_size>=0x1000, page=0x1000`, the prefix ends at `0x2003`; mapping one page `[0x1000,0x2000)` leaves the last three bytes unmapped. A two-page mapping covers those bytes, but physically mapping a page can overlap adjacent devices and needs ownership validation.

5. **The deliberate 'slack/reserve for future bug fixes' hypothesis:** no historical commit text, method comments, or current schema establishes a planned free area from this rounding discrepancy. When present, the old calculation **under-covers** the declared region rather than reserving spare space. A safe, explicit guard region would typically increase the reserved extent, not omit trailing physical bytes. Do not represent this hypothesis as a confirmed design decision. Negative evidence is not proof that designers never had such an intent.

6. **2026 change of impact without change of formula:** #1804 leaves mapped regions untouched and adds reservation of full DT region, reusing the same `align_size`. That broadens the interval algorithm's safety obligations to reservations; it does not establish an x86-specific code path (hardware_gen supports ARM/RISC-V).

## Remaining validation

- Binding-by-binding check of supported DT + YAML kernel-device configs for promised alignment and realistic nonaligned addresses.
- A/B check full kernel mapping windows, generated register symbols, overlaps, user: true, optional macros.
- Simulator/boot verification and actual capability accounting on supported targets.
- Discuss contract with maintainer via issue before any upstream PR.

## CI

`scripts/audit_historical_kernel_size_anchor.py` checks concrete boundary cases and preserved register pointer offsets; workflow step added to research branch. No production code changed.
