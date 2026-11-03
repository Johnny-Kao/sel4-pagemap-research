#!/usr/bin/env python3
"""Integration check using actual seL4 DTS + overlay pairs and hardware_gen.py."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

root, out = map(lambda p: Path(p).resolve(), sys.argv[1:3])
out.mkdir(parents=True, exist_ok=True)
cases = [
 ("spike","riscv64"),("ariane","riscv64"),("hifive","riscv64"),
 ("star64","riscv64"),("bananapi-f3","riscv64"),("cheshire","riscv64"),
 ("fvp","aarch64"),("rpi4","aarch64"),("odroidc2","aarch64"),
 ("tx1","aarch64"),("tx2","aarch64"),("exynos5422","aarch32"),
 ("rock3b","aarch64"),("imx8mq-evk","aarch64"),("imx8mp-evk","aarch64"),
 ("imx7sabre","aarch32"),("am335x-boneblack","aarch32"),
 ("allwinnerA20","aarch32"),("omap3","aarch32"),("sabre","aarch32")
]
memory = root / "tools/hardware/memory.py"
baseline = memory.read_text()
old = """        new_base = hardware.utils.align_down(self.base, align_bits)
        new_size = hardware.utils.align_up(self.size, align_bits)
        return Region(new_base, new_size, self.owner)"""
new = """        new_base = hardware.utils.align_down(self.base, align_bits)
        if self.size == 0:
            return Region(new_base, 0, self.owner)
        new_end = hardware.utils.align_up(self.base + self.size, align_bits)
        return Region(new_base, new_end - new_base, self.owner)"""
assert baseline.count(old) == 1
candidate = baseline.replace(old, new)

def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)

def header(dtb, arch, path):
    args = [sys.executable, str(root / "tools/hardware_gen.py"),
            "--dtb", str(dtb), "--hardware-config", str(root / "tools/hardware.yml"),
            "--hardware-schema", str(root / "tools/hardware_schema.yml"),
            "--sel4arch", arch, "--c-header", "--header-out", str(path)]
    result = run(args)
    if result.returncode:
        raise RuntimeError(result.stderr[-800:])
    return path.read_text()

results = []
try:
    for name, arch in cases:
        source = root / "tools/dts" / (name + ".dts")
        overlays = list(root.glob("src/plat/**/overlay-" + name + ".dts"))
        if not source.exists() or not overlays:
            results.append(dict(name=name, arch=arch, status="missing-pair"))
            continue
        with TemporaryDirectory() as temp:
            temp = Path(temp)
            combined = temp / "combined.dts"
            combined.write_text(source.read_text() + "\n" + overlays[0].read_text())
            dtb = temp / "combined.dtb"
            built = run(["dtc", "-q", "-I", "dts", "-O", "dtb", "-o", str(dtb), str(combined)])
            if built.returncode:
                results.append(dict(name=name, arch=arch, status="dtc-error", error=built.stderr[-500:]))
                continue
            try:
                memory.write_text(baseline)
                before = header(dtb, arch, out / (name + "-before.h"))
                memory.write_text(candidate)
                after = header(dtb, arch, out / (name + "-after.h"))
                diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                                fromfile="baseline", tofile="candidate", lineterm=""))
                if diff:
                    (out / (name + ".diff")).write_text("\n".join(diff) + "\n")
                results.append(dict(name=name, arch=arch, status="ok", changed=bool(diff),
                                    diff_lines=len(diff),
                                    before_sha=hashlib.sha256(before.encode()).hexdigest(),
                                    after_sha=hashlib.sha256(after.encode()).hexdigest(),
                                    changed_lines=[x for x in diff if x[:1] in ("+", "-") and
                                                   not x.startswith(("+++", "---"))][:30]))
            except Exception as exc:
                results.append(dict(name=name, arch=arch, status="generator-error", error=str(exc)[-600:]))
finally:
    memory.write_text(baseline)
(out / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
for item in results:
    print(item["name"], item["arch"], item["status"],
          "CHANGED" if item.get("changed") else "", item.get("error", "")[:110])
success = [x for x in results if x["status"] == "ok"]
print("SUMMARY", len(cases), "selected", len(success), "generated",
      sum(x["changed"] for x in success), "changed")
if len(success) < 5:
    sys.exit("Insufficient platform coverage: fewer than five generated headers")
