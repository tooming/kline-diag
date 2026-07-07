# BMW Diagnostic Platform - Development Roadmap

## Vision
A modern, open-source BMW diagnostic workstation combining ISTA/INPA/NCS Expert/Tool32 capabilities with a web UI and automatic safety guarantees.

## Current State (2026-07-04)

### ✅ Fully Operational
- **Transaction Layer**: Read → Backup → Write → Verify → Rollback
- **VIN-based Backups**: Complete history with metadata
- **Coding System**: 4 modules (IKE, LCM, GM, IHKA) with 34 presets
- **Diagnostics**: Scan, faults, live data, health engine, recording, replay
- **Protocols**: DS2 (E39), KWP2000 (E87)
- **Web UI**: Port 8039, SSE live graphs
- **Safety**: All writes go through transaction layer

### 🚧 Partially Implemented
- **Dashboard**: Has health/faults, missing full vehicle overview
- **Replay**: Works, but no comparison overlay yet
- **Backup System**: Per-operation, not full vehicle snapshots
- **Developer Mode**: Raw logging exists, not formalized UI section

### ❌ Not Yet Implemented
- **Adaptations**: Reset functions (throttle, fuel trims, transmission, etc.)
- **Actuator Tests**: None implemented
- **Maintenance Functions**: Oil service, battery registration, etc.
- **Reverse Engineering Tools**: RAM explorer, correlation engine, etc.
- **Analysis/Comparison**: Overlay two recordings
- **Plugin Architecture**: Modular but not formal plugins
- **Vehicle Profiles**: Hardcoded, need E46/E90/etc.
- **Safety Levels UI**: No color-coded safety indicators
- **Documentation Generation**: Manual only

---

## Phase 1: Complete Dashboard ⏱️ 2-3 days

### Goals
Unified vehicle overview as landing page.

### Tasks
- [ ] **Vehicle Info Card**
  - VIN (read from IKE/EWS)
  - Model/year detection
  - Engine type (from DME ident)
  - Transmission type
  - Mileage (from IKE)
- [ ] **ECU Grid**
  - Detected modules with addresses
  - Part numbers
  - Software versions
  - Last scanned timestamp
  - Click → jump to module diagnostics
- [ ] **Quick Status Panel**
  - Battery voltage (live)
  - Current gear (live)
  - Coolant temp (live)
  - Total fault count across all modules
- [ ] **Health Summary**
  - 8 subsystem tiles (already have data)
  - Click → details/graphs
- [ ] **Quick Actions**
  - Scan All Modules
  - Clear All Faults
  - Create Snapshot
  - Start Recording

### API Endpoints Needed
- `GET /api/vehicle` - VIN, model, mileage
- `GET /api/modules/summary` - all detected ECUs with versions

---

## Phase 2: Adaptations ⏱️ 3-4 days

### Goals
Reset learned values with transaction layer safety.

### Modules to Support
1. **DME (Engine)**
   - Throttle adaptation reset
   - Fuel trim reset (LTFT, STFT)
   - Idle adaptation reset
   - Lambda sensor aging reset
   - VANOS adaptation reset
   - Knock sensor adaptation
2. **EGS (Transmission)**
   - Shift adaptation reset
   - Clutch adaptation reset (SMG)
3. **ABS/DSC**
   - Steering angle calibration
   - Wheel speed sensor adaptation
4. **IKE (Cluster)**
   - Reset service indicators

### Implementation
```python
# Example: Throttle adaptation reset
def reset_throttle_adaptation():
    tm = get_transaction_manager()
    result = tm.execute(
        vin=VIN,
        module_name="DME",
        module_addr=0x12,
        operation="adaptation_reset_throttle",
        read_fn=lambda: read_throttle_adaptation(),
        write_fn=lambda: write_throttle_defaults(),
        verify_fn=lambda: verify_throttle_reset(),
        user_note="User requested throttle reset"
    )
```

### UI
- New "Adaptations" section
- List available resets per module
- Show current vs. default values
- Confirmation modal with explanation
- Success → show before/after

### API Endpoints
- `GET /api/adaptations?module=DME` - list available resets
- `GET /api/adaptations/read?module=DME&type=throttle` - read current
- `POST /api/adaptations/reset` - perform reset via transaction layer

