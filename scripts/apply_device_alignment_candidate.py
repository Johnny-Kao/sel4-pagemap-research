#!/usr/bin/env python3
"""Apply a minimal alignment fix to a disposable upstream source checkout."""
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
original = path.read_text()
old = """        new_base = hardware.utils.align_down(self.base, align_bits)
        new_size = hardware.utils.align_up(self.size, align_bits)
        return Region(new_base, new_size, self.owner)"""
new = """        new_base = hardware.utils.align_down(self.base, align_bits)
        new_end = hardware.utils.align_up(self.base + self.size, align_bits)
        return Region(new_base, new_end - new_base, self.owner)"""
if original.count(old) != 1:
    raise SystemExit("Expected exact upstream align_size source once; refusing to patch")
path.write_text(original.replace(old, new))
