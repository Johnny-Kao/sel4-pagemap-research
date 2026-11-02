#!/usr/bin/env python3
"""Bounded static evidence checks; only report audited source anchors."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
arch = sys.argv[2]
paths = {
    "aarch64": root / "src/arch/arm/64/kernel/vspace.c",
    "x86_64": root / "src/arch/x86/kernel/vspace.c",
    "riscv64": root / "src/arch/riscv/kernel/vspace.c",
}
p = paths[arch]
source = p.read_text()
checks = {
    "aarch64": ["performPageInvocationMap", "pte_get_page_base_address", "Page Flush: Attempting to use cap with stale mapping information.", "CONFIG_ARM_HYPERVISOR_SUPPORT", "invalidateTLBByASIDVA"],
    "x86_64": ["createSafeMappingEntries_PTE", "performX86PageInvocationMapPTE", "pte_ptr_get_page_base_address", "invalidatePageStructureCacheASID"],
    "riscv64": ["Virtual address (0x%", "pte_ptr_get_valid(lu_ret.ptSlot)", "seL4_DeleteFirst"],
}
print("arch=" + arch)
print("path=" + str(p))
for needle in checks[arch]:
    present = needle in source
    print("source_anchor=" + repr(needle) + " present=" + str(present))
    if not present:
        raise SystemExit("missing source anchor: " + needle)
print("STATIC_AUDIT: ANCHORS_PRESENT (not a security assessment)")
