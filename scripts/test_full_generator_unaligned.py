#!/usr/bin/env python3
"""End-to-end seL4 hardware_gen regression: unaligned device MMIO region.

Uses upstream device tree compiler, YAML hardware rules, FdtParser, KernelRegionGroup
and the actual generated C header. No emulated kernel or invented helper semantics.
"""
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

upstream=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
memory=upstream/"tools/hardware/memory.py"
original=memory.read_text()
needle="""        new_base = hardware.utils.align_down(self.base, align_bits)
        new_size = hardware.utils.align_up(self.size, align_bits)
        return Region(new_base, new_size, self.owner)"""
replacement="""        new_base = hardware.utils.align_down(self.base, align_bits)
        if self.size == 0:
            return Region(new_base, 0, self.owner)
        new_end = hardware.utils.align_up(self.base + self.size, align_bits)
        return Region(new_base, new_end - new_base, self.owner)"""
assert original.count(needle)==1,"Pinned upstream align_size not found uniquely"
candidate=original.replace(needle,replacement)

# Use standard 'arm,pl310-cache' hardware.yml rule, with no platform-specific
# virtual-address or fabricated kernel configuration. Address and size are DT
# cells; 'compatible' is an existing officially configured kernel-device type.
def dts(base,size):
    return f"""/dts-v1/;
/ {{
  #address-cells = <2>;
  #size-cells = <2>;
  chosen {{
    seL4,kernel-devices = "/test-device@{base:x}";
  }};
  memory@80000000 {{
    device_type = "memory";
    reg = <0x0 0x80000000 0x0 0x02000000>;
  }};
  test-device@{base:x} {{
    compatible = "arm,pl310-cache";
    cache-unified;
    reg = <0x0 {base:#x} 0x0 {size:#x}>;
  }};
}};
"""

def cmd(argv):
    p=subprocess.run(argv,capture_output=True,text=True)
    if p.returncode: raise RuntimeError(" ".join(map(str,argv))+"\n"+p.stdout[-1200:]+"\n"+p.stderr[-2000:])
    return p

def generate(dtb,outfile):
    cmd([sys.executable,str(upstream/"tools/hardware_gen.py"),
       "--dtb",str(dtb),
       "--hardware-config",str(upstream/"tools/hardware.yml"),
       "--hardware-schema",str(upstream/"tools/hardware_schema.yml"),
       "--sel4arch","aarch64","--c-header","--header-out",str(outfile)])
    return outfile.read_text()

def reserved_section(text):
    block=text.split("kernel_device_reserved_regions[] = {",1)[1].split("};",1)[0]
    starts=re.findall(r"\.start\s*=\s*0x([0-9a-fA-F]+)",block)
    ends=re.findall(r"\.end\s*=\s*0x([0-9a-fA-F]+)",block)
    assert len(starts)==1 and len(ends)==1,(starts,ends)
    return int(starts[0],16),int(ends[0],16)

results=[]
# Distinguish a regression-positive input from a page-aligned negative control.
cases=[("unaligned-cross-page",0x1003,0x1000,True),
       ("aligned-control",0x1000,0x1000,False),
       ("unaligned-within-page",0x1003,0x20,False),
       ("unaligned-cross-two-page",0x1ff0,0x30,True)]
try:
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        for name,base,size,expect_change in cases:
            source=td/(name+".dts"); dtb=td/(name+".dtb")
            source.write_text(dts(base,size))
            cmd(["dtc","-q","-I","dts","-O","dtb","-o",str(dtb),str(source)])
            memory.write_text(original)
            before=generate(dtb,out/(name+"-baseline.h"))
            memory.write_text(candidate)
            after=generate(dtb,out/(name+"-candidate.h"))
            b=reserved_section(before)
            a=reserved_section(after)
            expected=(base//4096*4096,((base+size+4095)//4096)*4096)
            assert a==expected,(name,"candidate incorrect",a,expected)
            assert (a!=b)==expect_change,(name,"change expectation mismatch",b,a)
            assert b[0] <= base,(name,"baseline start")
            assert b[1] < base+size if expect_change else b[1] >= base+size,(name,"baseline coverage",b)
            # Mapped device frames must at least cover the configured subrange;
            # any larger reserved range should not shorten the mapped part.
            diff="\n".join(difflib.unified_diff(before.splitlines(),after.splitlines(),
                                                 fromfile="baseline",tofile="candidate",lineterm=""))
            (out/(name+".diff")).write_text(diff+"\n")
            results.append(dict(case=name,device=[hex(base),hex(base+size)],
                                baseline=[hex(x) for x in b],
                                candidate=[hex(x) for x in a],
                                changed=bool(diff),diff=diff[:2200]))
finally:
    memory.write_text(original)
(out/"integration-summary.json").write_text(json.dumps(results,indent=2)+"\n")
for x in results:
    print("FULL_GENERATOR",x["case"],"device",x["device"],
          "baseline",x["baseline"],"candidate",x["candidate"],"CHANGED",x["changed"])
print("FULL_GENERATOR_PASS",len(results))
