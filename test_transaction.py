#!/usr/bin/env python3
"""Test transaction layer independently."""
import sys
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from transaction import TransactionManager

def test_basic_transaction():
    """Test basic transaction flow."""
    tm = TransactionManager(backup_root="/tmp/bmw_test_backups")

    # Simulate fault clear operation
    fake_faults_before = {"count": 3, "entries": [{"code": "2C55"}, {"code": "2C45"}, {"code": "93B2"}]}
    fake_faults_after = {"count": 0, "entries": []}

    state = {"current": fake_faults_before}

    def read_fn():
        return state["current"]

    def write_fn():
        state["current"] = fake_faults_after
        return {"ok": True, "after": fake_faults_after}

    def verify_fn():
        return state["current"]["count"] == 0

    result = tm.execute(
        vin="WBAXXXXXXXXXXXXXX",
        module_name="DME",
        module_addr=0x12,
        operation="clear_faults",
        read_fn=read_fn,
        write_fn=write_fn,
        verify_fn=verify_fn,
        user_note="Test fault clear"
    )

    print(f"Transaction result: {result}")
    print(f"Success: {result['success']}")
    print(f"Backup path: {result['backup_path']}")
    print(f"Verified: {result['verified']}")

    # List backups
    backups = tm.list_backups("WBAXXXXXXXXXXXXXX")
    print(f"\nBackups for VIN WBAXXXXXXXXXXXXXX:")
    for b in backups:
        print(f"  {b['timestamp']} - {b['operation']} - verified: {b.get('verified')}")

    # Retrieve backup
    if backups:
        backup_data = tm.get_backup("WBAXXXXXXXXXXXXXX", backups[0]["operation_id"])
        print(f"\nBackup data:")
        print(f"  Metadata: {backup_data['metadata']}")
        print(f"  Data: {backup_data['data']}")

def test_get_backup_rejects_path_traversal():
    """operation_id (and vin) can come straight from an HTTP request
    (diag_ui.py's /api/backup/<operation_id>) -- an unsanitized ".." there
    used to let a caller read a metadata.json from outside backup_root."""
    tmp = tempfile.mkdtemp()
    tm = TransactionManager(backup_root=tmp)

    outside = tempfile.mkdtemp()
    with open(os.path.join(outside, "metadata.json"), "w") as f:
        f.write('{"modules": {"secret": true}}')

    traversal = "../" * 10 + outside.lstrip("/")
    assert tm.get_backup("SOMEVIN", traversal) is None
    print("test_get_backup_rejects_path_traversal OK")


if __name__ == "__main__":
    test_basic_transaction()
    test_get_backup_rejects_path_traversal()
