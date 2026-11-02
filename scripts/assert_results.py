#!/usr/bin/env python3
"""Strict verdict for the bounded Page_Map experiment.

This checks that the probe ran to completion and observed the baseline behavior.
A mismatch is recorded as an unexpected result (CI fails); it is not interpreted
as evidence of a security vulnerability without separate authority analysis.
"""
import pathlib
import re
import sys

arch, filename = sys.argv[1:]
log = pathlib.Path(filename).read_text(errors="replace")
assert "Test suite passed." in log, "suite did not complete"
assert "PAGEMAP_STAGE S99_COMPLETED" in log, "probe did not reach final state"
def value(key):
    found = re.search(r"PAGEMAP_RESULT\s+" + re.escape(key) + r"=([^\\\s]+)", log)
    if found is None:
        raise AssertionError("Missing probe field: " + key)
    return found.group(1)

assert "Test PAGEMAP0001 passed" in log, "sel4test probe not complete"
assert log.count("Running test PAGEMAP0001 ") == 1, "unexpected repeated or absent probe"
assert log.count("PAGEMAP_RESULT map_a=") == 1, "ambiguous or missing probe record"
assert value("map_a") == "0"
if arch == "riscv64":
    assert value("map_b_occupied") == "8", "Expected DeleteFirst"
else:
    required = {
        "map_b_occupied": "0",
        "collision_read": "0x6b4d2e8c",
        "map_c_occupied": "0",
        "c_after_second_collision": "0x3c7a29b5",
        "stale_unmap_b": "0",
        "c_immediately_after_stale_unmap_b": "0x3c7a29b5",
        "map_b_after_c": "0",
        "b_after_c_restore": "0x6b4d2e8c",
        "stale_unmap_c": "0",
        "b_immediately_after_stale_unmap_c": "0x6b4d2e8c",
        "stale_a_map_same_va": "0",
        "stale_a_map_read": "0x5a3c1d7b",
        "restore_b_after_stale_a": "0",
        "restored_b_read": "0x6b4d2e8c",
        "unmap_a": "0",
        "b_immediately_after_stale_unmap": "0x6b4d2e8c",
        "remap_a_elsewhere": "0",
        "remap_a_content": "0x5a3c1d7b",
        "unmap_a_elsewhere": "0",
        "remap_b_same_va": "0",
        "b_after_stale_a_unmap": "0x6b4d2e8c",
        "unmap_b": "0",
        "remap_a_original": "0",
        "a_after_b_unmap": "0x5a3c1d7b",
    }
    for key, expected in required.items():
        actual = value(key)
        assert actual == expected, f"{key}: got {actual}, expected {expected}"
    stages = ["S00_BEGIN", "S01_BEFORE_COLLISION", "S02_AFTER_COLLISION_RC", "S02A_BEFORE_C_COLLISION", "S02B_BEFORE_B_RESTORE", "S02C_CHAIN_COMPLETED", "S03_BEFORE_STALE_UNMAP", "S04_AFTER_STALE_UNMAP_OBSERVATION", "S05_BEFORE_B_REMAP", "S06_BEFORE_B_UNMAP", "S99_COMPLETED"]
    offsets = [log.index("PAGEMAP_STAGE " + marker) for marker in stages]
    assert offsets == sorted(offsets), "probe stages out of order"
    if arch == "aarch64":
        rc = value("stale_a_clean_data")
        assert rc == "2", "Expected seL4_InvalidCapability for stale A cap on tested ARM EL1"
        assert value("b_after_stale_a_clean") == "0x6b4d2e8c", "Replacement frame unexpectedly changed"
        print("cache_clean_result=" + rc + " (report architecture config; not a vulnerability verdict)")
print("VERDICT: OBSERVED_EXPECTED_TEST_MATRIX arch=" + arch)
print("LIMIT: does not prove memory isolation, confidentiality, or CVE severity")
