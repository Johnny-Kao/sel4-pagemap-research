#!/usr/bin/env python3
"""A/B test seL4's actual C-header, YAML and JSON output contracts.

No kernel boot or real-device access is claimed. Requires upstream checkout,
dtc, pyfdt, yaml, jinja2, jsonschema. Research-only modifications are restored.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import yaml

upstream=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
memory=upstream/"tools/hardware/memory.py"
source=memory.read_text()
old="""        new_base = hardware.utils.align_down(self.base, align_bits)
        new_size = hardware.utils.align_up(self.size, align_bits)
        return Region(new_base, new_size, self.owner)"""
new="""        new_base = hardware.utils.align_down(self.base, align_bits)
        if self.size == 0:
            return Region(new_base, 0, self.owner)
        new_end = hardware.utils.align_up(self.base + self.size, align_bits)
        return Region(new_base, new_end - new_base, self.owner)"""
assert source.count(old)==1

def run(argv):
    p=subprocess.run(argv,text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError("command failure: "+" ".join(map(str,argv))+"\n"+p.stdout[-1300:]+"\n"+p.stderr[-1300:])
    return p

def c_ranges(txt, name, key):
    part=txt.split(name+"[] = {",1)[1].split("};",1)[0]
    return [int(x,16) for x in re.findall(r"\."+key+r"\s*=\s*0x([0-9a-fA-F]+)",part)]

def gen(dtb, prefix):
    hdr=out/(prefix+".h")
    yml=out/(prefix+".yaml")
    js=out/(prefix+".json")
    run([sys.executable,str(upstream/"tools/hardware_gen.py"),
         "--dtb",str(dtb),"--hardware-config",str(upstream/"tools/hardware.yml"),
         "--hardware-schema",str(upstream/"tools/hardware_schema.yml"),
         "--sel4arch","aarch64","--addrspace-max",str(1<<32),
         "--c-header","--header-out",str(hdr),
         "--yaml","--yaml-out",str(yml),
         "--json","--json-out",str(js)])
    h=hdr.read_text()
    y=yaml.safe_load(yml.read_text())
    j=json.loads(js.read_text())
    assert y["devices"]==j["devices"]
    assert y["memory"]==j["memory"]
    return {
        "mapped_page_starts":c_ranges(h,"kernel_device_frames","paddr"),
        "reserve_starts":c_ranges(h,"kernel_device_reserved_regions","start"),
        "reserve_ends":c_ranges(h,"kernel_device_reserved_regions","end"),
        "excluded_device_ranges":j["devices"],
    }

def dt_source(base, size):
    return f"""/dts-v1/;
/ {{
 #address-cells = <2>;
 #size-cells = <2>;
 chosen {{ seL4,kernel-devices = "/test-device@{base:x}"; }};
 memory@80000000 {{ device_type = "memory"; reg = <0 0x80000000 0 0x02000000>; }};
 test-device@{base:x} {{
   compatible = "arm,pl310-cache";
   cache-unified;
   reg = <0 {base:#x} 0 {size:#x}>;
 }};
}};
"""

result=[]
try:
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        for name,base,size in [
            ("unaligned_cross",0x1003,0x1000),
            ("aligned",0x1000,0x1000),
            ("unaligned_short",0x1003,0x20),
            ("two_page_cross",0x1ff0,0x30),
        ]:
            dts=td/(name+".dts")
            dtb=td/(name+".dtb")
            dts.write_text(dt_source(base,size))
            run(["dtc","-q","-I","dts","-O","dtb","-o",str(dtb),str(dts)])
            memory.write_text(source)
            before=gen(dtb,name+"-before")
            memory.write_text(source.replace(old,new))
            after=gen(dtb,name+"-after")
            expected_end=((base+size+4095)//4096)*4096
            assert after["reserve_ends"]==[expected_end]
            expected_change=name in {"unaligned_cross","two_page_cross"}
            assert (before["reserve_ends"]!=after["reserve_ends"])==expected_change
            # Reserve and mapped regions are two independent output contracts.
            assert (before["mapped_page_starts"]!=after["mapped_page_starts"])==expected_change
            assert (before["excluded_device_ranges"]!=after["excluded_device_ranges"])==expected_change
            result.append({"case":name,"before":before,"after":after})
            print("MULTI_OUTPUT",name,"MAPPED",before["mapped_page_starts"],after["mapped_page_starts"],
                  "RESERVED_END",before["reserve_ends"],after["reserve_ends"],
                  "DEVICE_EXCLUSION_CHANGED",before["excluded_device_ranges"]!=after["excluded_device_ranges"])
finally:
    memory.write_text(source)
(out/"multi-output-results.json").write_text(json.dumps(result,indent=2))
print("MULTI_OUTPUT_CONTRACT_PASS",len(result))
