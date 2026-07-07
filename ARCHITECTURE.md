# BMW Diagnostic Platform - Architecture Vision

## Mission

Build a modern, open-source BMW diagnostic workstation that combines diagnostics, coding, adaptations, reverse engineering, and maintenance with **automatic safety guarantees**.

This is NOT just an OBD reader. This is a complete platform for understanding, modifying, and maintaining BMW vehicles.

## Core Principles

1. **Never write without reading first** - every write must know the current state
2. **Every write is reversible** - automatic backups and version control
3. **Backups are VIN-specific** - organized by vehicle identity
4. **Writes are verified** - read back and confirm success
5. **Raw operations are hidden** - only exposed in Developer Mode with warnings
6. **Safety is inherited** - one transaction layer provides guarantees for all operations

## Transaction Layer (Foundation)

Every write operation flows through a single transaction manager:

```python
def safe_write(module, operation, new_data):
    """All writes go through this path - safety is automatic."""
    # 1. Read current state
    current = module.read()
    
    # 2. Create backup
    backup = create_backup(vin=VIN, module=module, data=current, 
                          operation=operation, timestamp=now())
    
    # 3. Perform write
    result = module.write(new_data)
    
    # 4. Verify
    actual = module.read()
    if not verify(actual, new_data):
        # 5. Automatic rollback
        module.write(backup.data)
        raise WriteVerificationError("Auto-rolled back")
    
    # 6. Record version
    record_version(vin=VIN, module=module, backup=backup, 
                  new_data=actual, verified=True)
    return result
```

This layer is built **once**, used by every feature that writes (coding, adaptations, service resets).

## Architecture Overview

### 1. Dashboard
- VIN, model, engine, transmission
- Detected ECUs with part numbers and software versions
- Real-time: battery voltage, current gear, coolant temp
- Health summary (green/yellow/red subsystems)
- Current fault count by module
- Quick actions: scan, clear faults, record

### 2. Diagnostics
**Current implementation** (keep building on this):
- Module scan with ident strings
- Read faults with location + type text (now in English)
- Clear faults with automatic snapshot
- Live data with profiles (E39 MS41: driveability, fuel, knock, sensors, vanos)
- SSE graphs with ~10 Hz refresh
- Health monitoring (charging, coolant, IAT, fuel trim, MAF, VANOS, knock, gear)
- CSV recording with event system (pull_start, pull_end, profile_change, event_data JSON)
- Queue-based writer thread (sampler never blocks on disk I/O)

**Add**:
- Replay mode: visualize recorded drives with synchronized graphs + events
- Comparison: overlay two recordings, auto-generate findings
- Fault history: show snapshots from `fault_snapshots.log` with timestamps
- Environment data: service 0x17 freeze-frame for each DTC

### 3. Coding
Read/modify/write module coding (VO, FA, ZCS) with diff viewer and version control.

**Safety model**:
- Read current coding → decode into human-readable structure
- Show diff: current vs. new (highlight changes)
- User confirms → goes through transaction layer (auto-backup, verify, rollback)
- Version history: factory, +US_blinkers, +comfort_blink, etc.

**Common E39 examples**:
- US turn signals (flash amber instead of red)
- Comfort blink (3 blinks from tap)
- Daytime running lights
- Welcome lights timing
- Auto door lock at speed
- Mirror folding on lock
- Digital speed display

**Implementation**:
- Coding strings are module-specific (IKE, LCM, GM, etc.)
- Some are binary bits, some are BCD tables
- Need per-module decoders (start with IKE/LCM for E39)
- Reverse-engineering is part of this: document unknowns in Developer Mode

### 4. Adaptations
Reset learned values (throttle position, fuel trims, transmission shift points, VANOS adaptation, idle valve position, lambda sensor aging).

**Via transaction layer**: read baseline → user confirms reset → write defaults → verify.

### 5. Actuator Tests
Trigger outputs for testing: fuel pump, cooling fan, VANOS solenoid, injectors, coils, idle valve, ABS pump, window motors, locks, lights. **Read-only by default** - actuator tests are explicit user-initiated actions.

