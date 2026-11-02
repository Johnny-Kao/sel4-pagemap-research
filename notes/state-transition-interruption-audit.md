# State-transition, observation and interruption audit

Source reviewed: tests/pagemap_collision.c; scripts/assert_results.py; .github/workflows/validate.yml.
Scope: single test task, same VSpace, two allocated small frames, no authority boundary crossing.

| Transition | Preconditions assumed | Immediate observation | What is not proved if interrupted here |
| --- | --- | --- | --- |
| Allocate A/B, reserve VA | Frames distinct, valid caps, allocated in test VSpace | handles/non-null checks | no PTE ownership check beyond allocator |
| Map A at VA | VA free, page table exists | syscall status, then marker write | logging a status alone cannot prove PTE durability |
| Map B temporarily, write marker, unmap B | B independently initialized and unmapped | address and subsequent value through occupied VA | B unmap successful state is not directly queried |
| Map B over occupied A | both caps and VSpace cap held | status plus actual read of B marker | A cap's map metadata inferred from later operations, not introspected |
| ARM stale A cache clean | A metadata says old VA, PTE points to B | return code 2, B read intact | no proof of EL2 behavior or cache-line operation effects |
| Map A into occupied VA again | stale A cap still owned | A marker read | map result cannot prove independent authority/isolation |
| Remap B at VA | B cap still owned | B marker read | transitional invalid states not measured |
| Unmap A | A stale cap, PTE points B | return code only | no immediate PTE read at this step; later Map B can mask a missing PTE |
| Remap A elsewhere | another reserved VA exists | return code and A marker | independent page-table hierarchy not directly checked |
| Remap B at old VA | B cap owned | return code and B marker | could restore state accidentally damaged by earlier Unmap |
| Unmap B, Map A back | own frames/caps | return codes and A marker | unmap and later successful map do not prove intermediate hole |

## Assumptions and invariants
A1. The two frames remain live and valid throughout the test; no revocation/deletion/finalisation is exercised.
A2. Tested caller already holds both Frame caps and VSpace cap; isolation between protection domains is not tested.
A3. No concurrency, re-entrant operation, page-table mutation from another thread, or asynchronous revocation.
A4. The VSpace library's own bookkeeping tracks its initial mapping; direct kernel mappings can diverge from that bookkeeping. This test avoids relying on it for post-collision reads.
A5. The CPU translation reflects the latest map calls in a single-threaded simulation. Barriers/TLB details require separate code review.
A6. Aarch64 test config is not EL2 solely because of arch name; distinguish kernel build flags.
A7. Test printed literal backslash-n in one physical log line; extractor must search record tokens rather than assume newline delimited.
A8. An observed success after recovery is not evidence that the original invariant held at every intermediate step.

## Interruption classification
- Interruption before initiating a syscall: operation may not have been invoked; terminal log absent.
- Interruption after syscall but before result print: kernel state may have changed; cannot infer success/failure from missing log.
- Interruption after result print but before memory read: syscall returned, actual translation still unknown.
- Interruption after observed memory read: that state was sampled; future states unknown.
- Cancellation/timeout of CI: results are partial and must be labelled INCOMPLETE, never PASS.
- Abrupt power loss/restart: user memory mappings are not durable across boot, so restart is not a persistence proof. Async interruptions or concurrent revocation are separate threats and not covered.

## Evidence limitations and next tests
1. Prefer a child-task or fault-handler controlled mapping observation between stale Unmap(A) and any corrective Map(B), avoiding an uncontrolled page fault in public CI. Compare mapping presence by an observation mechanism that does not itself restore the PTE.
2. Keep operation stage IDs and BEGIN/END markers for each transition so partial logs identify the last completed observation, not just the last printed return code.
3. Separate own-authority correctness tests from true protection-domain isolation tests; a high-severity claim requires unauthorized C/I/A consequences, not just stale cap metadata.
4. Conduct static review of frame cap finalisation/revocation and mapping checks before dynamic interruption experiments.
5. Do not publish high-impact exploit steps in this public research repository. No upstream interaction until explicit authorization.

## Outcome
The existing three-arch CI establishes repeatable own-authority map replacement and selected expected follow-ups; it does not establish correctness at every intermediate state or safety under interruption. Treat interruption and alternative-authority hypotheses as untested.
