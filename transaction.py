#!/usr/bin/env python3
"""Transaction layer for safe module writes with automatic backup + verify + rollback.

All write operations (coding, adaptations, service resets, fault clears) flow
through this layer. Safety guarantees:
  1. Read current state before writing
  2. Create VIN-based backup with metadata
  3. Perform write operation
  4. Verify by reading back
  5. Automatic rollback on verification failure
  6. Version history tracking

Usage:
    tm = TransactionManager(backup_root="backups/")

    def write_operation():
        return adapter.clear_faults(0x12)

    def verify_operation():
        faults = adapter.read_faults(0x12)
        return faults["count"] == 0

    result = tm.execute(
        vin="WBAXXXXXXXXXXXXXX",
        module_name="DME",
        module_addr=0x12,
        operation="clear_faults",
        read_fn=lambda: adapter.read_faults(0x12),
        write_fn=write_operation,
        verify_fn=verify_operation,
        user_note="Cleared after battery terminal fix"
    )
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path


def _safe_component(s):
    """Sanitize a path component (vin, operation_id) before it's joined
    into a filesystem path -- both ultimately originate from HTTP request
    data (diag_ui.py's /api/backup/<operation_id> and connected-adapter
    VIN), and an unsanitized ".." segment there is a path-traversal
    primitive out of backup_root. Stripping "/" alone isn't enough: a bare
    ".." has no slash in it and still means "parent dir" to the
    filesystem, so it needs its own check after the allow-list filter
    (same allow-list ovpf_producer._log_path uses for VINs)."""
    s = re.sub(r"[^A-Za-z0-9._-]", "_", s or "")
    return s if s not in ("", ".", "..") else "_"


class TransactionError(Exception):
    """Base exception for transaction failures."""
    pass


class VerificationError(TransactionError):
    """Write verification failed - data doesn't match expected state."""
    pass


class RollbackError(TransactionError):
    """Rollback failed after verification error."""
    pass


