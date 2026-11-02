# Results — seL4 Page_Map collision

## Decision
**Confirmed cross-architecture API correctness inconsistency. Security impact not established.**

CI: https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41412174036
Verified kernel SHA from prior build: `15ec7bf82864e0505dc682051c0d688a946f5ece`. For exact per-architecture provenance and config, refer to run artifacts.

| Architecture | Occupied VA Map B | Actual VA after Map B | Follow-up observations | Result |
| --- | --- | --- | --- | --- |
| RISC-V 64 | 8 = seL4_DeleteFirst | Not read (rejected) | no follow-up overwrite branch | Expected behavior |
| AArch64 | 0 = seL4_NoError | Frame B marker `0x6b4d2e8c` | Unmap A = 0; remap A elsewhere = 0 and reads original `0x5a3c1d7b`; remap B at same VA = 0, B marker unchanged; Unmap B = 0; remap A at original VA = 0, reads original marker | API mismatch confirmed, no harmful consequence demonstrated |
| x86_64 | 0 = seL4_NoError | Frame B marker `0x6b4d2e8c` | Same observations as AArch64 | API mismatch confirmed, no harmful consequence demonstrated |

CI test suites: x86_64 125 passed / 59 disabled; AArch64 125 passed / 59 disabled; RISC-V 115 passed / 53 disabled.

## Interpretation
AArch64 and x86_64 overwrite the occupied leaf entry rather than returning the documented `seL4_DeleteFirst` when a distinct unmapped frame is mapped to that VA. RISC-V rejects it.

Follow-up calls show that unmapping the prior frame A does not visibly disrupt B's contents, and that both frames can subsequently be mapped and unmapped through the exercised calls. This is **not** evidence of an exploitable authority or isolation failure. Frame-cap metadata was **not** directly introspected; stale or cleared metadata must not be asserted solely from syscall results.

## Limitations
- Tests exercise one VSpace, small pages, two distinct frames, and a single mapping sequence.
- No cross-VSpace isolation, permission bypass, or wrong-physical-page operation was demonstrated.
- Return code 0 from Page_Unmap alone is not proof of an actual page-table change.
- No post-unmap dereference or kernel-state corruption attempt was performed.
- Security severity/CVSS: **not assigned**. Confirmed correctness bug is not automatically a security vulnerability.

## Upstream
No upstream source modified, no fork, no issue/PR, and no maintainer contact.