### 6. Maintenance Functions
- Oil service reset (read current → set to factory)
- Inspection reset
- Battery registration (critical for charging profile)
- Brake service reset
- Steering angle sensor calibration
- DPF regeneration (if applicable)

All go through transaction layer.

### 7. Reverse Engineering
**Current foundation**: raw K-line logging (`kline_raw.log`), MS41 fast logger.

**Add**:
- Raw packet console (send arbitrary requests, see responses)
- RAM explorer: dump address ranges, watch values change
- EEPROM explorer (read-only until Developer Mode)
- Memory watch: monitor specific addresses during driving
- Differential logging: compare two memory dumps, highlight differences
- Correlation engine: find which RAM addresses change with throttle, RPM, load, etc.
- Unknown parameter discovery: sweep address ranges, identify live data
- Export discoveries as RomRaider logger XML
- Annotate findings in `ms41_ram_params.json` with confidence levels

### 8. Developer Mode
**Warning banner on every page in this section.**

Exposes raw protocol operations:
- Raw K-Line packets (DS2, KWP2000, UDS)
- Raw CAN frames
- Manual memory read/write (with confirmation + automatic backup)
- Custom service requests
- Packet recorder (capture bus traffic)
- Firmware tools: checksums, disassembly helpers
- No safety rails - user takes full responsibility

### 9. Backup System (Critical Feature)

**Directory structure**:
```
backups/
  WBAXXXXXXXXXXXXXX/  # VIN-based
    2026-07-04_factory/
      DME.json
      LCM.json
      IKE.json
      EWS.json
      metadata.json
    2026-07-05_us_blinkers/
      LCM.json  # only changed module
      metadata.json
    2026-07-10_vanos_adapt_reset/
      DME.json
      metadata.json
```

**Metadata** (per snapshot):
```json
{
  "vin": "WBAXXXXXXXXXXXXXX",
  "timestamp": "2026-07-04T12:34:56Z",
  "vehicle": "1998 BMW 523i (E39)",
  "mileage_km": 287453,
  "operation": "coding_change",
  "description": "Enabled US-style turn signals in LCM",
  "modules": {
    "LCM": {
      "addr": 208,
      "part_number": "61.35-8 368 135",
      "sw_version": "...",
      "data_hash": "sha256:...",
      "verified": true
    }
  },
  "user_note": "Testing comfort blink"
}
```

**Automatic backup triggers**:
- Before every coding change
- Before every adaptation reset
- Before every service function write
- On-demand: "Create Snapshot"

**Restore UI**:
- Show version history for each module
- Diff any two versions (visual diff, not raw hex)
- Restore: entire vehicle snapshot, single module, or specific coding block
- Verify after restore

### 10. Safety Levels

**Green (always safe)**:
- Read faults, idents, live data
- Record diagnostics
- Replay recordings
- View backups

**Yellow (requires confirmation)**:
- Clear faults (snapshots first, already implemented)
- Coding changes (diff shown, backup automatic)
- Adaptation resets (backup automatic)
- Actuator tests (explicit user action)

**Red (dangerous, double confirmation + backup + verify)**:
- EEPROM writes
- VIN programming
- Immobilizer operations
- Flash firmware updates
- Raw memory writes (Developer Mode only)

Red operations **must**:
1. Show large warning
2. Require typing module name to confirm
3. Create backup automatically
4. Verify write by reading back
5. Auto-rollback on verification failure

### 11. Plugin Architecture

**Protocols** (in `protocols/`):
- `ds2.py` - DS2 (pre-EOBD, E39 1998)
- `kwp2000.py` - ISO 14230 (E87 2005, E39 2001+)
- `uds.py` - ISO 14229 (E90 2006+)
- `can.py` - Raw CAN (F-series 2011+)

