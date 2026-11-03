# seL4 #1843 — device bindings, boot-stage provenance and historical contract audit

Date: 2026-11-03. Scope: read-only upstream investigation; research fixture improvements only. No upstream PR.

## Executive decision

**The generic Device Tree contract does not mandate page-aligned `reg` start/size; neither do the specific `reg` declarations examined for PL310, PL011, SiFive CLINT and PLIC.** However, the physical register layout and supported seL4 platform configuration are additional restrictions. A syntactically valid or even schema-valid DTB is **not** proof that a particular chip physically exists at the invented address.

A conservative upstream fix must distinguish:
1. *DTSpec valid* versus *device-binding valid* versus *actual platform-supported* versus *kernel user capability exposed*.
2. Original MMIO resource range (`reg = <address length>`) versus seL4 kernel mapped prefix (`kernel_size`) versus seL4 kernel full-device reserved span.
3. Frame-granularity backing from any deliberate spare area. An unreserved terminal page is not documented redundant/slack space.

## Binding verification

Reference generic Device Tree Specification §2.3.6: https://devicetree-org.github.io/devicetree-specification/ — `reg` comprises address/length pairs in the parent bus address space, not page-granularity allocation units.

Concrete relevant Linux bindings (versions consulted 2026-11-03):
- ARM PL310 (`arm,pl310-cache`): https://www.kernel.org/doc/Documentation/devicetree/bindings/arm/l2c2x0.yaml . `reg: maxItems: 1`; required `compatible, cache-unified, reg`; no explicit 4KiB align constraint in the `reg` schema. Provided example is aligned at `0xfff12000` of size `0x1000`. This fixture therefore needs `cache-unified`. It **does not** establish that a hypothetical PL310 at `0x1003` is a physically plausible board.
- ARM PL011 (`arm,pl011`): https://www.kernel.org/doc/Documentation/devicetree/bindings/serial/pl011.yaml . `reg: maxItems: 1`, required `compatible, reg, interrupts`. No explicit page align constraint in `reg`; example is page aligned.
- SiFive CLINT (`sifive,clint0`): https://www.kernel.org/doc/Documentation/devicetree/bindings/timer/sifive,clint.yaml . `reg: maxItems: 1`; required `compatible, reg, interrupts-extended`; no explicit page align condition in `reg`; example is aligned.
- SiFive PLIC (`sifive,plic-1.0.0`): https://www.kernel.org/doc/Documentation/devicetree/bindings/interrupt-controller/sifive,plic-1.0.0.yaml . `reg: maxItems: 1`; required additional interrupt metadata; no explicit page align condition in `reg`; example is aligned.

**Binding validation caveat:** earlier research synthetic PL310 DTBs omitted `cache-unified`, which its binding requires. The actual seL4 hardware generator still generated an output because it validates `hardware.yml` against `tools/hardware_schema.yml`, **not** every DTB device node against Linux's DT bindings. The research fixture was updated in `scripts/test_full_generator_unaligned.py` and `scripts/test_multi_output_contract.py` to add `cache-unified;`. Still do not claim complete `dt-validate` schema verification, chip realism, or boot reproducibility merely from this addition.

## Where upstream assumptions enter the chain

DTB `reg` -> `FdtParser.get_kernel_devices()` resolves **only nodes explicitly listed in `/chosen/seL4,kernel-devices`** -> `WrappedNode.get_regions()` converts parent bus address to physical addresses and keeps region length -> compatible-based `DeviceRule.get_regions()` resolves `kernel_size` and page quantum -> `KernelRegionGroup` calls `align_size` for reservation and map prefix -> C/YAML/JSON generation -> kernel ARM/RISC-V `map_kernel_devices()`, `reserve_region()`, `create_untypeds()`.

The selector is a major reachability filter: an arbitrarily malformed DT node that is not chosen as a kernel device cannot be cited as a real kernel-device mapping bug.

Device Tree `ranges` address translation must be included when looking for final physical base alignment: it can change the offset of a selected child resource. Need verify translation is valid over the *whole* `reg` interval; current `_translate_child_address` translates a base value, not both ends.

## History and interpretation

2019 `75f2c54b42`: `Region.align_size` already computed `align_down(base), align_up(size)`. `KernelRegionGroup` truncated to `min(max_size,region.size)` and computed the register symbol's page offset `region.base - aligned.base`, indicating awareness of non-page-aligned register addresses. The 2019 schema incorrectly documented `max(kernel_size,region_size)` despite executing `min`, so historical prose cannot be assumed to be flawless.

2026 #1804: explicitly states the old implementation mapped only a prefix and inadvertently exposed another part of the device to user level; the **new reservation contract** is the whole device, but its implementer reused the 2019 helper. #1804 described leaving mapped regions unchanged. This creates a new dependency on `align_size` for full-device protection; it does *not* introduce the arithmetic undercoverage itself.

No retrieved source asserts that the difference between `align_up(base), align_up(size)` is deliberate extra headroom or reserved slack. The old expression can OMIT the tail from mapping/reservation; this would be the opposite of defensive reservation.

## kernel_size: exact anchor

`KernelRegionGroup` truncates `region.size = min(max_size, region.size)` *before* invoking `align_size` and then generates a symbol at `region.base - aligned.base`.

Hence `kernel_size` controls a **byte count beginning at the raw/translated DT device base**, not a number of pages beginning at the rounded-down mapping start. A mapping honoring the requested bytes must cover `[base, base + min(kernel_size, device_size))`; page mapping necessarily covers adjacent bytes when the physical base is unaligned. This makes an extra page the expected page-granular physical outcome, not a preference.

## Limits and gate

- Earlier 20 platform A/B generated headers showed no difference. This is evidence the trigger is not demonstrated on those matched selected kernel devices; not a guarantee for all seL4 platforms.
- No actual platform's boot failure, freeze, real-world capability disclosure, or device register collision has been demonstrated; avoid those claims.
- The next discriminating task is an **exhaustive supported-platform, selected-kernel-device inventory**, capturing final translated base, length, `kernel_size`, architecture-specific device page size, and binding constraints; compare where a patched map adds a page and the ownership of that page.
- If all *actual supported* selected devices satisfy offset+size coverage by coincidence, the concern remains a latent contract error, not confirmed deployed breakage. Reviewer issue-first request is justified; do not submit a replacement PR until the scope is demonstrated.

Sources: links above; upstream pinned `15ec7bf82864e0505dc682051c0d688a946f5ece`.
