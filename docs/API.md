# Code / API Reference

Auto-generated from module and function docstrings.


## `actuators.py`

Actuator tests (Phase 3) and maintenance functions (Phase 4).

- **def `run_actuator_test`** — Run one actuator test. Real car refuses unless the command is

## `adaptations.py`

DME adaptation reset (Phase 2).

- **def `mask_for`** — OR the selection bits for the named groups. Unknown names raise.
- **def `build_selective_erase`** — Build the DS2 payload for a selective adaptation erase, EXCEPT the
- **def `read_adaptation_groups`** — Read the three adaptation groups (read-only). Returns
- **def `reset_adaptations`** — Full adaptation-reset flow through the transaction layer.

## `coding.py`

Coding data structures and decoders for BMW modules.

- **class `CodingDecoder`** — Decode module coding bytes into human-readable structure.
- **def `get_coding_decoder`** — Get appropriate coding decoder for a module.
- **def `get_presets_for_module`** — Get available coding presets for a module.

## `compare.py`

Recording comparison & analysis engine (Phase 6).

- **def `parse_csv`** — Return {channel_id: [float,...]} plus meta (events, row count).

## `correlate.py`

Correlation engine (Phase 7.2) — discover which signals track a target.

- **def `pearson`** — Pearson correlation of two equal-length numeric series; 0 if flat.
- **def `correlate_channels`** — Rank channels in a log by |correlation| against `target`.
- **def `correlate_ram`** — Locate RAM offsets whose value tracks target_values.

## `dev_console.py`

Developer Mode — safe raw console backend (Phase 8).

- **def `check_request`** — Return (allowed: bool, reason: str) for a raw request payload.
- **def `send_raw`** — Send a raw request after the safety check. Never sends a denied

## `diag_ui.py`

Web UI for BMW K-line diagnostics — faults, clearing, live data + graphs.

- **class `E39Adapter`** — DS2 protocol (1998 523i).
- **class `DemoAdapter`** — Simulated 523i for demoing the UI without the car connected.
- **class `E87Adapter`** — KWP2000 (2005 E87).
- **class `VanosMonitor`** — Correlates the VANOS solenoid command (S23) with the measured cam
- **def `log_vanos_event`** — Persist a VANOS event with a telemetry snapshot; returns UI payload.
- **def `load_gear_ratios`** — Load calibrated gear ratios from file, or return defaults.
- **def `save_gear_ratios`** — Save calibrated gear ratios to file.
- **def `is_stable_for_calibration`** — Check if driving conditions are stable enough for gear calibration.
- **def `estimate_gear`** — Estimate current gear from RPM and vehicle speed ratio.
- **def `evaluate_health`** — M52-specific health evaluation from live data.
- **def `detect_pull`** — Detect pull start/end based on throttle, load, and RPM.
- **def `csv_writer_thread`** — Background thread: process CSV queue and write samples to disk.
- **def `sampler`** — Background thread: poll live data while any SSE client is attached.

## `dme_registry.py`

E39 engine/DME registry + auto-detection (multi-car support, Phase 10-ish).

- **def `detect_dme`** — Return the DME descriptor matching an ident ASCII, or an 'unknown'
- **def `load_params`** — Load the RAM parameter list for a detected DME, or [] if none.

## `ds2_diag.py`

BMW DS2 diagnostics for pre-2001 cars (E39/E38/E36 era) over a K+DCAN cable.

- **def `fault_type_text`** — Decode a fault entry's type byte (2nd byte). Exact match first, then
- **def `body`** — Payload after addr+len+status, before checksum.
- **class `MS41Logger`** — Fast multi-parameter logging from the MS41 DME via the DS2
- **def `ram_read`** — Read-only RAM explorer (Phase 7.1). Reads a list of 16/32-bit MS41
- **def `ram_dump_range`** — Read a contiguous RAM window (start..start+count) in chunks. Read-only.
- **def `ram_diff`** — Offline (Phase 7.3): compare two RAM dumps ({addr:value}), return the
- **def `mode_live`** — Poll DME analog block (0B 03) + IKE block (0B 0A); annotate changes.

## `kline_obd.py`


## `operations.py`

BMW operation database with graded Evidence (Protocol Explorer core).

- **def `evidence_grade`** — One-word grade for UI/reporting, derived from the flags.
- **def `usable_on_car`** — True only if we can construct it AND it is safe or tested. Writes
- **def `seed_db`** — Seed the DB with operations this platform has actually verified this

## `plugins.py`

Plugin architecture (Phase 9 scaffold).

- **class `ModulePlugin`** — Base class for a diagnostic module plugin. Subclasses fill in the
- **class `Registry`** — Holds registered plugins and answers lookups by kind/address.

## `power_diag.py`

BMW E87 K-line power-supply diagnostics over a K+DCAN (FTDI) cable on macOS.

- **def `decode_dtc_payload`** — p = 58 n [hi lo status]*n
- **def `mode_clear`** — Clear fault memory (KWP clearDiagnosticInformation, service 0x14),
- **def `mode_detail`** — Read fault memory, then per-DTC environment/freeze-frame records.

## `sgbd_parser.py`

SGBD/PRG job parser (Protocol Explorer — "the gold mine").

- **def `parse_sgbd_markdown`** — Parse one SGBD markdown doc into operation records.
- **def `parse_dir`** — Parse every sgbd_docs/*.md into operation records.

## `snapshot.py`

Full-vehicle snapshot system (Phase 5).

- **def `create_snapshot`** — Read every responding module and persist one snapshot record.
- **def `list_snapshots`** — List snapshots, newest first. If vin is None, scan all VINs.
- **def `diff_snapshots`** — Structural diff of two snapshot dicts (or dirs/paths).

## `trace.py`

K-line trace parser, diff and replay (Protocol Explorer).

- **def `parse_trace`** — source = path, file-like, or list of lines. Returns frame dicts.
- **def `extract_requests`** — Unique request payloads (service + args), keyed by (ecu, payload).
- **def `trace_diff`** — Requests present in trace A but not B, and vice versa. Useful to spot
- **def `replay_plan`** — Ordered, de-duplicated READ-ONLY requests safe to replay. Write and
- **def `annotate_with_db`** — Match each request's service against the operation DB to label it.

## `transaction.py`

Transaction layer for safe module writes with automatic backup + verify + rollback.

- **class `TransactionError`** — Base exception for transaction failures.
- **class `VerificationError`** — Write verification failed - data doesn't match expected state.
- **class `RollbackError`** — Rollback failed after verification error.
- **class `TransactionManager`** — Manages safe write transactions with automatic backup + verify + rollback.
- **def `get_transaction_manager`** — Get or create global transaction manager instance.

## `vehicle_profiles.py`

Vehicle profile abstraction (Phase 10 scaffold).

- **def `get_profile`** — Return a profile by protocol key (e39/e87/...) or None.
- **def `list_profiles`** — Summaries for a vehicle picker UI.
- **def `validate_profile`** — Structural check for a profile dict — used when adding a new car so

## `verification.py`

Evidence promotion: sourced -> car-verified (answers "does connecting a
car auto-verify?").

- **def `plausibility_check`** — Return {checks:[...], passed:bool}. Each check reports the channel,
- **def `record_verification`** — Attempt to promote a DME map to verified for this VIN.
- **def `dme_evidence`** — Overlay verified status onto a DME's base evidence string.
