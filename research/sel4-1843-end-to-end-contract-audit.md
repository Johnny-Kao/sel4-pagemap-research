# seL4 #1843 — end-to-end contract and causality audit

Date: 2026-11-03. Research branch only; original PR #1843 is closed. No upstream write.

## Decision standard
Three independent proof obligations:
1. **Input validity** — Is an unaligned DT `reg` size/base a valid, supported input for a kernel-mapped device, or an upstream-invalid DT/binding that should be rejected earlier?
2. **Interval semantics** — Does each consumer require (A) a containing page-aligned interval, (B) a capped amount of kernel-mapped data, or (C) a truly empty zero-sized interval?
3. **Runtime effect** — Does the generated reservation difference affect a booted kernel's reservations or untyped-cap availability on a supported target?

A successful arithmetic test cannot prove #1 or #3.

## Verified history and actual contracts

- The alignment formula predates #1804; it arrived with the 2019 hardware generator rewrite, commit `75f2c54b42`.
- #1804 (merged 2026-10-26) explicitly separated mapped device pages from full-device reservations. It introduced `KernelRegionGroup.reserved = region.align_size(page_bits)`, then truncated `region.size = min(max_size, region.size)` and independently called `align_size(page_bits)` for mapped pages.
- `tools/hardware_schema.yml` describes `kernel_size` as the maximum portion mapped to the kernel, and the full device as reserved unless `user: true`. The wording uses `PAGE_ALIGN_UP(min(kernel_size,region_size))` and must be reconciled with unaligned base offsets; the schema does not explicitly constrain `reg` base or region size to page multiples.
- The Device Tree `reg` values pass via `WrappedNode.get_regions()` to a `Region` without page-alignment validation. There is an address-translation step (`_translate_child_address`) that must also be audited for input validity and integer range.
- `get_reserved_regions` checks for overlapping kernel reserve ranges; `c_header.py` emits these into `kernel_device_reserved_regions`. `outputs/yaml.py` and `outputs/json.py` also consume `get_addrspace_exclude` on the reserved ranges. Thus two distinct output families depend on the same reserve contract.
- `Config.get_device_page_bits`: ARM defaults to 12 (4 KiB); RISC-V32 uses 22 (4 MiB); RISC-V64 uses 21 (2 MiB). This makes the triggering cases and total mapped/reserved page deltas architecture-configuration-sensitive, although the underlying Python formula is common. The generator's `get_arch_config` does not accept x86; do not conflate this with independent Page_Map collision research.

## Mechanism and proof

Let `Q=2**bits`, `o=base%Q` and `r=size%Q`. For positive `size`, old aligned interval `[floor(base/Q)*Q, floor(base/Q)*Q + ceil(size/Q)*Q)` fails to contain the input exactly if `o>0 and (r==0 or o+r>Q)`. This is not a property of `align_up` alone. The minimally covering interval ends at `ceil((base+size)/Q)*Q`.

A candidate correction can cause **one more mapped page**, not only one more reserved page, because `KernelRegionGroup.__init__` makes both calls. This is NOT automatically a bad change: a missing page may be necessary for the requested mapped bytes. It requires separate checks on MMIO page coverage, `kernel_size`, overlap with other device registers, and kernel virtual-space limits. The earlier PR's `size==0` branch keeps the length at zero but changes the base to `floor(base/Q)*Q`; zero-length semantics remain undecided.

Two functions with the same name have distinct API contracts:
- `hardware.utils.align_up(num,bits)`: bits-to-power-of-two quantum.
- `libsel4/tools/syscall_stub_gen.py:align_up(x,a)`: explicit alignment quantum for marshalling. Both are equivalent when `a=1<<bits` for nonnegative values. The explicit multiple/zero check in the latter does not expose a zero bug in the former.

## Regression suite status

Pre-existing CI (2026-11-03) used a real DTB and a valid `hardware.yml` matching compatible `arm,pl310-cache` to show baseline generated header undercoverage on synthetic input; four generator assertions passed. In the same run 20 selected actual platform outputs were unchanged. This is sufficient to prove production build-tool reachability from a crafted DTB, but *not* observed incidence on real supported targets.

New `scripts/audit_alignment_contract.py`: exhaustive combinations for small alignment quanta, equivalence tests for helper API semantics, exact trigger assertion, and mapped-versus-reserved deltas. The workflow invokes it. It is an arithmetic/model audit rather than full kernel execution.

## Additional gates before any upstream patch

**Input validity / upstream origin**
- Enumerate the actual matched kernel devices (DT `chosen/seL4,kernel-devices`, compatible, relevant YAML region index), including address translations and overlay results, for supported ARM/RISC-V targets.
- Validate whether device-tree bindings or platform CMake invariants *guarantee* alignment. Do not infer an input contract solely from passing 20 platforms.
- Test a realistic misaligned MMIO definition tied to an actual board or supported emulated device, instead of relying on an arbitrary fabricated PL310 `reg` address.

**Contract change containment**
- A/B compare generated C header **mapped frames** and **reserved intervals**, plus YAML/JSON exclusions, not just reserved intervals.
- Check conditional `macro`, `user: true`, duplicate grouped regions, overlap rejection, zero-sized regions, and word-width boundary behavior.
- Verify that a corrective change doesn't accidentally add a kernel mapping beyond intended `kernel_size` semantics or into neighboring unrelated MMIO.

**Downstream impact**
- Confirm consumer behavior in kernel early-boot `map_kernel_devices`, `reserve_region`, and user untyped creation; use an emulator only where platform configs support those routes.
- Never equate a generated-header delta with a confirmed boot failure, capability exposure, or privilege separation breach.

## Upstream submission gate

Do not reopen the patch just because a synthetic interval is wrong. Require (a) documented input contract; (b) caller-by-caller behavioral contract with a negative-control matrix; (c) updated generated output evidence; (d) a supported-target or clearly stated synthetic-only impact; (e) CI results on the exact final patch; and (f) a concise issue-first explanation of why the existing behavior violates an intended property.

Potential alternative outcomes remain open:
1. reject malformed inputs upstream, if contract strictly mandates alignment;
2. fix `Region.align_size` if it promises a containing interval;
3. separately correct mapping/reservation calculation if their contracts intentionally diverge;
4. leave production behavior unchanged and only tighten tests/docs if relevant input is unsupported.

No outcome is preselected.
