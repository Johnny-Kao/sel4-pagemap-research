#!/usr/bin/env python3
"""Compare possible minimal seL4 #1843 repairs against mapped/reserved contracts.

Research-only: never writes upstream. No emulated hardware is claimed.
"""
from itertools import product

def down(n,q): return n - (n % q)
def up(n,q): return ((n + q - 1)//q)*q

def old(b,s,q):
    a=down(b,q)
    return (a,a+up(s,q))

def local_interval_fix(b,s,q):
    # The smallest semantics-preserving change in Region.align_size:
    a=down(b,q)
    return a, a+(up(s+(b-a),q) if s else 0)

def reserve_only_fix(b,s,q,max_size):
    # Patch only KernelRegionGroup.reserved, leaving mapped computation unchanged.
    return local_interval_fix(b,s,q),old(b,min(s,max_size),q)

def both_via_region_fix(b,s,q,max_size):
    return local_interval_fix(b,s,q),local_interval_fix(b,min(s,max_size),q)

def covers(span,b,s):
    return span[0]<=b and span[1]>=b+s

def verify():
    total=0
    delta=0
    reservation_only_mapping_fail=0
    old_mapping_fail=0
    for bits in (2,3,4,12,21,22):
        q=1<<bits
        # Exhaustive for small quanta, structured boundaries for large quanta.
        bases = range(q*2) if bits<=4 else [0,q,q+1,q+3,2*q-1,2*q+1,3*q-1]
        sizes = range(q*2+1) if bits<=4 else [0,1,3,q//2,q-1,q,q+1,2*q,2*q+1]
        caps = [q,2*q]
        for b,s,cap in product(bases,sizes,caps):
            total+=1
            before_res=old(b,s,q)
            before_map=old(b,min(s,cap),q)
            new_res,new_map=both_via_region_fix(b,s,q,cap)
            sole_res,sole_map=reserve_only_fix(b,s,q,cap)
            assert sole_res == new_res
            assert sole_map == before_map
            assert new_res[0]%q==new_res[1]%q==0
            assert new_map[0]%q==new_map[1]%q==0
            if s:
                assert covers(new_res,b,s)
                assert covers(new_map,b,min(s,cap))
                if not covers(before_map,b,min(s,cap)):
                    old_mapping_fail+=1
                    assert not covers(sole_map,b,min(s,cap))
                    reservation_only_mapping_fail+=1
            else:
                assert new_res[0]==new_res[1]
                assert new_map[0]==new_map[1]
                assert new_res[0]==before_res[0]
            if before_res != new_res or before_map != new_map:
                delta+=1
                assert new_res[1]-before_res[1] in (0,q)
                assert new_map[1]-before_map[1] in (0,q)
            # If an input is page aligned, its result must be bit-for-bit identical.
            if b%q==0:
                assert before_res==new_res and before_map==new_map
    assert old_mapping_fail>0
    assert reservation_only_mapping_fail==old_mapping_fail
    assert local_interval_fix(0x1003,0x1000,0x1000)==(0x1000,0x3000)
    # Original helper is mathematically valid for nonnegative integers:
    for bits in range(1,10):
        q=1<<bits
        for n in range(0,2*q):
            assert ((n+q-1)&~(q-1))==up(n,q)
    print("MINIMAL_CONTRACT_PASS",total,"cases",delta,"changes")
    print("RESERVATION_ONLY_REMAINS_UNCOVERED_MAPPED_CASES",reservation_only_mapping_fail)
    print("CONCLUSION: align_up primitive does not need semantic change")
    print("CONCLUSION: local Region.align_size contract fix covers both callers")
    print("LIMIT: actual hardware-input validity, kernel boot, and cap exposure NOT tested")

if __name__=="__main__": verify()