**Modules** (in `modules/`):
- `dme.py` - engine control (MS41, MS43, MSV70, etc.)
- `ews.py` - immobilizer
- `lcm.py` - light control
- `ike.py` - instrument cluster
- `abs.py` - ABS/DSC
- `gm.py` - central body electronics
- `ihka.py` - climate control
- `pdc.py` - park distance
- Each module knows its protocol, address, coding structure, adaptation values

**Vehicle Profiles** (in `vehicles/`):
- `e39.json` - modules, coding options, known issues
- `e46.json`
- `e87.json`
- `e90.json`
- Future: E60, E92, F30, G20, etc.

Each profile defines:
- Which modules exist
- Default addresses
- Coding examples
- Maintenance intervals
- Known fault patterns
- RAM/ROM addresses (for reverse engineering)

### 12. Documentation (Auto-Generated)

- Protocol specifications (DS2, KWP2000, UDS)
- Module API reference
- Discovered parameters (from reverse engineering)
- Coding options library
- Safety model explanation
- Backup format specification
- Plugin development guide

Use docstrings → auto-generate markdown.

## Phased Implementation

### Phase 1: Transaction Layer (Foundation)
- Implement `TransactionManager` with read → backup → write → verify → rollback
- VIN-based backup directory structure
- Metadata format
- Version tracking
- Verification logic
- Automatic rollback on failure

**This must be built first** - everything else depends on it.

### Phase 2: Replay & Analysis
- Replay recorded CSV files with synchronized graphs
- Event markers on timeline
- Jump to pulls, knock events, health warnings
- Comparison: overlay two recordings, auto-diff
- Export findings as markdown report

Builds on existing CSV recording + event system.

### Phase 3: Coding (Read-Only First)
- Read coding strings from modules (start with E39 IKE, LCM)
- Decode into human-readable format
- Diff viewer (current vs. factory)
- Version history viewer
- Document coding options (US blinkers, comfort blink, etc.)

**No writes yet** - establish read/decode infrastructure first.

### Phase 4: Coding (Write with Safety)
- Integrate with transaction layer
- Write coding with automatic backup + verify
- Rollback on failure
- Test on sacrificial E39 LCM first (light module is low-risk)

### Phase 5: Adaptations & Service Resets
- Read adaptation values
- Reset functions (throttle, fuel trims, transmission, etc.)
- Via transaction layer (backup + verify)
- Battery registration (critical for E39/E46)

### Phase 6: Reverse Engineering Tools
- RAM explorer with live watch
- Memory dump diff viewer
- Correlation engine (throttle vs. address changes)
- Unknown parameter discovery
- Export as RomRaider logger XML

### Phase 7: Actuator Tests & Maintenance
- Safe actuator test framework (explicit user action)
- Maintenance service functions (oil, inspection, etc.)
- Via transaction layer

### Phase 8: Developer Mode
- Raw protocol console
- Manual memory operations (with warnings)
- Packet recorder
- Firmware helpers

### Phase 9: Multi-Vehicle Support
- Vehicle profiles (E46, E90, etc.)
- Protocol plugins (UDS for newer cars)
- Module library expansion

### Phase 10: Polish & Documentation
- UI refinements
- Auto-generated docs
- Plugin development guide
- Safety model explanation
- Deployment packaging

## Current State (2026-07-04)

**Diagnostics** (Fully operational):
- ✅ DS2 protocol (E39 1998 523i)
- ✅ KWP2000 protocol (E87 2005 116i)
- ✅ Web UI (diag_ui.py + ui.html) on port 8039
- ✅ Module scan with idents
- ✅ Read faults with English text (ms41_dtc.json, e39_body_dtc_en.json, e87_dtc.json)
- ✅ Clear faults with automatic snapshot to fault_snapshots.log
- ✅ MS41 fast logger with 5 profiles (driveability, fuel, knock, sensors, vanos)
- ✅ Live data via SSE at ~10 Hz
- ✅ Health monitoring (8 subsystems: gear, charging, coolant, IAT, fuel trim, MAF, VANOS, knock)
- ✅ Gear estimation with user calibration wizard
- ✅ CSV recording with queue-based writer (non-blocking)
- ✅ Event system (pull_start, pull_end, profile_change with JSON event_data)
- ✅ Replay mode with synchronized graphs, event markers, scrubbing
- ✅ Raw K-line logging (kline_raw.log)
- ✅ Adapter recovery (USB reset on wedged FTDI driver)
- ✅ macOS-specific serial port handling (raw termios, IOSSIOSPEED ioctl for 10400 baud)

