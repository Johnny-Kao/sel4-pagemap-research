#!/usr/bin/env python3
"""Inventory kernel-selected device regions from supported DTS/overlay pairs.

Reports translated physical base/size, hardware.yml kernel_size, page bits,
and independent reservation/mapping undercoverage, with no patch applied.
"""
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / "tools"))
import yaml
from hardware.fdt import FdtParser
from hardware.config import get_arch_config
from hardware.utils.rule import HardwareYaml

cases = [
 ("spike","riscv64"),("ariane","riscv64"),("hifive","riscv64"),
 ("star64","riscv64"),("bananapi-f3","riscv64"),("cheshire","riscv64"),
 ("fvp","aarch64"),("rpi4","aarch64"),("odroidc2","aarch64"),
 ("tx1","aarch64"),("tx2","aarch64"),("exynos5422","aarch32"),
 ("rock3b","aarch64"),("imx8mq-evk","aarch64"),("imx8mp-evk","aarch64"),
 ("imx7sabre","aarch32"),("am335x-boneblack","aarch32"),
 ("allwinnerA20","aarch32"),("omap3","aarch32"),("sabre","aarch32")
]
rules = yaml.safe_load((root / "tools/hardware.yml").read_text())
results = []
failures = 0
for name, arch in cases:
    base = root / "tools/dts" / (name + ".dts")
    overlays = sorted(root.glob("src/plat/**/overlay-" + name + ".dts"))
    if not base.exists() or not overlays:
        results.append({"platform": name, "arch": arch, "status": "missing-pair"})
        continue
    with TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        combined=tmp / "combined.dts"
        fragments=[base.read_text(),overlays[0].read_text()]
        if name=="rpi4": fragments.append((root/"src/plat/bcm2711/overlay-rpi4-8gb.dts").read_text())
        combined.write_text("\n".join(fragments))
        dtb=tmp/"combined.dtb"
        p=subprocess.run(["dtc","-q","-I","dts","-O","dtb","-o",str(dtb),str(combined)],capture_output=True,text=True)
        if p.returncode:
            results.append({"platform":name,"arch":arch,"status":"dtc-failed","error":p.stderr[-500:]})
            continue
        try:
            parser=FdtParser(io.BytesIO(dtb.read_bytes()))
            config=get_arch_config(arch, 1<<32)
            hw=HardwareYaml(rules,config)
            q=1<<config.get_device_page_bits()
            nodes=parser.get_kernel_devices()
            for node in nodes:
                rule=hw.get_rule(node)
                device_regions=node.get_regions()
                for i, rr in sorted(rule.regions.items()):
                    if i>=len(device_regions): continue
                    region=device_regions[i]
                    b,s=region.base,region.size
                    cap=rr.get("kernel_size",q)
                    mapped=min(cap,s)
                    def baseline_end(length): return (b//q)*q+((length+q-1)//q)*q
                    reserve_missed=s>0 and baseline_end(s)<b+s
                    map_missed=mapped>0 and baseline_end(mapped)<b+mapped
                    item={"platform":name,"arch":arch,"status":"ok",
                          "node":node.path,
                          "compatible":list(node.get_prop("compatible").strings) if node.has_prop("compatible") else [],
                          "region_index":i,"base":hex(b),"size":hex(s),
                          "kernel_size":hex(cap),"device_page_size":hex(q),
                          "start_offset":hex(b%q),"size_remainder":hex(s%q),
                          "reserve_undercoverage":reserve_missed,
                          "map_undercoverage":map_missed,
                          "user":bool(rr.get("user",False)),
                          "conditional_macro":rr.get("macro")}
                    results.append(item)
                    if reserve_missed or map_missed: failures+=1
        except Exception as e:
            results.append({"platform":name,"arch":arch,"status":"parse-failed","error":str(e)[-500:]})
for x in results:
    if x["status"]=="ok":
        print("KERNEL_DEVICE",x["platform"],x["arch"],x["node"],"base",x["base"],"size",x["size"],
              "page",x["device_page_size"],"kernel_size",x["kernel_size"],"reserve_missed",x["reserve_undercoverage"],
              "map_missed",x["map_undercoverage"],"user",x["user"])
    elif x["status"]!="missing-pair":
        print("NON_OK",x)
print("SELECTED_INVENTORY",len(cases),"platforms",sum(x["status"]=="ok" for x in results),
      "selected device regions",failures,"triggered regions")
(out/"selected-kernel-device-region-inventory.json").write_text(json.dumps(results,indent=2)+"\n")
if sum(x["status"]=="ok" for x in results)<15:
    raise SystemExit("too few selected kernel-device regions inspected")
if any(x["status"] in {"parse-failed","dtc-failed"} for x in results):
    raise SystemExit("platform inventory incomplete")
