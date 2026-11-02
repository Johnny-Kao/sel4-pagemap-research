# Security-outcome regression matrix (design gate, not a claim of exploitation)

## Target
The existing Page_Map collision test proves an API/invariant defect in a *single VSpace whose task owns all tested frame caps*. This plan separates that observation from unauthorized confidentiality, integrity, availability, and lifecycle effects. No upstream changes or PR.

## Required independent test cases
Each test must use a fresh disposable sel4test environment, record BEGIN, operation result, *immediate* pre-repair observation, and END/INCOMPLETE. Keep a separate baseline and negative control. Do not silently use a later remap to infer an earlier state.

| ID | Hypothesis | Controlled setup & validation | Positive security-impact signal | Disproof / limitation |
| --- | --- | --- | --- | --- |
| AUTH-1 | Mapping can be changed without the required VSpace authority | Two isolated test protection domains, distinct owned frames; deliberately omit mapping authority in the restricted domain, invoke only permitted APIs, and check owner-domain sentinel independently | Owner memory modified despite no authorized mapping path | Rejected invocation or unchanged sentinel; possessing both VSpace and frame cap proves nothing about isolation |
| AUTH-2 | Mapping permissions can be unintentionally upgraded | Restrict a test-owned mapping to read-only/non-executable, compare documented cap rights with actual read/write/execute fault handling under a controlled fault endpoint | An operation completes contrary to effective rights | Distinguish attributes, cap rights and architecture defaults; no injected machine-code payload |
| LIFE-1 | Revoke/Delete leaves reachable stale mapping | Map test-owned frames; use the test harness's legal revoke/delete path, verify expected cap invalidation and mapping presence **before** remapping | Reachable mapping remains when the relevant authority and frame lifetime are no longer valid | A derived cap revoke is not always destruction of underlying frame; check final-cap semantics first |
| LIFE-2 | Frame reuse exposes old data or aliases | Reclaim a test-owned frame through normal VKA path, allocate a new zeroed/sentinel frame, check old controlled VA via a fault-safe observer and new owner's sentinel | Same physical frame is legitimately reassigned yet prior VA remains accessible contrary to isolation | Physical reuse is not guaranteed; never infer reuse from address coincidence without allocator evidence |
| PREEMPT-1 | Interrupted revoke exposes inconsistent authorization state | Inspect cteRevoke preemption points and legal interruption semantics; if reachable, isolate an interruption checkpoint in a child test task and verify mapping ownership on resume | Unauthorized mapping survives completed revocation or is visible across a defined permission boundary | CI cancellation is **not** kernel preemption; no assertion without actually observing kernel state |
| CACHE-1 | Cache/TLB desynchronizes PTE and authority | Static verify all invalidation paths/ordering; only perform non-destructive same-domain consistency probes on tested configurations | Different authorized observers access inconsistent physical contents after completed synchronization | CPU cache ≠ cap metadata. ARM EL1 stale clean currently rejected with error 2; EL2 is distinct |
| RECOVERY-1 | Subsequent success masks earlier invalid state | Read mapping under controlled fault handler **immediately after** target operation, before map repair | Unexpected frame/permission observed at intermediate checkpoint | Old tests already show B unchanged after stale Unmap(A); avoid redundant loops |

## Execution gates
1. Static gate: find exact seL4 capability creation, derivation, revocation, finalise, and allocation semantics *in the pinned upstream revision*, and identify test harness APIs, without guessing signatures.
2. For AUTH tests, establish two genuinely distinct protection domains and verify cap tables; otherwise mark NOT_TESTED, never PASS.
3. For LIFE-2, verify actual frame reuse and ownership transfer, or mark INCONCLUSIVE.
4. Before any memory read that might be unmapped, use a fault endpoint/child task and explicit timeout/stop marker. Never dereference raw unknown VA in the whole test task.
5. Always include architecture/platform/kernel SHA, frame size, ASID/VSpace, input capabilities, syscall return, observed frame marker and stage index. Include negative controls.
6. Treat timeout, missing stage, skipped subcase, incomplete log, or nonzero simulator exit without suite completion as INCOMPLETE. Only source-proven and dynamically observed cases may be marked VERIFIED.
7. A high CVSS severity requires real confidentiality/integrity/availability impact with a plausible attacker capability precondition; a mismatch alone is not enough.
8. Do not execute exploit payloads, attempt actual unauthorized third-party memory access, or publish a cross-domain proof-of-concept in this public repo. Any suspected high-severity issue should be handled privately.

## Immediate status
AUTH-1, AUTH-2, LIFE-1, LIFE-2, PREEMPT-1: DESIGNED / NOT EXECUTED.
CACHE-1: ARM64 EL1 cache-clean negative control previously observed; rest NOT TESTED.
RECOVERY-1: same-VSpace stale-unmap intermediate check previously observed; no cross-domain conclusion.
