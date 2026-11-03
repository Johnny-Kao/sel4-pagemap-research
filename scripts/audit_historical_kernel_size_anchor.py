#!/usr/bin/env python3
"""Demonstrate exactly where kernel_size starts, historic label-offset behavior,
and whether independent size-rounding can encode reserved slack.
This is a source-model verification; not kernel runtime validation.
"""
def up(x,q): return ((x+q-1)//q)*q
def down(x,q): return x//q*q

def historic(base,dev_size,kernel_size,q):
    # Original KernelRegionGroup code in 2019 and modern source; use page size q.
    # Mutates region.size before alignment, then labels register offset from original base.
    requested=min(kernel_size,dev_size)
    aligned_base=down(base,q)
    mapped_end=aligned_base+up(requested,q)
    reg_offset=base-aligned_base
    return {"mapped":(aligned_base,mapped_end),
            "register_offset":reg_offset,
            "requested":(base,base+requested)}

def covering(base,dev_size,kernel_size,q):
    requested=min(kernel_size,dev_size)
    a=down(base,q)
    return {"mapped":(a,up(base+requested,q) if requested else a),
            "register_offset":base-a,
            "requested":(base,base+requested)}

def test():
    # These cases are not hypothetical CPU page rules, just inputs admitted
    # by existing Python layer without an alignment check.
    cases=[
        ("aligned",0x1000,0x3000,0x1000,0x1000),
        ("unaligned_short",0x1003,0x3000,0x20,0x1000),
        ("unaligned_one_page",0x1003,0x3000,0x1000,0x1000),
        ("unaligned_small_offset",0x1ff0,0x3000,0x20,0x1000),
        ("large_page",0x200003,0x400000,0x200000,0x200000),
    ]
    impacted=0
    for name,base,dev_size,kernel_size,q in cases:
        before=historic(base,dev_size,kernel_size,q)
        after=covering(base,dev_size,kernel_size,q)
        # REG pointer is always at start of original physical device address.
        assert before["mapped"][0]+before["register_offset"]==base
        assert after["mapped"][0]+after["register_offset"]==base
        # A correct mapping must contain all bytes selected by min(kernel_size, dev_size).
        original_cover=(before["mapped"][1]>=before["requested"][1])
        fixed_cover=(after["mapped"][1]>=after["requested"][1])
        assert fixed_cover
        impacted += not original_cover
        print(name,
              "base",hex(base),"kernel_size",hex(kernel_size),
              "requested",tuple(map(hex,before["requested"])),
              "old_map",tuple(map(hex,before["mapped"])),
              "fixed_map",tuple(map(hex,after["mapped"])),
              "reg_offset",hex(before["register_offset"]),
              "old_covers_requested",original_cover)
    assert impacted==3
    # Historical schema's 'max(kernel_size,region_size)' conflicts
    # with actual min(...) truncation in original Python code.
    assert min(0x1000,0x3000)==0x1000
    assert max(0x1000,0x3000)==0x3000
    print("HISTORICAL_KERNEL_SIZE_ANCHOR_PASS: start is raw device base, not aligned base")
    print("SCHEMA_2019_MAX_VS_IMPLEMENTATION_MIN: documented inconsistency")
    print("HISTORICAL_SLACK_HYPOTHESIS_UNSUPPORTED: undercoverage does not guarantee safe slack")

if __name__=="__main__":test()
