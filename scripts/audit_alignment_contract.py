#!/usr/bin/env python3
"""seL4 #1843: dependency-free, exhaustive interval-contract differential audit.

This is a research test, not a proposed upstream implementation.
Run: python3 scripts/audit_alignment_contract.py
"""
from itertools import product

def up(x, bits):
    q = 1 << bits
    return (x + q - 1) & ~(q - 1)

def down(x, bits):
    q = 1 << bits
    return x & ~(q - 1)

def baseline(base, size, bits):
    b = down(base, bits)
    return b, b + up(size, bits)

def covering(base, size, bits):
    b = down(base, bits)
    return b, up(base + size, bits)

def trigger(base, size, bits):
    q = 1 << bits
    o, r = base % q, size % q
    return size > 0 and o > 0 and (r == 0 or o + r > q)

def audit():
    samples = changes = 0
    for bits in range(1, 8):
        q = 1 << bits
        for base, size in product(range(q * 3), range(q * 3 + 1)):
            samples += 1
            old = baseline(base, size, bits)
            new = covering(base, size, bits)
            if size:
                expected = trigger(base, size, bits)
                assert (old[1] < base + size) == expected, (base, size, bits, old)
                assert (new != old) == expected, (base, size, bits, old, new)
                assert new[0] <= base and new[1] >= base + size
                if expected:
                    changes += 1
                    assert new[1] - old[1] == q
            assert up(0, bits) == 0
            assert up(base, bits) % q == 0
            assert down(base, bits) % q == 0
    # Two independent APIs. syscall_stub_gen uses an alignment amount rather than bit count.
    def syscall_up(x, a):
        if x % a == 0:
            return x
        return x + a - (x % a)
    for bits in range(1, 12):
        for x in range(0, 128):
            assert up(x, bits) == syscall_up(x, 1 << bits)
    print("EXHAUSTIVE_NONNEGATIVE_CONTRACT_PASS", samples, "positive_differentials", changes)
    # Candidate fix changes MAPPING as well as RESERVATION in KernelRegionGroup
    # (both call Region.align_size). Thus generated-headers equality alone is insufficient.
    for name, base, size, bits, max_size in [
        ("aligned", 0x1000, 0x1000, 12, 0x1000),
        ("unaligned_cross", 0x1003, 0x1000, 12, 0x1000),
        ("unaligned_short", 0x1003, 0x20, 12, 0x1000),
        ("zero", 0x1003, 0, 12, 0x1000),
        ("riscv64_quantum", 0x200003, 0x200000, 21, 0x200000),
    ]:
        old_reserved = baseline(base, size, bits)
        new_reserved = (down(base,bits),down(base,bits)) if size == 0 else covering(base,size,bits)
        mapped_size = min(max_size, size)
        old_mapped = baseline(base, mapped_size, bits)
        new_mapped = (down(base,bits),down(base,bits)) if mapped_size == 0 else covering(base,mapped_size,bits)
        print("CONTRACT_DIFFERENTIAL",name,"original",(hex(base),hex(base+size)),
              "reserved_old",tuple(map(hex,old_reserved)),
              "reserved_candidate",tuple(map(hex,new_reserved)),
              "mapped_old",tuple(map(hex,old_mapped)),
              "mapped_candidate",tuple(map(hex,new_mapped)),
              "mapped_page_delta",(new_mapped[1]-old_mapped[1])//(1<<bits))
        assert new_reserved[1]>=base+size if size else new_reserved[0]==new_reserved[1]
    print("NO_CLAIM_ON_RUNTIME_OR_EXISTING_PLATFORM_REACHABILITY")

if __name__ == "__main__":
    audit()
