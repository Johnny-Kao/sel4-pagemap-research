# seL4 #1843: Maintainer-facing impact, ownership and repair decision

Date: 2026-11-03. Research only, upstream unchanged.
Pinned source: seL4/seL4 @ 15ec7bf82864e0505dc682051c0d688a946f5ece.
Related PRs: https://github.com/seL4/seL4/pull/1843 ; https://github.com/seL4/seL4/pull/1804 .

## Five direct questions

### 1. Why does it happen?

A Region is [base, base+size). The original align_size computes aligned_start = floor(base/page)*page, aligned_length = ceil(size/page)*page, and hence aligned_end = aligned_start + aligned_length. Once base is shifted left, the shifted offset must be included in the required span; the function omits it. Exact trigger for size>0: o=base%page >0 AND (size%page==0 OR o+(size%page)>page).

The bottom-level hardware.utils.align_up(num,bits) correctly aligns an integer. The interval composition is incorrect when the API requires a covering interval. The 2019 generator's label offset region.base-aligned.base is evidence it knew how to represent unaligned register bases.

### 2. Why did the 2026 modification matter?

PR #1804's author explicitly documented a pre-existing problem: mapping only the first part of certain device blocks caused the remainder to be handed out as device untyped. The fix introduced a separate full-device reservation, but it computes the new reserved range via the same legacy Region.align_size used for mapping. This new caller inherits its non-covering-range edge case.

### 3. Could the omitted page have been intentional boot/firmware headroom?

No source reviewed (2019 commit, 2026 PR, hardware_schema, hardware.yml, C generator, DTS selectors) documents a deliberately *unreserved terminal page* as bootloader scratch area or future rescue capacity. The old formula can OMIT trailing bytes; that is opposite of guaranteeing those bytes are reserved for boot firmware. Device Tree /reserved-memory carves RAM from normal usage, via hardware.utils.memory.parse_reserved_regions(), and is different from kernel-device MMIO reservation. Kernel start-up also explicitly reserves its code, initial task, memory regions. A board-specific bootloader scratch area could exist but needs its own board or DT evidence; never infer one from this arithmetic.

### 4. What actually fails (conditional, not observed)?

Given base=0x1003,size=0x1000,page=0x1000:
- physical resource [0x1003,0x2003)
- old mapped and reserved range [0x1000,0x2000)
- minimal covering interval [0x1000,0x3000)
- missing original resource bytes [0x2000,0x2003), only 3 bytes; page-granular reserved/mapping difference is 4 KiB.
A kernel register access inside those missing bytes could fault if it relies on a missing map; whether boot stalls depends on whether that access is executed, MMU/CPU architecture and exception handling. Missing reservation may allow a device untyped for the next page to be made available to root task *only if* it is within CONFIG_PADDR_USER_DEVICE_TOP, not reserved elsewhere, and correctly partitioned into untyped capabilities. seL4's root task and trusted driver policy determine whether it is actually remapped to an untrusted task. The page could contain device registers, privileged controls, DMA, etc.; misuse could cause device failure, interrupts, hangs or integrity breaches, but none are established from the interval arithmetic alone.
No automatic GPU, whole RAM crash or project-wide guarantee collapse is demonstrated.

Security significance conditional: seL4 isolation hinges on correct initial authority distribution, while official caveats explain device untyped caps are intentionally given to initial task and DMA-capable device access can circumvent hardware protection if entrusted to unsafe components. seL4's proofs have assumptions about boot and DMA. Sources:
https://github.com/seL4/seL4/blob/master/CAVEATS.md
https://docs.sel4.systems/Tutorials/untyped.html
https://docs.sel4.systems/projects/sel4/frequently-asked-questions
https://www.sel4.org/Verification/assumptions.html

### 5. Best repair, proof of compatibility, and cost

Preferred research candidate, conditional on accepted input contract:

```python
new_base = hardware.utils.align_down(self.base, align_bits)
offset = self.base - new_base
new_size = (hardware.utils.align_up(self.size + offset, align_bits)
            if self.size else 0)
return Region(new_base, new_size, self.owner)
```

Do NOT alter primitive align_up semantics; it is a value-rounding helper. Do NOT just fix reservation while mapped prefix can independently miss bytes. Do NOT reject all unaligned device bases; actual upstream sample includes such selected devices.

The candidate preserves any aligned input's exact output and integer API contract, but is **not globally guaranteed behavior-preserving**. Under a triggering input, it changes kernel_device_frames (mapped pages), kernel_device_reserved_regions, YAML/JSON user-device exclusions, and potentially register-symbol virtual offsets for subsequent groups; virtual device mapping window capacity and physical/virtual overlap must be checked. Explicit conditional macro and user:true cases and multiple devices sharing a page matter. If a new reservation overlaps another kernel-reserved device, get_reserved_regions may reject at build-time: a safer failure than silently assigning ownership, but still potentially breaks the build. The affected platform firmware and root-task capability layout could also change.
2019 schema had an incorrect max(kernel_size,region_size) phrase while implementation used min; #1804 updates docs to min, meaning one must not derive a strict historical contract from prose alone.

Current CI:
- https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41623290788 generator multi-output AB and 20 selected platform header comparisons PASS.
- https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41629627065 actual 20-platform selected-device inventory: 62 selected reg entries, four unaligned starts, zero tail-undercoverage triggers.
These are a sample, no actual triggered supported board or QEMU end-to-end capability test.

**Decision:** bug worth reporting as issue, not yet justified as an immediately mergeable PR. Maintainer can choose scope/risk with clear semantics. Next research gate: all-supported-platform selected-device inventory, device binding realism for a crossing-page input, conditional macro & shared-page tests, output+virtual offsets+capability comparison, and proof/test configuration impact. Avoid categorical claims that change is costless or all firmware preserved.

## Stakeholders / intent

seL4 is a high-assurance capability-based microkernel: isolation, confidentiality/integrity and resource-authority control. Its validation depends on correct system configuration and has boot/firmware/DMA assumptions. This generator executes at build time on a host, not on a low-end chip; the resulting kernel boot configuration does execute in embedded targets, including potentially hard-to-update deployments. The difference between 'build-tool arithmetic incorrect' and 'high-impact runtime fault' must be kept explicit.
