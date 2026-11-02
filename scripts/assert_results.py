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
def value(key):
    found = re.search(r"PAGEMAP_RESULT\s+" + re.escape(key) + r"=([^\\\s]+)", log)
    if found is None:
        raise AssertionError("Missing probe field: " + key)
    return found.group(1)

assert "Test PAGEMAP0001 passed" in log, "sel4test probe not complete"
assert value("map_a") == "0"
if arch == "riscv64":
    assert value("map_b_occupied") == "8", "Expected DeleteFirst"
else:
    required = {
        "map_b_occupied": "0",
        "collision_read": "0x6b4d2e8c",
        "stale_a_map_same_va": "0",
        "stale_a_map_read": "0x5a3c1d7b",
        "restore_b_after_stale_a": "0",
        "restored_b_read": "0x6b4d2e8c",
        "unmap_a": "0",
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
    if arch == "aarch64":
        rc = value("stale_a_clean_data")
        assert rc in ("0", "2", "3", "4", "5", "6", "7", "8"), "Unknown cache-clean response"
        assert value("b_after_stale_a_clean") == "0x6b4d2e8c", "Replacement frame unexpectedly changed"
        print("cache_clean_result=" + rc + " (report architecture config; not a vulnerability verdict)")
print("VERDICT: OBSERVED_EXPECTED_TEST_MATRIX arch=" + arch)
print("LIMIT: does not prove memory isolation, confidentiality, or CVE severity")