**Transaction Layer** (Production-ready):
- ✅ `TransactionManager` with read → backup → write → verify → rollback
- ✅ VIN-based backup directory structure (`backups/{VIN}/{timestamp}_{operation}/`)
- ✅ Metadata with decoded data, verification status, user notes
- ✅ SHA256 hashing for integrity verification
- ✅ Automatic backup before every write operation
- ✅ Verification by read-back comparison
- ✅ Backup history viewer with restore capability
- ✅ Module-specific data files (JSON with raw_hex + decoded structure)

**Coding System** (Complete for E39):
- ✅ Module decoders for 4 E39 modules:
  - **IKE (0x80)**: Instrument cluster - vehicle type, units, language, display options
  - **LCM (0xD0)**: Light control - market, lighting options, headlight type, fade options
  - **GM (0x00)**: General module - central locking, comfort functions
  - **IHKA (0x5B)**: Climate control - temp units, recirculation, rest function
- ✅ **34 one-click presets** across all modules:
  - IKE: 6 presets (digital speed, date/time formats)
  - LCM: 10 presets (US signals, comfort blink, DRL, welcome/follow-me-home lights)
  - GM: 10 presets (auto lock, selective unlock, comfort close, crash unlock, mirror fold)
  - IHKA: 8 presets (temp units, auto recirc, rest function, comfort/economy modes)
- ✅ **Preview system**: Shows exact changes before applying (field-by-field diff)
- ✅ **Manual editor**: Interactive bit toggles for expert users
- ✅ **Restore capability**: Restore from any backup with confirmation
- ✅ **Full audit trail**: Every change backed up with before/after decoded data
- ✅ API endpoints:
  - `GET /api/coding?addr=0x80` - read and decode module coding
  - `GET /api/coding/presets?addr=0x80` - list available presets
  - `GET /api/coding/preview?addr=0x80&preset_id=X` - preview changes
  - `POST /api/coding/apply` - apply preset (transaction layer)
  - `POST /api/coding/write` - manual coding write (transaction layer)
  - `POST /api/coding/restore` - restore from backup (transaction layer)
- ✅ Demo mode for testing without car connection

**Coding Implementation Details**:

The coding system has three access levels:

1. **Presets** (safest): One-click changes for common modifications
   - User clicks preset button
   - System shows preview of exact changes
   - User confirms → transaction layer creates backup → writes → verifies
   - Example: "Enable US Turn Signals (Amber)" changes bit 4 of LCM byte 1

2. **Preview**: See what will change before applying
   - Fetches current coding
   - Applies preset/modification in memory
   - Shows field-by-field diff (before → after)
   - No write until user confirms

3. **Manual Editor** (expert mode): Interactive bit-level editing
   - Enable "Manual Edit Mode" checkbox
   - Click any bit value to toggle (UI updates in real-time)
   - Raw hex display updates as bits change
   - Apply button writes via transaction layer
   - Full backup + verify + rollback protection

**Coding Structure** (per module):

```python
IKE_CODING_MAP = {
    "byte_0": {
        "name": "Vehicle Type",
        "type": "enum",
        "values": {0x00: "Sedan", 0x01: "Touring (Wagon)", ...}
    },
    "byte_1": {
        "name": "Units",
        "type": "bitfield",
        "bits": {
            0: {"name": "Speed unit", "values": {0: "km/h", 1: "mph"}},
            1: {"name": "Temp unit", "values": {0: "°C", 1: "°F"}},
            ...
        }
    },
    ...
}
```

