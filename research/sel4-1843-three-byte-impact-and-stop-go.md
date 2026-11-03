# seL4 #1843 — the 3-byte question and an economic stop/go gate

Date: 2026-11-03. Research-only; no upstream write.

## Clarification: 3 bytes is not a payload

The 3 bytes in the example `reg=[0x1003,0x2003)` are an *address tail* `[0x2000,0x2003)` omitted by the generator's old aligned region `[0x1000,0x2000)`. They do not mean 3 bytes of corrupted RAM, attacker-controlled payload, or writable boot scratch. A real device fixes what (if any) registers are at those addresses. An altered DTB can specify those addresses but cannot turn invalid silicon registers into valid ones.

The MMU and device-untyped representation are page-granular. The next page `[0x2000,0x3000)` may be either a missing kernel MMIO mapping or (under other necessary conditions) device-untyped capacity available for initial root task. One must never infer from the 3-byte gap that a three-byte capability is minted; see the actual `create_untypeds_for_region` size/alignment logic.

## Observable consequences without any patch

1. **Mapped-prefix failure:** a register access in the actual requested prefix beyond old map end can fault or fail. Hardware register accesses are normally 32-bit or wider and must comply with hardware's alignment/register semantics; not every last three bytes has accessible registers. Need actual MMIO register map and access trace.
2. **Reservation failure:** a kernel-exclusive device span extends past old reserved end. If an otherwise-unreserved page falls within `CONFIG_PADDR_USER_DEVICE_TOP`, the boot code can create device untyped capability for its surrounding free interval, subject to minimum untyped size and alignment. The root task can then retype device-untyped into a frame; actual untrusted access requires downstream delegation. The seL4 official CAVEATS.md explicitly states the root task is responsible for handing device capabilities only to sufficiently trusted drivers, and notes DMA-capable devices can bypass normal isolation if misconfigured.
3. **Neither:** a separate reservation covers that page, the range is intentionally `user:true`, the physical address is above the configured top, the kernel never accesses the omitted register addresses, or the particular hardware resource never straddles the page. These are credible no-harm paths.

## What we have measured

20 actual seL4 platform DTS + overlays, 62 selected kernel-device reg entries, four unaligned starts, zero trigger cases, zero generated-header diffs. CI https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41629627065 . Synthetic valid-ish PL310 DTB demonstrates generator undercoverage; its invented physical base has not been demonstrated on actual silicon.

Research-only fail-path model `scripts/audit_no_patch_failure_modes.py` has cases for mapping missing, reserved-only missing, user:true and already-reserved neighboring pages; successful workflow https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41634215423. It does not demonstrate actual fault or bootinfo capability issuance.

## Economic decision

**No justification for additional large CI/silicon work today** without a credible supported hardware target with a crossing-page selected device region. Do not claim CPU/GPU freeze, memory crash, or security vulnerability. Conversely, leave a small reproducible issue documenting the exact invariant and future platform risk as the defensible outcome, without pre-committing to a patch.

One cheap, high-value discriminating test if restarting the work: find an actual supported DTS/overlay and device datasheet whose kernel-selected MMIO region has (1) unaligned physical base, (2) spans beyond old page end, (3) kernel-only access, and (4) no independent reservation. If none, stop and park. A bootinfo-diff experiment using arbitrary MMIO addresses demonstrates the mechanics but not real-world security severity and should not be treated as substitute evidence.

## Verified docs

- https://docs.sel4.systems/Tutorials/untyped.html : device untyped retyped into frames, root task receives bootinfo untypeds.
- https://github.com/seL4/seL4/blob/master/CAVEATS.md : initial task's trust and DMA assumptions.
- https://www.sel4.org/Verification/assumptions.html : security proof hardware assumptions.
- https://devicetree-org.github.io/devicetree-specification/ : `reg` is address/length of bus resources, not necessarily RAM.
