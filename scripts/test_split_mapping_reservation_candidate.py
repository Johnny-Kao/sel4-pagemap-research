#!/usr/bin/env python3
"""Research-only seL4 split contract experiment.

2019 kernel MMIO mappings remain byte-for-byte legacy when they cover the
configured mapped prefix. 2026 full-device reservations cover the original
device interval. An undercovered legacy kernel mapping is rejected explicitly.

Changes apply only to a disposable upstream checkout inside GitHub Actions.
No upstream PR, no boot/hardware execution.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
rule_path = root / "tools/hardware/utils/rule.py"
original = rule_path.read_text()
old_reservation = "        self.reserved = region.align_size(page_bits)"
old_mapped = """        aligned = region.align_size(page_bits)
        self.size = aligned.size"""
assert original.count(old_reservation)==1
assert original.count(old_mapped)==1

# Do not change Region.align_size or hardware.utils.align_up globally.
new_reservation = """        # The full device is reserved, even when its base is not page-aligned.
        aligned_start =  (region.base >> page_bits) << page_bits
        aligned_end = hardware.utils.align_up(region.base + region.size, page_bits)
        self.reserved = Region(aligned_start, aligned_end - aligned_start, region.owner)"""
# rule.py imports the Region, but not hardware itself. Use the existing
# Region/memory implementation's imported hardware module as a local import.
new_reservation = new_reservation.replace(
    "        # The full device is reserved",
    "        from hardware.utils import align_up\n        # The full device is reserved"
).replace("hardware.utils.align_up(region.base + region.size, page_bits)",
          "align_up(region.base + region.size, page_bits)")
new_mapped = """        aligned = region.align_size(page_bits)
        if region.size and aligned.base + aligned.size < region.base + region.size:
            raise ValueError(
                "kernel device mapping does not cover its configured MMIO range: "
                "{}; device base=0x{:x}, mapped size=0x{:x}, page bits={}".format(
                    self.desc, region.base, region.size, page_bits))
        self.size = aligned.size"""
patched = original.replace(old_reservation,new_reservation).replace(old_mapped,new_mapped)

def run(args, expect_failure=False):
    p=subprocess.run([str(x) for x in args],text=True,capture_output=True)
    if expect_failure:
        assert p.returncode != 0, "expected generator rejection but succeeded"
        assert "kernel device mapping does not cover" in p.stderr,(p.stdout[-700:],p.stderr[-1500:])
    elif p.returncode:
        raise RuntimeError(" ".join(map(str,args))+"\n"+p.stderr[-2000:]+"\n"+p.stdout[-900:])
    return p

def gen(dtb, arch, output, yaml_config=None, expect_failure=False):
    args=[sys.executable,root/"tools/hardware_gen.py",
          "--dtb",dtb,"--hardware-config",yaml_config or root/"tools/hardware.yml",
          "--hardware-schema",root/"tools/hardware_schema.yml",
          "--sel4arch",arch,"--c-header","--header-out",output]
    run(args,expect_failure)
    return None if expect_failure else output.read_text()

def reserved(header):
    block=header.split("kernel_device_reserved_regions[] = {",1)[1].split("};",1)[0]
    starts=re.findall(r"\.start\s*=\s*0x([0-9a-fA-F]+)",block)
    ends=re.findall(r"\.end\s*=\s*0x([0-9a-fA-F]+)",block)
    assert len(starts)==len(ends)==1
    return int(starts[0],16),int(ends[0],16)

def frames(header):
    block=header.split("kernel_device_frames[] = {",1)[1].split("};",1)[0]
    return re.findall(r"\.paddr\s*=\s*0x([0-9a-fA-F]+)",block)

def dts(base,size):
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

def header_diff(a,b):
    return a != b

result=[]
try:
    with TemporaryDirectory() as td:
        tmp=Path(td)
        # Use the real PL310 rule with an independently realistic short
        # kernel-mapped prefix (32 bytes), while reserving the full device.
        cfg=(root/"tools/hardware.yml").read_text()
        anchor="        kernel: L2CC_L2C310_PPTR"
        assert cfg.count(anchor)==1
        small_cfg=tmp/"hardware-small-prefix.yml"
        small_cfg.write_text(cfg.replace(anchor,anchor+"\n        kernel_size: 0x20"))

        # Mapping covers the first 32 bytes; reservation should grow to cover
        # all 0x1000 bytes. Frame list must remain identical.
        for name,b,size,custom,expect_failure in [
            ("reservation-only-cross",0x1003,0x1000,True,False),
            ("mapped-cross-rejected",0x1003,0x1000,False,True),
            ("unaligned-short",0x1003,0x20,False,False),
            ("aligned-full",0x1000,0x1000,False,False),
            ("start-near-boundary",0x1ff0,0x30,True,False),
        ]:
            source=tmp/(name+".dts");dtb=tmp/(name+".dtb")
            source.write_text(dts(b,size))
            run(["dtc","-q","-I","dts","-O","dtb","-o",dtb,source])
            yaml_config=small_cfg if custom else None
            rule_path.write_text(original)
            before=gen(dtb,"aarch64",out/(name+"-baseline.h"),yaml_config)
            rule_path.write_text(patched)
            after=gen(dtb,"aarch64",out/(name+"-candidate.h"),yaml_config,expect_failure)
            if expect_failure:
                assert before is not None
                result.append(dict(type="synthetic",case=name,outcome="reject_undercovered_kernel_mapping"))
                print("SPLIT_REJECT_UNSAFE_MAPPING",name)
                continue
            assert after is not None and before is not None
            assert frames(after)==frames(before),(name,"existing MMIO frames changed")
            expect=(b//4096*4096,((b+size+4095)//4096)*4096)
            assert reserved(after)==expect,(name,reserved(after),expect)
            if name in {"reservation-only-cross","start-near-boundary"}:
                assert reserved(before)!=reserved(after),(name,"expected reservation difference")
            else:
                assert before==after,(name,"no-impact fixture changed")
            result.append(dict(type="synthetic",case=name,outcome="pass",
                               legacy_mapping_unchanged=True,
                               reservation_before=[hex(x) for x in reserved(before)],
                               reservation_after=[hex(x) for x in reserved(after)],
                               generated_header_changed=header_diff(before,after)))
            print("SPLIT_SYNTHETIC",name,"mapping_unchanged",
                  "reservation",reserved(before),"->",reserved(after))

        # Existing production device-tree inputs must have exactly the same
        # entire generated C headers as baseline. Check 20 specific platforms.
        cases=[
          ("spike","riscv64"),("ariane","riscv64"),("hifive","riscv64"),
          ("star64","riscv64"),("bananapi-f3","riscv64"),("cheshire","riscv64"),
          ("fvp","aarch64"),("rpi4","aarch64"),("odroidc2","aarch64"),
          ("tx1","aarch64"),("tx2","aarch64"),("exynos5422","aarch32"),
          ("rock3b","aarch64"),("imx8mq-evk","aarch64"),("imx8mp-evk","aarch64"),
          ("imx7sabre","aarch32"),("am335x-boneblack","aarch32"),
          ("allwinnerA20","aarch32"),("omap3","aarch32"),("sabre","aarch32")]
        ok=0
        for name,arch in cases:
            source=root/"tools/dts"/(name+".dts")
            overlays=sorted(root.glob("src/plat/**/overlay-"+name+".dts"))
            assert source.exists() and overlays,(name,"missing pair")
            combined=tmp/(name+"-combined.dts");binary=tmp/(name+".dtb")
            parts=[source.read_text(),overlays[0].read_text()]
            if name=="rpi4":parts.append((root/"src/plat/bcm2711/overlay-rpi4-8gb.dts").read_text())
            combined.write_text("\n".join(parts))
            run(["dtc","-q","-I","dts","-O","dtb","-o",binary,combined])
            rule_path.write_text(original)
            before=gen(binary,arch,out/(name+"-baseline.h"))
            rule_path.write_text(patched)
            after=gen(binary,arch,out/(name+"-candidate.h"))
            assert before==after,(name,"production C header changed")
            ok+=1
            result.append(dict(type="platform",case=name,outcome="byte-identical",
                               sha256=hashlib.sha256(before.encode()).hexdigest()))
            print("SPLIT_PLATFORM_IDENTICAL",name)
        assert ok==20
finally:
    rule_path.write_text(original)
(out/"split-mapping-reservation-summary.json").write_text(json.dumps(result,indent=2)+"\n")
print("SPLIT_CONTRACT_PASS",len([r for r in result if r["type"]=="synthetic"]),
      "synthetic",len([r for r in result if r["type"]=="platform"]),
      "real-platform headers; physical hardware not tested")
