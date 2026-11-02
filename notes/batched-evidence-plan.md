# Batched evidence plan (no upstream PR)

## Scope and cost control
All dynamic tests run on Ubuntu GitHub-hosted runners, not macOS. AArch64 and RISC-V run under emulation. First exhaust source review. A new CI run is justified only when a genuinely new observable property remains uncertain. Do not create one CI run per hypothesis. Existing workflow tests all three architectures and currently rebuilds from scratch; cache upstream dependencies/build products where safe after fixing provenance.

## Already observed (runs 41408157221, 41412174036, 41417918469)
- RISC-V rejects occupied VA Page_Map with DeleteFirst (8).
- AArch64 and x86_64 allow a second frame to replace the PTE; VA reads replacement frame content.
- Stale first-frame cap may map the original frame again into same VA.
- AArch64/x86 unmap checks matching physical frame, preventing a stale unmap from removing the replacement in the examined sequence.

## Static review gates before new simulation
1. **Frame-cap mapping data:** trace every consumer of mapped ASID/address across map/unmap, destruction, revoke, finalise and flush paths. Record whether physical-frame identity is checked.
2. **Mapping synchronization:** compare TLBI/page-structure cache invalidation and barriers, distinguishing stale cap metadata from CPU caches.
3. **ARM cache path:** EL1 cross-checks PTE physical identity; EL2 operates on cap physical address. Distinguish different but valid authority models from wrong-frame operations.
4. **Authorization model:** identify required caps for Page_Map; a caller possessing both frame and VSpace authority replacing its own mapping is not by itself evidence of unauthorized access.
5. **Arch/size matrix:** differentiate x86 small vs large page, ARM frame sizes, RISC-V. Avoid equating one leaf-size result with all mappings.

## Single next dynamic batch — only if static analysis leaves uncertainty
- Same-VA collision return code and marker (existing baseline).
- Same-frame attribute update vs different-frame replacement and actual observed permission behavior (non-destructive, own frames).
- Stale first-frame cap unmap then remap, checking markers with guarded access (existing baseline).
- ARM stale-cap cache clean result and unchanged replacement-frame marker (non-destructive; EL1/EL2 build config explicitly recorded).
- Dedicated diagnostics distinguishing a rejected operation from a successfully executed operation; include errors, architecture, platform, config, SHA and machine-readable verdict.
- Explicit assertion failures for deviations; do not mark an architecture PASS only because a 'PAGEMAP_RESULT' string appears.
- No fuzzing, no third-party frames, no privilege escalation, no public high-impact proof-of-concept.

## Decision
- Correctness: occupied VA replacement confirmed.
- Security severity: unset until an actual unauthorized confidentiality/integrity/availability effect is demonstrated.
- If an isolation concern emerges, stop public CI expansion and use responsible private handling.