---

## Phase 3: Actuator Tests ⏱️ 2-3 days

### Goals
Safely trigger outputs for testing.

### Safety Model
- Read-only by default
- Actuator tests require explicit user action
- Display warning before activating
- Timeout after N seconds
- Emergency stop button

### Actuators to Support
1. **DME**
   - Fuel pump relay
   - Cooling fan
   - VANOS solenoid
   - Individual injectors (pulse test)
   - Individual coils (spark test)
   - Idle valve
2. **LCM**
   - All lights individually
   - Fog lights
   - High beams
   - Turn signals
3. **GM**
   - Door locks
   - Window motors
   - Mirror fold
   - Trunk release
4. **ABS**
   - ABS pump (brief pulse only)
   - Valve test

### Implementation
```python
def test_actuator(module, actuator, duration_ms):
    # No transaction layer - this is read-only test
    # Just send activation command and return result
    result = send_activation(module, actuator, duration_ms)
    return result
```

### UI
- New "Actuator Tests" section
- Group by module
- Each actuator: button with warning
- Click → confirmation modal
- Active indicator while running
- Emergency stop always visible

### API Endpoints
- `GET /api/actuators` - list available tests
- `POST /api/actuators/activate` - trigger actuator
- `POST /api/actuators/stop` - emergency stop

---

## Phase 4: Maintenance Functions ⏱️ 2-3 days

### Goals
Service reset functions with transaction layer.

### Functions to Implement
1. **Oil Service Reset** (IKE)
   - Read current interval
   - Reset to factory
   - Verify reset
2. **Inspection Reset** (IKE)
   - Inspection I, II, III
3. **Battery Registration** (DME/LCM)
   - Critical for charging profile
   - Record battery type, capacity, manufacture date
4. **Brake Service Reset** (ABS/DSC)
   - Reset brake pad wear counter
5. **Steering Angle Calibration** (ABS/DSC)
   - After wheel alignment
6. **DPF Regeneration** (DME on diesel)
   - Force regeneration cycle

### Implementation
All go through transaction layer:
```python
result = tm.execute(
    operation="oil_service_reset",
    read_fn=lambda: read_service_interval(),
    write_fn=lambda: write_factory_interval(),
    verify_fn=lambda: verify_interval_reset()
)
```

### UI
- New "Maintenance" section
- List available functions per module
- Show current status (days/km until service)
- Confirmation with explanation
- Success → show new status

### API Endpoints
- `GET /api/maintenance` - list available functions
- `GET /api/maintenance/status?function=oil_service` - current status
- `POST /api/maintenance/reset` - perform reset via transaction

---

## Phase 5: Snapshot System ⏱️ 2-3 days

### Goals
Complete vehicle snapshots, not just per-operation backups.

### Features
- **Create Snapshot**
  - Read all detected modules
  - Save all coding, adaptations, idents
  - Store as single timestamped snapshot
- **Snapshot Browser**
  - List all snapshots for VIN
  - Show what changed between snapshots
  - Drill down into individual modules
- **Restore Options**
  - Restore entire vehicle
  - Restore single module
  - Restore specific data (coding only, adaptations only)

### Directory Structure
```
backups/
  WBAXXXXXXXXXXXXXX/
    snapshots/
      20260704_120000_factory/
        metadata.json
        modules/
          DME_0x12.json
          LCM_0xD0.json
          IKE_0x80.json
          ...
    operations/
      20260704_123456_coding_preset_us_blinkers/
        ...
```

### Metadata Format
```json
{
  "type": "snapshot",
  "vin": "WBAXXXXXXXXXXXXXX",
  "timestamp": "2026-07-04T12:00:00",
  "description": "Factory baseline before modifications",
  "mileage_km": 287453,
  "modules": {
    "DME": {
      "addr": 18,
      "part_number": "...",
      "sw_version": "...",
      "coding": {...},
      "adaptations": {...},
      "ident": "..."
    },
    ...
  }
}
```

### UI
- "Create Snapshot" button on dashboard
- Snapshot browser in Backups section
- Diff viewer for snapshot comparison
- Restore wizard with confirmation

