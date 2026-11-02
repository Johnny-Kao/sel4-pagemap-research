# seL4 Page_Map collision research

Private, standalone correctness research. **No fork, upstream changes, issue, PR, or maintainer contact.**

## Question
Does a new frame mapping replace an occupied virtual address rather than return `seL4_DeleteFirst` on AArch64 and x86_64, unlike RISC-V?

The seL4 public API documents `seL4_DeleteFirst` for an already occupied address. Static inspection of kernel master suggests an unchecked overwrite on AArch64 and x86 small pages. This is **not** yet an experimentally verified bug or security vulnerability.

## Procedure
CI fetches the official seL4test manifest and upstream source. A minimal sel4test extension is appended only inside the disposable CI workspace, never submitted to upstream. Each architecture builds and, if QEMU supports it, runs the test. SHA/config/logs are uploaded as CI artifacts.

The collision test does not deliberately touch an unmapped address after unmap, and does not seek privilege escalation. Follow-up mapping-metadata investigation is gated on actual overwrite observations.

See [RESULTS.md](RESULTS.md) and [notes/source-analysis.md](notes/source-analysis.md).
