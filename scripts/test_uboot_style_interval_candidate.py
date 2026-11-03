#!/usr/bin/env python3
"""Research A/B: U-Boot-style [align_down(start), align_up(end)) in seL4.

Changes only the disposable upstream source checkout during GitHub Actions.
Compares formula with original and previously proposed end-based correction;
exercises real seL4 hardware_gen C/YAML/JSON on synthetic DTBs and existing
DTS+overlay platform C headers. No kernel boot or silicon validation.
"""
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
memory=root/"tools/hardware/memory.py"
original=memory.read_text()
old="""        new_base = hardware.utils.align_down(self.base, align_bits)
        new_size = hardware.utils.align_up(self.size, align_bits)
        return Region(new_base, new_size, self.owner)"""
uboot="""        # Calculate the original endpoint before page-aligning the region.
        new_end = hardware.utils.align_up(self.base + self.size, align_bits)
        new_base = hardware.utils.align_down(self.base, align_bits)
        new_size = new_end - new_base if self.size else 0
        return Region(new_base, new_size, self.owner)"""
prior="""        new_base = hardware.utils.align_down(self.base, align_bits)
        if self.size == 0:
            return Region(new_base, 0, self.owner)
        new_end = hardware.utils.align_up(self.base + self.size, align_bits)
        return Region(new_base, new_end - new_base, self.owner)"""
assert original.count(old)==1,"unexpected pinned source"
candidate=original.replace(old,uboot)