### API Endpoints
- `POST /api/snapshot/create` - create full snapshot
- `GET /api/snapshots` - list all snapshots
- `GET /api/snapshot/{id}` - get snapshot details
- `POST /api/snapshot/restore` - restore snapshot

---

## Phase 6: Comparison & Analysis ⏱️ 3-4 days

### Goals
Overlay two recordings, auto-generate findings.

### Features
- **Recording Comparison**
  - Select two CSV files
  - Overlay graphs (different colors)
  - Align by time or by RPM
  - Highlight differences
- **Automatic Findings**
  - "MAF reading improved by 8%"
  - "Fuel trims more stable"
  - "VANOS response faster"
  - "Knock reduced at 4000 RPM"
- **Event Correlation**
  - Show when events occurred in each recording
  - Compare pulls (0-60 times, max torque, etc.)
- **Health Comparison**
  - Before/after health status
  - Which subsystems improved

### Implementation
```python
def compare_recordings(file1, file2):
    data1 = parse_csv(file1)
    data2 = parse_csv(file2)
    
    findings = []
    
    # Compare MAF
    maf1_avg = mean(data1["P12"])
    maf2_avg = mean(data2["P12"])
    if maf2_avg > maf1_avg * 1.05:
        findings.append({
            "type": "improvement",
            "subsystem": "airflow",
            "description": f"MAF reading improved by {(maf2_avg/maf1_avg - 1)*100:.1f}%"
        })
    
    # Compare fuel trims
    # Compare knock
    # Compare VANOS
    # etc.
    
    return findings
```

### UI
- New "Compare" section
- Dropdown: select two recordings
- Sync options (time, RPM)
- Overlay graphs
- Findings panel (auto-generated)
- Export comparison report

### API Endpoints
- `POST /api/compare` - compare two recordings
- `GET /api/compare/findings` - get auto-generated findings

---

## Phase 7: Reverse Engineering Tools ⏱️ 5-7 days

### Goals
Tools for discovering unknown parameters and coding options.

### Features

#### 7.1 RAM Explorer
- **Address Range Viewer**
  - Dump address ranges (0x0000-0xFFFF)
  - Live view mode (update every 100ms)
  - Watch list (monitor specific addresses)
- **Value Search**
  - Search for value (e.g., find addresses containing current RPM)
  - Differential search (value changed/unchanged)
- **Address Annotations**
  - Add notes to discovered addresses
  - Mark confidence level
  - Export as RomRaider XML

#### 7.2 Correlation Engine
- **Auto-Discovery**
  - Record live data + RAM dump simultaneously
  - Correlate throttle position with address changes
  - Correlate RPM with addresses
  - Find unknown sensor addresses
- **Results**
  - List candidate addresses for each parameter
  - Show correlation strength
  - Suggest data type (uint8, uint16, float, etc.)

#### 7.3 Differential Logging
- **Compare Memory Dumps**
  - Capture RAM dump at idle
  - Capture RAM dump at 3000 RPM
  - Highlight changed addresses
  - Group by magnitude of change

#### 7.4 EEPROM Explorer
- **Read EEPROM** (read-only by default)
  - Dump entire EEPROM
  - Show known coding areas
  - Highlight unknown areas
- **Checksum Calculator**
  - Calculate checksums for validation
  - Warn if checksum invalid

### Implementation
```python
def ram_explorer(address, length):
    data = send_read_memory(address, length)
    return data

def correlation_engine(parameter_name, parameter_values, ram_dumps):
    candidates = []
    for addr in range(0x0000, 0xFFFF):
        correlation = correlate(parameter_values, [d[addr] for d in ram_dumps])
        if correlation > 0.9:
            candidates.append({"addr": addr, "correlation": correlation})
    return candidates
```

### UI
- New "Reverse Engineering" section
- RAM Explorer tab
- Correlation Engine tab
- Diff Viewer tab
- EEPROM Explorer tab
- Export buttons (RomRaider XML, JSON, markdown)

### API Endpoints
- `POST /api/ram/read` - read address range
- `POST /api/ram/watch` - start live watch
- `POST /api/ram/correlate` - run correlation
- `POST /api/eeprom/dump` - dump EEPROM

---

## Phase 8: Developer Mode ⏱️ 3-4 days

### Goals
Formalize dangerous operations in separate section with warnings.

