# seL4 #1843 — how frequently does the tail-undercoverage condition arise?

Date: 2026-11-03. Research only. Based on 20 selected platform DTS + overlay combinations, pinned seL4 revision 15ec7bf82864e0505dc682051c0d688a946f5ece.

## Exact code and trigger

`Region.align_size(bits)` does:

```python
new_base = align_down(self.base, bits)
new_size = align_up(self.size, bits)
return Region(new_base, new_size, self.owner)
```

Let `Q=2**bits`, `o=base%Q`, `r=size%Q`, and `size>0`. The original computed end is below `base+size` **iff** `o>0 and (r==0 or o+r>Q)`. When this condition holds, a corrected covering interval requires one more mapped/reserved **whole page** than the original interval. The actual uncovered original data tail is not necessarily a whole page; it is `(base+size) - old_end` bytes, in `[1,Q-1]`.

Examples at 4KiB:
- `base=0x1000,size=0x1000`: no miss.
- `base=0x1003,size=0x20`: no miss.
- `base=0x1003,size=0x1000`: 3 bytes uncovered; fixing requires an extra 4KiB mapping/reservation page.
- `base=0x1ff0,size=0x30`: 0x20 bytes uncovered; fixing requires one extra page.

## Evidence: actually selected kernel-device inputs

Source: successful research run https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41629627065, job logs and selected-kernel-device-region-inventory JSON artifact.

20 platforms; 62 selected regions; **58 page-aligned bases**, **4 unaligned bases**; 43 region sizes are exact page multiples (these are not necessarily nonaligned bases). All four unaligned-base entries remain within the first aligned page. **Zero reservation undercoverage; zero mapped-prefix undercoverage.**

| Platform | Kernel-chosen region | Final translated start | DT size | Offset within page | Spare bytes in this mapped page after source end | User-sharing |
| --- | --- | --- | --- | --- | --- | --- |
| rpi4 | UART | 0xfe215040 | 0x40 | 0x40 | 0xf80 | true |
| odroidc2 | UART | 0xc81004c0 | 0x18 | 0x4c0 | 0xb28 | true |
| sabre | interrupt controller subregion | 0xa00100 | 0x100 | 0x100 | 0xe00 | false |
| sabre | timer | 0xa00600 | 0x20 | 0x600 | 0x9e0 | false |

The trailing bytes in these examples are **not evidence of a contractual spare area**. They are merely the unused remainder of an MMU page, and some pages are shared among distinct register blocks. They may contain other device registers and are not general-purpose memory for future use.

## Why the bug stayed latent

The observed configurations often choose aligned interrupt controller / cache bases, or small unaligned UART, timer, and register subregions that fit within one page. This makes `align_down(base)+align_up(size)` *accidentally sufficient* for the observed inputs. The formula does not enforce those properties. In particular, even a small resource can cross a page boundary if its offset is near the end of the page; a nonaligned resource of exactly page-length always triggers.

The sample is **not** an estimate of probability across possible hardware or random input; the practical incidence depends on actual DT hardware bindings, chosen node lists, and bus address translation.

## Engineering decision

Do not introduce a blanket page-alignment requirement; it would reject known deployed configurations. Do not redefine this unused page tail as a deliberate safety cushion. At the same time, a full-region alignment fix is not yet certified safe on all memory-mapping ownership constraints. Best immediate upstream deliverable is a precise, issue-first report of the contract invariant with an explicit no-current-target-impact caveat. Any PR should remain research-only until supporting input and downstream mapping side effects are evaluated.

No seL4 upstream modifications, confirmed reboot failure, or observed memory isolation breach.
