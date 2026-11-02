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
# The test harness prints literal backslash-n delimiters. Concurrent seL4 kernel
# diagnostics may splice into a printf token; remove only the known diagnostic
# envelopes before validating all individual observations.
log = re.sub(r"\x1b\[[0-9;]*m", "", log)
log = re.sub(r"<<seL4\(CPU \d+\).*?>>\s*", "", log, flags=re.DOTALL)
# Console warnings may split a single C printf over two GitHub log lines:
# after removing the warning, remove the runner timestamp+newline boundary.
log = re.sub(r"\n\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z ", "", log)
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
assert value("auth_invalid_vspace_rc") != "0", "Invalid VSpace cap unexpectedly authorized mapping"
assert value("auth_invalid_vspace_a_read") == "0x5a3c1d7b", "Invalid mapping attempt changed owner contents"
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
        "derived_c_slot_alloc": "0",
        "derived_c_copy": "0",
        "revoke_derived_c": "0",
        "b_after_revoke_c": "0x6b4d2e8c",
        "delete_displaced_c": "0",
        "b_after_displaced_c_delete": "0x6b4d2e8c",
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
    assert value("revoked_c_unmap") != "0", "Revoked child C unexpectedly callable"
    for i in range(4):
        required[f"repeat_stale_c_unmap_{i}"] = "0"
        required[f"repeat_stale_c_read_{i}"] = "0x6b4d2e8c"
    for key, expected in required.items():
        actual = value(key)
        assert actual == expected, f"{key}: got {actual}, expected {expected}"
    stages = ["S00_BEGIN", "S01_BEFORE_COLLISION", "S02_AFTER_COLLISION_RC", "S02A_BEFORE_C_COLLISION", "S02B_BEFORE_B_RESTORE", "S02C_CHAIN_COMPLETED", "S02D_REPEAT_COMPLETED", "S02E_REVOKE_COMPLETED", "S02F_DELETE_COMPLETED", "S03_BEFORE_STALE_UNMAP", "S04_AFTER_STALE_UNMAP_OBSERVATION", "S05_BEFORE_B_REMAP", "S06_BEFORE_B_UNMAP", "S99_COMPLETED"]
    offsets = [log.index("PAGEMAP_STAGE " + marker) for marker in stages]
    assert offsets == sorted(offsets), "probe stages out of order"
    if arch == "aarch64":
        rc = value("stale_a_clean_data")
        assert rc == "2", "Expected seL4_InvalidCapability for stale A cap on tested ARM EL1"
        assert value("b_after_stale_a_clean") == "0x6b4d2e8c", "Replacement frame unexpectedly changed"
        print("cache_clean_result=" + rc + " (report architecture config; not a vulnerability verdict)")
print("VERDICT: OBSERVED_EXPECTED_TEST_MATRIX arch=" + arch)
print("LIMIT: does not prove memory isolation, confidentiality, or CVE severity")

print("CASE_AUTH_INVALID_VSPACE_NEGATIVE_CONTROL=OBSERVED_REJECTED")
print("CASE_REVOKE_DERIVED_C=" + ("NOT_APPLICABLE" if arch == "riscv64" else "OBSERVED_ACTIVE_B_INTACT"))
print("CASE_DELETE_DISPLACED_C=" + ("NOT_APPLICABLE" if arch == "riscv64" else "OBSERVED_ACTIVE_B_INTACT"))
print("CASE_COLLISION=" + ("REJECTED_AS_EXPECTED" if arch == "riscv64" else "CONFIRMED_OVERWRITE"))
print("CASE_STALE_UNMAP=" + ("NOT_APPLICABLE_COLLISION_REJECTED" if arch == "riscv64" else "OBSERVED_NO_DISRUPTION"))
print("CASE_THREE_FRAME_CHAIN=" + ("NOT_APPLICABLE_COLLISION_REJECTED" if arch == "riscv64" else "OBSERVED_NO_DISRUPTION"))
print("CASE_REPEATED_UNMAP=" + ("NOT_APPLICABLE_COLLISION_REJECTED" if arch == "riscv64" else "OBSERVED_NO_DISRUPTION"))
print("CASE_ARM_CACHE_CLEAN=" + ("OBSERVED_REJECTED" if arch == "aarch64" else "NOT_APPLICABLE"))
for case in ("AUTH_1_CROSS_DOMAIN", "AUTH_2_EFFECTIVE_RIGHTS", "LIFE_1_REVOKE",
             "LIFE_2_FRAME_REUSE", "PREEMPT_1", "CACHE_1_EL2"):
    print("CASE_" + case + "=NOT_TESTED")