def down(x,q): return x//q*q
def up(x,q): return ((x+q-1)//q)*q

# Exhaustive small-page domain plus boundary-rich 4 KiB and 2 MiB cases.
checks=0
changes=0
for q in (4,8,16,4096,2**21):
    bases=range(2*q) if q<=16 else [0,1,3,q-1,q,q+1,q+3,2*q-1,2*q,2*q+7]
    lengths=range(2*q+1) if q<=16 else [0,1,3,32,q//2,q-1,q,q+1,2*q,2*q+1]
    for b in bases:
        for n in lengths:
            previous=(down(b,q),down(b,q)+up(n,q))
            current=(down(b,q),up(b+n,q) if n else down(b,q))
            prior_fix=(down(b,q),down(b,q)+(up(n+b-down(b,q),q) if n else 0))
            assert current==prior_fix,(q,b,n,current,prior_fix)
            assert current[0]%q==current[1]%q==0
            assert current[0]<=b
            if n: assert current[1]>=b+n
            if b%q==0: assert previous==current
            if current!=previous:
                assert current[1]-previous[1]==q
                changes+=1
            checks+=1
print("UBOOT_INTERVAL_EQUIVALENCE_PASS",checks,"inputs",changes,"cases changed")

def run(argv):
    r=subprocess.run(list(map(str,argv)),text=True,capture_output=True)
    if r.returncode: raise RuntimeError("FAILED "+ " ".join(map(str,argv))+"\n"+r.stderr[-1200:]+"\n"+r.stdout[-1000:])
    return r

def generate(dtb,arch,prefix,multi=False):
    header=out/(prefix+".h")
    cmd=[sys.executable,root/"tools/hardware_gen.py",
         "--dtb",dtb,"--hardware-config",root/"tools/hardware.yml",
         "--hardware-schema",root/"tools/hardware_schema.yml",
         "--sel4arch",arch,"--c-header","--header-out",header]
    if multi:
        cmd+=["--addrspace-max",str(1<<32),"--yaml","--yaml-out",out/(prefix+".yaml"),
              "--json","--json-out",out/(prefix+".json")]
    run(cmd)
    result={"header":header.read_text()}
    if multi:result["json"]=json.loads((out/(prefix+".json")).read_text())
    return result

def dt(base,size):
    return f"""/dts-v1/;
/ {{
 #address-cells = <2>; #size-cells = <2>;
 chosen {{ seL4,kernel-devices = "/test-device@{base:x}"; }};
 memory@80000000 {{ device_type = "memory"; reg = <0 0x80000000 0 0x02000000>; }};
 test-device@{base:x} {{
   compatible = "arm,pl310-cache";
   cache-unified;
   reg = <0 {base:#x} 0 {size:#x}>;
 }};
}};
"""

def c_reserve(txt):
    v=txt.split("kernel_device_reserved_regions[] = {",1)[1].split("};",1)[0]
    start=re.findall(r"\.start\s*=\s*0x([0-9a-fA-F]+)",v)
    end=re.findall(r"\.end\s*=\s*0x([0-9a-fA-F]+)",v)
    assert len(start)==len(end)==1
    return int(start[0],16),int(end[0],16)

results=[]
try:
    with tempfile.TemporaryDirectory() as d:
        tmp=Path(d)
        synthetic=[
            ("cross",0x1003,0x1000,True),
            ("near-boundary",0x1ff0,0x30,True),
            ("unaligned-in-page",0x1003,0x20,False),
            ("aligned",0x1000,0x1000,False)]
        for name,b,n,expected_changed in synthetic:
            source=tmp/(name+".dts"); binary=tmp/(name+".dtb")
            source.write_text(dt(b,n))
            run(["dtc","-q","-I","dts","-O","dtb","-o",binary,source])
            memory.write_text(original)
            baseline=generate(binary,"aarch64",name+"-old",True)
            memory.write_text(candidate)
            corrected=generate(binary,"aarch64",name+"-uboot",True)
            r0=c_reserve(baseline["header"]);r1=c_reserve(corrected["header"])
            assert r1==(down(b,4096),up(b+n,4096))
            assert (r0!=r1)==expected_changed
            assert (baseline["header"]!=corrected["header"])==expected_changed
            assert (baseline["json"]!=corrected["json"])==expected_changed
            diff=list(difflib.unified_diff(baseline["header"].splitlines(),corrected["header"].splitlines(),
                                           fromfile="old",tofile="uboot",lineterm=""))
            (out/(name+".diff")).write_text("\n".join(diff)+"\n")
            results.append(dict(kind="synthetic",name=name,status="ok",changed=expected_changed,
                                baseline_reserved=[hex(i) for i in r0],
                                corrected_reserved=[hex(i) for i in r1],
                                header_changed=bool(diff),json_changed=baseline["json"]!=corrected["json"]))
            print("UBOOT_SYNTHETIC",name,"RESERVE",r0,r1,"HDR_JSON_CHANGED",bool(diff))
        # Retest all existing real-platform fixtures rather than assuming equivalence.
        boards=[
            ("spike","riscv64"),("ariane","riscv64"),("hifive","riscv64"),
            ("star64","riscv64"),("bananapi-f3","riscv64"),("cheshire","riscv64"),
            ("fvp","aarch64"),("rpi4","aarch64"),("odroidc2","aarch64"),
            ("tx1","aarch64"),("tx2","aarch64"),("exynos5422","aarch32"),
            ("rock3b","aarch64"),("imx8mq-evk","aarch64"),("imx8mp-evk","aarch64"),
            ("imx7sabre","aarch32"),("am335x-boneblack","aarch32"),
            ("allwinnerA20","aarch32"),("omap3","aarch32"),("sabre","aarch32")]
        good=0
        for name,arch in boards:
            source=root/"tools/dts"/(name+".dts")
            overlays=sorted(root.glob("src/plat/**/overlay-"+name+".dts"))
            if not source.exists() or not overlays:
                results.append(dict(kind="platform",name=name,status="missing-pair"));continue
            combined=tmp/(name+"-combined.dts");binary=tmp/(name+".dtb")
            parts=[source.read_text(),overlays[0].read_text()]
            if name=="rpi4":parts.append((root/"src/plat/bcm2711/overlay-rpi4-8gb.dts").read_text())
            combined.write_text("\n".join(parts))
            run(["dtc","-q","-I","dts","-O","dtb","-o",binary,combined])
            memory.write_text(original)
            before=generate(binary,arch,name+"-old")["header"]
            memory.write_text(candidate)
            after=generate(binary,arch,name+"-uboot")["header"]
            assert before==after,(name,"candidate changes existing platform output")
            good+=1
            results.append(dict(kind="platform",name=name,status="ok",changed=False,
                                sha256=hashlib.sha256(before.encode()).hexdigest()))
            print("UBOOT_PLATFORM_NO_DIFF",name,arch)
        assert good==20,(good,"not all requested platforms generated")
finally:
    memory.write_text(original)
(out/"uboot-style-summary.json").write_text(json.dumps(results,indent=2)+"\n")
print("UBOOT_STYLE_INTEGRATION_PASS",len([x for x in results if x["kind"]=="synthetic"]),
      "synthetic,",good,"actual platform headers unchanged; real kernel boot NOT tested")
