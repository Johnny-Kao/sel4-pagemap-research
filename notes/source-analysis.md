# Source inspection — provisional

Target: upstream seL4 `master`, retrieved 2026-11-02. Precise CI SHAs must be taken from `results/build-info.txt` artifacts once runs finish.

- ARM64: `src/arch/arm/64/kernel/vspace.c`, `decodeARMFrameInvocation` / `performPageInvocationMap`. Frame metadata is set before lookup; occupied PTE is not rejected in the path inspected; `performPageInvocationMap` writes `*ptSlot = pte`.
- x86: `src/arch/x86/kernel/vspace.c`, `createSafeMappingEntries_PTE` and `performX86PageInvocationMapPTE`. PTE helper checks lookup success but not present-PTE collision. Large-page helper has `seL4_DeleteFirst` check.
- RISC-V: `src/arch/riscv/kernel/vspace.c`. Non-remap branch checks `pte_ptr_get_valid(lu_ret.ptSlot)` and returns `seL4_DeleteFirst`.
- API contract: https://docs.sel4.systems/projects/sel4/api-doc.html

Invariant under investigation (conditional on overwrite): frame-cap mapping metadata must correspond to actual page-table mapping.

Static reading is not proof. Experimental syscall return values and safe observations are the decision gate.
