# seL4 #1843 — no-patch failure conditions, severity, and decision gate

Date: 2026-11-03. Research-only. No upstream modification.
Pinned upstream: seL4/seL4@15ec7bf82864e0505dc682051c0d688a946f5ece.

## Core conclusion

A nonaligned region is not automatically wrong. The condition is `base % Q != 0` AND (`size % Q == 0` OR `base % Q + size % Q > Q`) for positive length `size`, using device mapping page size `Q`. On a triggered input, the old range ends one aligned page early, but the *actual device bytes* omitted can be 1 to Q-1 bytes. The missing page of mapping/reservation is a page-sized authorization difference, not necessarily a page of useful registers.

In code, mapped prefix length is `min(kernel_size,device_size)` whereas reserved length is full `device_size`. Thus the two failure predicates are independent:
- **Mapping undercoverage** applies to truncated mapped prefix, and a kernel access in the missing tail is needed for an observed MMU fault / bad boot.
- **Reservation undercoverage** applies to the full device extent, even when the mapped prefix is short, and matters if it leaves a page available for device untyped issuance.

## Concrete cases for Q=4096

| Device `[base, base+size)` | kernel_size | Old mapped | Old reserved | Failure mode |
| --- | --- | --- | --- | --- |
| `[0x1000,0x2000)` | 0x1000 | [0x1000,0x2000) | same | none |
| `[0x1003,0x1023)` | 0x1000 | [0x1000,0x2000) | same | none |
| `[0x1003,0x2003)` | 0x1000 | [0x1000,0x2000) | same | mapped prefix tail 3 bytes missing; whole-device reserve tail 3 bytes missing |
| `[0x1003,0x3003)` | 0x20 | [0x1000,0x2000) | [0x1000,0x3000) | mapped requested prefix fully covered, but full-device reserve tail 3 bytes missing |

The reserve-only case is especially relevant to PR #1804: mapping first small prefix can be complete while the new full-device reserve still undercovers.

## Root-device untyped gate: source-backed conditions

In src/arch/{arm,riscv}/machine/hardware.c, `map_kernel_devices()` loops over generated `kernel_device_frames` for `map_kernel_frame`, and independently over `kernel_device_reserved_regions` for `reserve_region`.

In src/kernel/boot.c, `create_untypeds()` iterates the gaps between `ndks_boot.reserved` intervals, feeds gaps to `create_untypeds_for_region(...,true,...)`, and also fills to `CONFIG_PADDR_USER_DEVICE_TOP`. `create_untypeds_for_region` cuts the gap into size-aligned chunks and calls `provide_untyped_cap` only for chunks >= `seL4_MinUntypedBits`.

Consequently, undercoverage alone is insufficient to prove an extra device-UT capability. Further requirements include (i) the region is not user:true (such sharing is intentional), (ii) not independently reserved by another entry, (iii) falls in configured device-untyped addressability, (iv) sufficient aligned usable space, (v) initial task/capability recipients and their authority policy. Even a successful cap issue does not automatically transfer it to an untrusted task.

## Kernel fault gate

The generated MMIO mapping may be incomplete, but unless the kernel actually addresses registers in the omitted tail, there need not be a crash. If it does, CPU memory translation may fault or exhibit platform-specific consequences. The claim 'freezes CPU/GPU' is a **hypothesis**, not observed evidence.

For x86, the device generator does not share the ARM/RISC-V pipeline, so don't infer x86 impact.

## Severity prioritization

| Evidence | Classification | Recommendation |
| --- | --- | --- |
| A source-level invalid covering-region invariant + crafted DTB | confirmed build-time correctness issue | keep research and file precise issue |
| On supported board, an actively accessed kernel register is missing | boot/functional breakage | fix promptly once mapping/ownership assessed |
| On supported board, unreserved kernel-only MMIO page is issued as root device untyped | authority/boot policy deviation | prioritize, even without freeze |
| Cap is further provided to lower-trust component and maps privileged MMIO | potential security isolation consequence | dedicated security assessment/disclosure based on demonstrated conditions |
| No selected supported board hits trigger, no harmful capability change | latent bug only | issue and contract-focused regression first; broad patch needs maintainer decision |

## Incidence sample

Research run https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41629627065: 20 DTS+overlay platform selections, 62 kernel-selected regions, four unaligned bases, zero triggering undercoverage. This is a selected platform sample, not a probability estimate; conditional macros and future added boards require broader validation.

## Test added

`scripts/audit_no_patch_failure_modes.py` models no-patch mathematical outcomes under variations in user sharing, neighboring reserved regions, device-cap top and register accesses; explicitly does **not** claim to be real boot/cap test. CI workflow step added. Later seek a *legitimate supported configuration* that exhibits one of the two effects, and inspect actual resulting bootinfo capability slots if available.

No production or upstream changes.
