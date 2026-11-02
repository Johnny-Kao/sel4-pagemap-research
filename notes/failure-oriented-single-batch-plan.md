# Failure-oriented batched investigation gate

## Goal
Find *unexpected outcomes* from confirmed Page_Map overwrite / stale mapping metadata, not accumulate successful normal behavior. Target x86_64 + AArch64 only. Upstream untouched. This document is planning, NOT executed tests.

## Batch design — distinct hypotheses
| ID | State transition | Security invariant at risk | Result needed for claim | Control |
|---|---|---|---|---|
| F1 | overwrite A→B, then reverse mapping under changed rights | effective read/write restrictions | privilege-inconsistent access, not merely syscall success | baseline read-only mapped frame with fault handling |
| F2 | overwrite A→B while CSpace derivations differ | authority/lifecycle ownership | operation on a cap no longer authorized affects unrelated frame | known-authorized and invalid-cap negative controls |
| F3 | overwrite; tear down and rebuild VSpace / ASID | stale cap generation ambiguity | stale cap acts on a *new* address space despite no corresponding current authority | distinct old/new roots, explicit ASID ownership |
| F4 | overwrite; final cap delete; allocator recycle | stale PTE after physical reuse | old mapping retains access after proven same physical page recycled | actual allocator provenance required; new allocation != verified reuse |
| F5 | overwrite during revoke/finalise interleavings | consistency at completed syscall boundary | unauthorized observable result after completed transitions | log preemption vs incomplete invocation separately |
| F6 | map overwrite, then VM fault/permission path | unexpected page fault, lost mapping, integrity error | deterministic fault or corruption outside authorized mapping change | supervised child/test process, no unsafe raw access |

## CI construction requirements
- Build all viable distinct subtests before the **single** 2-architecture workflow_dispatch. No incremental runs for isolated edits.
- Each subtest fresh independent vspace/cspace where needed; fault-prone tests in child execution context to prevent whole suite blockage.
- At each transition record expected authority, operation result, *immediate* observation, and completion/fault marker. Evidence of failure must be a genuine invariant violation, not expected rejection.
- Explicitly mark NOT_EXECUTED if an isolated subtest cannot be implemented. Do not equate original seL4test suite PASS with security-boundary coverage.
- RISC-V bypassed (occupied mapping rejected before anomaly). Keep normal checks as controls only, not the majority of the matrix.
- Prioritize source analysis of Arch_finaliseCap, VSpace/ASID lifecycle and allocator ownership before deciding dynamic test feasibility.
- Avoid publishing detailed exploit mechanics or third-party memory contents in a public research repo; use benign sentinel-only outputs.
- Preserve links to runs, build provenance and evidence-to-claim mapping; CVE severity unassigned until unauthorized impact is proven.