### Features
- **Warning Banner** (always visible in Developer Mode)
  - Red background
  - "DEVELOPER MODE - Raw operations can damage modules"
  - Exit Developer Mode button
- **Raw Protocol Consoles**
  - DS2 console (send raw frames)
  - KWP console (send raw services)
  - UDS console (for newer cars)
  - CAN console (send raw frames)
- **Manual Memory Operations**
  - Read memory by address
  - Write memory (with double confirmation)
  - Automatic backup before any write
- **Packet Recorder**
  - Record all bus traffic
  - Filter by module/service
  - Export as PCAP or JSON
- **Firmware Tools**
  - Checksum calculator
  - Binary diff viewer
  - Disassembler helper (show bytes as assembly)

### Safety
- All raw writes require:
  1. Type module name to confirm
  2. Automatic backup
  3. Verification
  4. Manual rollback available

### UI
```html
<div id="developer-mode-warning" style="background:var(--err);padding:16px">
  ⚠️ DEVELOPER MODE ACTIVE - Raw operations can brick modules
  <button>Exit Developer Mode</button>
</div>

<section id="raw-ds2-console">
  <h3>Raw DS2 Console</h3>
  <input placeholder="Frame (hex): 80 03 00 XX">
  <button>Send</button>
  <pre id="response"></pre>
</section>
```

### API Endpoints
- `POST /api/raw/ds2` - send raw DS2 frame
- `POST /api/raw/kwp` - send raw KWP service
- `POST /api/raw/memory/read` - read memory
- `POST /api/raw/memory/write` - write memory (with backup)

---

## Phase 9: Plugin Architecture ⏱️ 7-10 days

### Goals
Modular system for protocols, modules, vehicles.

### Structure
```
bmw_platform/
  core/
    transaction_manager.py
    backup_system.py
    web_server.py
  protocols/
    ds2.py
    kwp2000.py
    uds.py
    can.py
  modules/
    dme.py
    lcm.py
    ike.py
    gm.py
    ihka.py
    ews.py
    abs.py
    egs.py
  vehicles/
    e39.json
    e46.json
    e87.json
    e90.json
  plugins/
    __init__.py
    registry.py
```

### Plugin API
```python
class ModulePlugin:
    def __init__(self):
        self.name = "IKE"
        self.description = "Instrument Cluster"
        self.addresses = [0x80]  # Can vary by vehicle
        self.protocol = "ds2"  # or "kwp2000", "uds"
    
    def read_ident(self):
        pass
    
    def read_faults(self):
        pass
    
    def read_coding(self):
        pass
    
    def write_coding(self, data):
        pass
    
    def get_coding_map(self):
        return IKE_CODING_MAP
    
    def get_presets(self):
        return IKE_PRESETS
```

### Vehicle Profiles
```json
{
  "vehicle": "E39",
  "years": [1996, 2003],
  "protocol": "ds2",
  "modules": [
    {
      "name": "IKE",
      "addr": "0x80",
      "plugin": "ike.IKEPlugin"
    },
    {
      "name": "LCM",
      "addr": "0xD0",
      "plugin": "lcm.LCMPlugin"
    }
  ],
  "coding_examples": [
    {
      "name": "US Market Setup",
      "modules": {
        "IKE": {"preset": "us_units"},
        "LCM": {"preset": "enable_us_signals"}
      }
    }
  ]
}
```

---

## Phase 10: Multi-Vehicle Support ⏱️ 5-7 days per vehicle

### Priority Order
1. **E39** (1996-2003) - already started
2. **E46** (1998-2006) - similar to E39
3. **E87** (2004-2011) - KWP2000, already have protocol
4. **E90** (2005-2012) - KWP2000/UDS hybrid
5. **E60** (2003-2010) - similar to E90
6. **F30** (2012-2019) - full UDS + CAN

### Per-Vehicle Tasks
- [ ] Research module addresses
- [ ] Create vehicle profile JSON
- [ ] Add coding maps for main modules
- [ ] Add common presets
- [ ] Test on real hardware
- [ ] Document common issues
- [ ] Add to UI vehicle selector

---

## Phase 11: Documentation Generation ⏱️ 3-5 days

### Goals
Auto-generate comprehensive documentation.

