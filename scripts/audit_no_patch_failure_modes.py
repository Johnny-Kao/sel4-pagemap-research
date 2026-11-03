#!/usr/bin/env python3
"""No-patch seL4 #1843 impact gates.

This is a conservative model of the arithmetic and src/kernel/boot.c
create_untypeds gap-selection logic, not an emulated kernel boot.
"""
def align_down(n,q): return n//q*q
def align_up(n,q): return ((n+q-1)//q)*q

def effects(base,size,kernel_size,page,reserved_other=(),user=False,user_top=(1<<32),accesses=()):
    assert base >= 0 and size > 0 and kernel_size > 0 and page > 0
    o=align_down(base,page)
    mapped_length=min(size,kernel_size)
    old_mapped_end=o+align_up(mapped_length,page)
    old_reserved_end=o+align_up(size,page)
    correct_mapped_end=align_up(base+mapped_length,page)
    correct_reserved_end=align_up(base+size,page)
    missing_map=(old_mapped_end,correct_mapped_end) if old_mapped_end<correct_mapped_end else None
    missing_reserved=(old_reserved_end,correct_reserved_end) if old_reserved_end<correct_reserved_end else None
    # Conservative possibility: a missing PAGE can be entirely available as device UT
    # if under the physical device cap top, no other reservation, and not 'user:true'
    def overlap(a,b):return a[0]<b[1] and b[0]<a[1]
    possible_cap=(missing_reserved is not None and not user
                  and missing_reserved[1]<=user_top
                  and all(not overlap(missing_reserved, x) for x in reserved_other))
    access_failure_candidates=[hex(a) for a in accesses
                               if base<=a<base+mapped_length
                               and a >= old_mapped_end]
    return dict(device=[hex(base),hex(base+size)],mapped=[hex(o),hex(old_mapped_end)],
                required_mapped_end=hex(correct_mapped_end),
                reserved=[hex(o),hex(old_reserved_end)],
                required_reserved_end=hex(correct_reserved_end),
                unmapped_requested_bytes=(max(0,base+mapped_length-old_mapped_end)),
                unreserved_device_bytes=(max(0,base+size-old_reserved_end)) if not user else 0,
                missed_mapping_page=bool(missing_map),
                missed_reservation_page=bool(missing_reserved) and not user,
                candidate_accesses=access_failure_candidates,
                possible_root_device_untyped=possible_cap)

def test():
    Q=0x1000
    rows=[
      ("ordinary_aligned",dict(base=0x1000,size=0x1000,kernel_size=0x1000,page=Q,accesses=[0x1fff])),
      ("unaligned_small",dict(base=0x1003,size=0x20,kernel_size=0x1000,page=Q,accesses=[0x1022])),
      ("both_missing",dict(base=0x1003,size=0x1000,kernel_size=0x1000,page=Q,accesses=[0x2000])),
      ("reserve_only_missing",dict(base=0x1003,size=0x2000,kernel_size=0x20,page=Q,accesses=[0x2000])),
      ("mapping_missing_but_reserved",dict(base=0x1ff0,size=0x30,kernel_size=0x30,page=Q,
          reserved_other=[(0x2000,0x3000)],accesses=[0x2001])),
      ("user_shared_device",dict(base=0x1003,size=0x1000,kernel_size=0x1000,page=Q,user=True)),
      ("outside_device_cap_top",dict(base=0x1003,size=0x1000,kernel_size=0x1000,page=Q,user_top=0x2000)),
      ("riscv64_two_mib_page",dict(base=0x200003,size=0x200000,kernel_size=0x200000,page=0x200000,
          accesses=[0x400000]))
    ]
    for name, args in rows:
        z=effects(**args)
        print("IMPACT_GATE",name,z)
        if name=="both_missing":
            assert z["unmapped_requested_bytes"]==3 and z["unreserved_device_bytes"]==3
            assert z["candidate_accesses"]==["0x2000"]
            assert z["possible_root_device_untyped"]
        if name=="reserve_only_missing":
            assert z["unmapped_requested_bytes"]==0
            assert z["unreserved_device_bytes"]==3
            assert z["possible_root_device_untyped"]
        if name=="mapping_missing_but_reserved":
            assert z["unmapped_requested_bytes"]>0 and not z["possible_root_device_untyped"]
        if name=="user_shared_device":
            assert not z["possible_root_device_untyped"]
        if name=="outside_device_cap_top":
            assert not z["possible_root_device_untyped"]
    print("NO_PATCH_SEVERITY_GATES_PASS",len(rows),"CAUTION simulation of possible cap coverage, not actual capability issuance or runtime crash")

if __name__=="__main__":test()
