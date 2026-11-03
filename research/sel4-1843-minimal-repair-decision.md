# seL4 #1843 — minimum repair decision (research candidate)

Status: **candidate only, not upstream-ready**. Pinned base `15ec7bf82864e0505dc682051c0d688a946f5ece`.

## Source of the causal failure

An integer rounding function accepts one value and one alignment exponent, and does what it promises. `Region.align_size` instead promises a page-aligned **region**. Rounding its base down and its standalone size up independently is not enough because the left shift of the origin consumes length. A fix in the common `align_up` primitive would need to change its existing integer contract and risks unrelated call sites.

## Three alternatives

| Alternative | Correct reserved coverage? | Correct mapped coverage for nonempty requested prefix? | Blast radius |
| --- | --- | --- | --- |
| Change `hardware.utils.align_up` globally | Not established without altering its API | Not established | Unbounded other integer callers |
| Change only `KernelRegionGroup.reserved` | Yes | **No**: old `aligned=region.align_size` can still miss the mapped prefix end | Small edit but leaves known incomplete region |
| Correct `Region.align_size` with the lost offset | Yes | Yes, under the **cover-the-requested-prefix** contract | Two current call sites in `KernelRegionGroup` change together |

Candidate (not yet an upstream patch):

```python
new_base = hardware.utils.align_down(self.base, align_bits)
offset = self.base - new_base
new_size = (hardware.utils.align_up(self.size + offset, align_bits)
            if self.size else 0)
return Region(new_base, new_size, self.owner)
```

This is equivalent to rounding up the original interval's end for nonempty regions. The zero case deliberately preserves the existing `size==0` output and aligned-down base.

The local API is unchanged; most existing downstream build outputs remain byte-for-byte identical on page-aligned inputs. **But that does not mean the new mapping behavior has been contractually approved**.

## Why mapping change cannot be dismissed

`KernelRegionGroup` currently calls `Region.align_size` once for full-device reservation and once after limiting requested map length by `max_size`. A reservation-only patch still leaves the mapped prefix undercovered for certain nonaligned `base` values. Fixing mapping potentially uses one more aligned page, which is required if `kernel_size` means *bytes of the device starting at its base* rather than *number of pages*, but can map adjacent MMIO that needs careful ownership and overlap checks.

`tools/hardware_schema.yml` says `kernel_size` is the maximum size of the region in the kernel and describes page-rounded mapping of `min(kernel_size,region_size)` bytes starting at device base. The precise behavior when `base` is not page aligned is not expressly defined. The correct action depends on whether such device definitions are valid and supported.

## Test gates

- Pure-model differential: `scripts/compare_minimal_repair_paths.py` checks both mapped and reserved interval coverage over small exhaustive and large-page boundary cases. Tests actual alignment helper math against a separate mathematical formula. CI action added on research branch.
- Existing real-generator tests: `scripts/test_full_generator_unaligned.py`, `scripts/test_multi_output_contract.py`, `scripts/compare_real_platform_headers.py`.
- Not yet tested: real valid binding for a device with unaligned `reg`, full supported platform / overlay inventory, mapped-page ownership collision, complete architecture boot CI, QEMU runtime allocation behavior and hardware-specific safety.

## Decision / upstream threshold

Tentatively choose the local `Region.align_size` contract repair rather than modifying `align_up` or fixing only reservation. Do **not** push this candidate upstream until a supported input/binding contract has been established and mapping enlargement validated across relevant consumers. Reviewer asked for an issue first: present observed contract gap and uncertainty before opening another PR.