### Features
- **API Documentation**
  - From docstrings → markdown
  - Include examples
- **Protocol Specifications**
  - DS2 frame format
  - KWP2000 services
  - UDS services
- **Module Documentation**
  - Each module's capabilities
  - Coding options
  - Adaptation options
- **Discovered Parameters**
  - RAM addresses
  - Confidence levels
  - Data types
- **Safety Model**
  - Transaction layer explanation
  - Backup format
  - Restore procedure

### Implementation
```python
def generate_docs():
    # Extract docstrings
    docs = extract_docstrings("bmw_platform/")
    
    # Generate markdown
    generate_api_docs(docs)
    generate_protocol_docs()
    generate_module_docs()
    
    # Export
    write_file("docs/API.md")
    write_file("docs/PROTOCOLS.md")
    write_file("docs/MODULES.md")
```

---

## Phase 12: UI Polish & UX ⏱️ 5-7 days

### Goals
Professional, intuitive interface.

### Tasks
- [ ] **Consistent Design System**
  - Color palette (already have CSS vars)
  - Typography scale
  - Spacing system
  - Component library
- [ ] **Navigation**
  - Sidebar with sections
  - Breadcrumbs
  - Back button
- [ ] **Loading States**
  - Spinners for API calls
  - Skeleton screens
  - Progress indicators
- [ ] **Error Handling**
  - User-friendly error messages
  - Retry buttons
  - Help links
- [ ] **Responsive Design**
  - Works on tablet
  - Mobile view (read-only)
- [ ] **Keyboard Shortcuts**
  - Scan: Ctrl+S
  - Record: Ctrl+R
  - Clear faults: Ctrl+Shift+C
- [ ] **Dark/Light Themes**
  - Toggle in settings
  - Save preference

---

## Success Criteria

### Safety
- ❌ Zero bricked modules due to failed writes
- ✅ 100% of writes backed up automatically
- ✅ 100% of writes verified
- ✅ All dangerous operations require confirmation

### Coverage
- ✅ E39 fully supported (all modules, all coding options)
- ✅ E46/E87 supported (main modules)
- ⏱️ E90/F30 basic support

### Performance
- ✅ Live data at 10 Hz minimum
- ✅ UI responsive (<100ms interactions)
- ✅ Recording never drops samples

### Documentation
- ✅ Every API endpoint documented
- ✅ Every protocol explained
- ✅ Every discovered parameter annotated
- ✅ Safety model explained

### Community
- ⏱️ Open source on GitHub
- ⏱️ Contribution guidelines
- ⏱️ 10+ community contributors
- ⏱️ 100+ vehicles tested

---

## Timeline Estimate

| Phase | Days | Cumulative |
|-------|------|------------|
| 1. Dashboard | 3 | 3 |
| 2. Adaptations | 4 | 7 |
| 3. Actuator Tests | 3 | 10 |
| 4. Maintenance | 3 | 13 |
| 5. Snapshots | 3 | 16 |
| 6. Comparison | 4 | 20 |
| 7. Reverse Eng | 7 | 27 |
| 8. Developer Mode | 4 | 31 |
| 9. Plugin Arch | 10 | 41 |
| 10. E46 Support | 7 | 48 |
| 11. E87 Support | 7 | 55 |
| 12. Documentation | 5 | 60 |
| 13. UI Polish | 7 | 67 |

**Total: ~67 development days (3-4 months full-time)**

---

## Priorities

### Must Have (v1.0)
- ✅ Transaction layer
- ✅ Coding (read/write/restore)
- ✅ Diagnostics
- ✅ Backups
- ⏱️ Adaptations
- ⏱️ Maintenance
- ⏱️ Dashboard

### Should Have (v1.1)
- ⏱️ Snapshots
- ⏱️ Comparison
- ⏱️ Actuator tests
- ⏱️ E46 support

### Nice to Have (v2.0)
- ⏱️ Reverse engineering tools
- ⏱️ Developer mode
- ⏱️ Plugin architecture
- ⏱️ E90 support

---

## Notes

- Every phase builds on transaction layer
- Can parallelize documentation with feature dev
- UI polish is ongoing, not just Phase 12
- Community testing after v1.0
- Real hardware testing required for each vehicle

**Current status: ~25% complete (strong foundation)**