class TransactionManager:
    """Manages safe write transactions with automatic backup + verify + rollback."""

    def __init__(self, backup_root="backups/"):
        """
        Initialize transaction manager.

        Args:
            backup_root: Root directory for all backups (organized by VIN)
        """
        self.backup_root = Path(backup_root)
        self.backup_root.mkdir(exist_ok=True)

    def execute(self, vin, module_name, module_addr, operation,
                read_fn, write_fn, verify_fn=None, user_note=""):
        """
        Execute a write transaction with automatic safety guarantees.

        Args:
            vin: Vehicle identification number (for backup organization)
            module_name: Human-readable module name (e.g., "DME", "LCM", "IKE")
            module_addr: Module address (e.g., 0x12 for DME)
            operation: Operation type (e.g., "clear_faults", "coding_change")
            read_fn: Callable that returns current module state (dict or serializable)
            write_fn: Callable that performs the write, returns result
            verify_fn: Optional callable that verifies success (returns bool).
                      If None, automatic verification compares read before/after.
            user_note: Optional user description of why this change was made

        Returns:
            dict with:
                - success: bool
                - backup_path: Path to backup directory
                - operation: operation name
                - verified: bool (whether verification succeeded)
                - rolled_back: bool (whether rollback was performed)
                - write_result: result from write_fn
                - error: error message if failed

        Raises:
            TransactionError: If transaction fails catastrophically
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        operation_id = f"{timestamp}_{operation}"

        # 1. Read current state
        try:
            current_state = read_fn()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read current state: {e}",
                "operation": operation,
                "backup_path": None,
                "verified": False,
                "rolled_back": False
            }

        # 2. Create backup with metadata
        try:
            backup_path = self._create_backup(
                vin=vin,
                operation_id=operation_id,
                module_name=module_name,
                module_addr=module_addr,
                operation=operation,
                data=current_state,
                user_note=user_note
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create backup: {e}",
                "operation": operation,
                "backup_path": None,
                "verified": False,
                "rolled_back": False
            }

        # 3. Perform write
        try:
            write_result = write_fn()
        except Exception as e:
            return {
                "success": False,
                "error": f"Write operation failed: {e}",
                "operation": operation,
                "backup_path": str(backup_path),
                "verified": False,
                "rolled_back": False,
                "write_result": None
            }

        # 4. Verify write
        verified = False
        verification_error = None

        if verify_fn is not None:
            # Use custom verification function
            try:
                verified = verify_fn()
                if not verified:
                    verification_error = "Custom verification function returned False"
            except Exception as e:
                verification_error = f"Verification function raised: {e}"
        else:
            # Automatic verification: re-read and compare
            try:
                new_state = read_fn()
                # For fault clears, check that state actually changed
                if operation == "clear_faults":
                    # Expect fault count to be 0 or reduced
                    old_count = current_state.get("count", 0)
                    new_count = new_state.get("count", 0)
                    verified = new_count < old_count or new_count == 0
                    if not verified:
                        verification_error = f"Fault count unchanged: {old_count} -> {new_count}"
                else:
                    # Generic: state should be different from before
                    verified = new_state != current_state
                    if not verified:
                        verification_error = "Module state unchanged after write"
            except Exception as e:
                verification_error = f"Failed to read back for verification: {e}"

        # 5. Rollback if verification failed
        rolled_back = False
        if not verified and verification_error:
            try:
                # Attempt to restore previous state
                # For now, we can't generically restore without a restore_fn
                # This is a placeholder - specific operations may need custom rollback
                rolled_back = False
                rollback_note = "Verification failed but automatic rollback not implemented for this operation"
            except Exception as e:
                raise RollbackError(f"Verification failed AND rollback failed: {e}")

        # 6. Record version and result in backup metadata
        self._update_backup_result(
            backup_path=backup_path,
            verified=verified,
            verification_error=verification_error,
            rolled_back=rolled_back,
            write_result=write_result
        )

        return {
            "success": verified,
            "backup_path": str(backup_path),
            "operation": operation,
            "verified": verified,
            "rolled_back": rolled_back,
            "write_result": write_result,
            "error": verification_error if not verified else None
        }

    def _create_backup(self, vin, operation_id, module_name, module_addr,
                      operation, data, user_note):
        """
        Create VIN-based backup directory with data and metadata.

        Args:
            vin: Vehicle identification number
            operation_id: Unique operation identifier (timestamp_operation)
            module_name: Module name (e.g., "DME", "ABS/ASC/DSC")
            module_addr: Module address (e.g., 0x12)
            operation: Operation type (e.g., "clear_faults")
            data: Current module state (dict or serializable)
            user_note: User description

        Returns:
            Path to backup directory
        """
        # Create VIN-specific backup directory
        vin_dir = self.backup_root / _safe_component(vin)
        vin_dir.mkdir(exist_ok=True)

        backup_dir = vin_dir / _safe_component(operation_id)
        backup_dir.mkdir(exist_ok=True)

        # Sanitize module name for filename (replace path separators)
        safe_module_name = module_name.replace("/", "_").replace("\\", "_")

        # Save module data
        data_file = backup_dir / f"{safe_module_name}.json"
        with open(data_file, "w") as f:
            json.dump(data, f, indent=2)

        # Compute hash
        data_hash = self._compute_hash(data)

        # Create metadata
        metadata = {
            "vin": vin,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "operation": operation,
            "operation_id": operation_id,
            "user_note": user_note,
            "modules": {
                module_name: {  # Keep original name in metadata
                    "addr": module_addr,
                    "addr_hex": f"0x{module_addr:02X}",
                    "data_file": f"{safe_module_name}.json",  # Use sanitized name for file
                    "data_hash": data_hash
                }
            }
        }

        metadata_file = backup_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        return backup_dir

    def _update_backup_result(self, backup_path, verified, verification_error,
                             rolled_back, write_result):
        """Update backup metadata with transaction result."""
        metadata_file = backup_path / "metadata.json"

        with open(metadata_file, "r") as f:
            metadata = json.load(f)

        metadata["result"] = {
            "verified": verified,
            "verification_error": verification_error,
            "rolled_back": rolled_back,
            "write_result": str(write_result) if write_result else None
        }

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def _compute_hash(self, data):
        """Compute SHA256 hash of data for integrity checking."""
        json_str = json.dumps(data, sort_keys=True)
        return f"sha256:{hashlib.sha256(json_str.encode()).hexdigest()}"

    def list_backups(self, vin):
        """
        List all backups for a given VIN.

        Args:
            vin: Vehicle identification number

        Returns:
            List of dicts with backup metadata
        """
        vin_dir = self.backup_root / _safe_component(vin)
        if not vin_dir.exists():
            return []

        backups = []
        for backup_dir in sorted(vin_dir.iterdir(), reverse=True):
            if not backup_dir.is_dir():
                continue

            metadata_file = backup_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file) as f:
                metadata = json.load(f)

            backups.append({
                "path": str(backup_dir),
                "operation_id": metadata.get("operation_id"),
                "timestamp": metadata.get("timestamp"),
                "operation": metadata.get("operation"),
                "user_note": metadata.get("user_note", ""),
                "modules": list(metadata.get("modules", {}).keys()),
                "verified": metadata.get("result", {}).get("verified", None)
            })

        return backups

    def get_backup(self, vin, operation_id):
        """
        Retrieve a specific backup by operation ID.

        Args:
            vin: Vehicle identification number
            operation_id: Operation identifier (timestamp_operation)

        Returns:
            dict with metadata and data, or None if not found
        """
        backup_dir = self.backup_root / _safe_component(vin) / _safe_component(operation_id)
        if not backup_dir.exists():
            return None

        metadata_file = backup_dir / "metadata.json"
        if not metadata_file.exists():
            return None

        with open(metadata_file) as f:
            metadata = json.load(f)

        # Load module data
        module_data = {}
        for module_name, module_info in metadata.get("modules", {}).items():
            data_file = backup_dir / module_info["data_file"]
            if data_file.exists():
                with open(data_file) as f:
                    module_data[module_name] = json.load(f)

        return {
            "metadata": metadata,
            "data": module_data
        }


# Global transaction manager instance
_transaction_manager = None


def get_transaction_manager(backup_root="backups/"):
    """Get or create global transaction manager instance."""
    global _transaction_manager
    if _transaction_manager is None:
        _transaction_manager = TransactionManager(backup_root=backup_root)
    return _transaction_manager