Decoder converts raw bytes → human-readable structure:
- Enums: Single-value fields (e.g., country, language)
- Bitfields: Multiple boolean/choice options per byte

**Transaction Flow for Coding Changes**:

```
User clicks preset "Enable US Turn Signals"
  ↓
Preview API shows: "US turn signals: EU (red) → US (amber)"
  ↓
User confirms
  ↓
Transaction Manager:
  1. Read current coding: 01 3C 02 03
  2. Create backup: backups/{VIN}/20260704_123456_coding_preset_enable_us_signals/
     - LCM.json: {"raw_hex": "013C0203", "decoded": {...}}
     - metadata.json: {operation, timestamp, user_note, verification: pending}
  3. Apply preset: bit 4 of byte 1: 0 → 1
  4. Write new coding: 01 4C 02 03
  5. Verify: read back and compare
  6. Update metadata: {"verified": true}
  ↓
User sees: "✓ Preset applied successfully! Backup saved to: ..."
```

**Backup History UI**:
- Shows all operations for current VIN
- Click backup → view full details (raw hex + decoded data)
- "Compare vs. Current" button for fault operations
- "Restore This Coding" button for coding operations (with confirmation)
- Restore creates new backup of current state before restoring old

**Safety Guarantees**:
- ❌ **Cannot write without reading first** - transaction layer enforces this
- ❌ **Cannot skip backup** - automatic before every write
- ❌ **Cannot skip verification** - read-back comparison mandatory
- ❌ **Cannot lose data** - every backup has full decoded state
- ✅ **Can restore any previous state** - full history with human-readable data
- ✅ **Can audit all changes** - timestamps, user notes, before/after diffs

**Next Steps**:
1. Add more E39 modules (ABS/ASC, EWS, SZM, etc.)
2. Add E87 coding support (KWP2000 coding services)
3. Add coding validation (warn about incompatible combinations)
4. Add coding templates ("US market setup", "EU with comfort features", etc.)
5. Test on real E39 hardware (currently demo mode only)

## Development Roadmap

See **[ROADMAP.md](ROADMAP.md)** for the complete 12-phase development plan.

**Summary**:
- Phase 1-4: Core features (Dashboard, Adaptations, Actuators, Maintenance) - ~13 days
- Phase 5-6: Advanced features (Snapshots, Comparison) - ~7 days  
- Phase 7-8: Power user tools (Reverse Eng, Developer Mode) - ~11 days
- Phase 9-11: Extensibility (Plugins, Multi-vehicle, Docs) - ~22 days
- Phase 12: Polish - ~7 days

**Total: ~67 development days (3-4 months full-time)**

**Current completion: ~25%** (Transaction layer, Coding, Diagnostics complete)

## Success Metrics

- **Safety**: Zero reports of bricked modules due to failed writes
- **Recoverability**: Every write can be rolled back to any previous version
- **Extensibility**: New modules/protocols added without touching transaction layer
- **Documentation**: Every discovered parameter documented with confidence level
- **Community**: Other BMW enthusiasts contribute vehicle profiles, coding examples, discoveries

## Non-Goals

- **Not a flash tool** (yet) - focus on diagnostics, coding, adaptations first
- **Not a replacement for BMW factory tools** - but should be safer and more transparent
- **Not trying to support every car brand** - BMW-specific expertise is the value

## Philosophy

BMW diagnostic tools have traditionally been:
- Expensive (ISTA/D license)
- Opaque (proprietary protocols, no source)
- Risky (wrong coding can brick modules)
- Windows-only
- Fragmented (INPA for diagnostics, NCS for coding, Tool32 for low-level, etc.)

This platform should be:
- Free and open source
- Transparent (every operation explained, documented)
- Safe (automatic backups, verification, rollback)
- Cross-platform (web UI works everywhere)
- Unified (one tool for everything)

The goal is to **democratize BMW diagnostics** while being **safer than the factory tools**.
