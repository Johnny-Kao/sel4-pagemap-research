import sys
import unittest
import types

# The focused fixture does not parse DTBs; minimal pyfdt structural types
# allow importing the unmodified hardware rule definitions without dependencies.
try:
    import pyfdt.pyfdt
except ImportError:
    pkg = types.ModuleType("pyfdt")
    sub = types.ModuleType("pyfdt.pyfdt")
    sub.FdtNode = type("FdtNode", (), {})
    sub.FdtProperty = type("FdtProperty", (), {})
    pkg.pyfdt = sub
    sys.modules["pyfdt"] = pkg
    sys.modules["pyfdt.pyfdt"] = sub

import hardware.utils
from hardware.memory import Region
from hardware.utils.rule import KernelRegionGroup


class RegionCoverage(unittest.TestCase):
    def test_edge_cases_cover_original(self):
        for bits in (12, 14, 16):
            for offset in (0, 1, 3, 128, (1 << bits) - 1):
                for size in (1, 100, 4096, 4097, 8192, 16384):
                    original = Region((1 << bits) + offset, size)
                    aligned = original.align_size(bits)
                    with self.subTest(bits=bits, offset=offset, size=size):
                        self.assertLessEqual(aligned.base, original.base)
                        self.assertGreaterEqual(aligned.base + aligned.size, original.base + original.size)
                        self.assertEqual(aligned.base % (1 << bits), 0)
                        self.assertEqual(aligned.size % (1 << bits), 0)

    def test_empty_and_aligned_regions(self):
        for bits in (12, 14, 16):
            for offset in (0, 1, 3, (1 << bits) - 1):
                empty = Region((1 << bits) + offset, 0).align_size(bits)
                self.assertEqual(empty.size, 0)
                self.assertEqual(empty.base % (1 << bits), 0)
                aligned = Region(1 << bits, 2 << bits).align_size(bits)
                self.assertEqual((aligned.base, aligned.size), (1 << bits, 2 << bits))

    def test_reserved_device_cover(self):
        original = Region(0x1003, 0x1000)
        group = KernelRegionGroup(original, "TEST_DEVICE", 12, 0x1000)
        reserved = group.get_reserved()
        self.assertEqual(reserved.base, 0x1000)
        self.assertEqual(reserved.base + reserved.size, 0x3000)
        self.assertEqual([r.base for r in group.regions], [0x1000, 0x2000])


if __name__ == "__main__":
    unittest.main(verbosity=2)
