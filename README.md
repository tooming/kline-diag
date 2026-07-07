# OpenDiag

K-line diagnostics for older BMWs (E39 / E87) using a cheap **K+DCAN USB
cable** — no INPA, no Windows VM, no ELM327. An open, hackable alternative
to ISTA/INPA/NCS for pre-CAN diagnostics.

Talks raw ISO 14230 / KWP2000 (E87) and DS2 (E39) on the K-line (OBD pin 7),
straight through the FTDI serial port. Reads and clears fault memory in
every module (including airbag), reads per-fault environment data
(voltage/odometer at the moment a fault stored), live-logs engine data, and
serves a real-time web dashboard.

> **Downloads:** prebuilt Mac and Windows apps will be published under
> [Releases](../../releases). For now, run from source (below).

Built and verified live on real cars while diagnosing electrical and
driveability faults — see [Case history](#case-history).

## Hardware

- **K+DCAN cable** (FTDI FT232 based, USB product name "D-CAN"). These are
  the ~€15 "INPA cables". An ELM327 will *not* work with this tool, and
  ELM327 apps will not work with this cable.
- Pre-03/2007 E8x/E9x expose **all modules on the K-line**, so this whole
  toolkit works on those cars. Later cars moved to D-CAN (different wiring,
  not supported here).
- Ignition must be ON (position 2). Engine running is fine.

## Requirements

- macOS (uses Apple's built-in FTDI driver — nothing to install)
- Python 3 — **standard library only** for all core functions
- Optional, for automatic USB recovery of a wedged adapter:
  `brew install libusb` and `pip install pyusb`

## Quick start

```sh
# is the cable + car talking? which OBD PIDs exist?
python3 power_diag.py pids

# read fault codes from every module
python3 power_diag.py scan

# live battery voltage + RPM at ~8 Hz, logged to CSV, Ctrl+C to stop
python3 power_diag.py monitor
```

## Modes

| Command | What it does |
|---|---|
| `scan` | Fast-init all known modules, read + decode stored DTCs |
| `sweep` | Try every address 0x00–0xE8 (finds modules on unknown cars) |
| `dtc <addr>` | DTCs from one module (hex address, e.g. `dtc 01`) |
| `detail <addr>` | DTCs **plus per-fault environment data** (service 0x17): recorded voltage, occurrence counters |
| `clear <addr...>` | Clear fault memory and re-read to verify (e.g. `clear 00 01 29`) |
| `monitor` | Continuous voltage + RPM → console + CSV. Warns on <12.5 V while running, >15.0 V, ECU comm loss, USB dropout. Auto-recovers from all of them. |
| `probe-voltage` | Scan KWP local-identifier records for voltage-like values (how `21 5A` was found) |
| `pids` | Show which OBD Mode-01 PIDs the DME supports |

Global flags: `--raw` prints every frame on the wire; all traffic is always
appended to `kline_raw.log`. `--port` overrides the device path.

`monitor` extras: `--duration N` (seconds, default: until Ctrl+C),
`--interval`, `--local-id/--offset/--scale` to use a different KWP record
as the voltage source.

## Module map (verified on this car)

| Addr | Module |
|---|---|
| 0x00 | JBE/SPEG — junction box / power distribution |
| 0x01 | MRS — airbag / restraints (not 0xA4 like older BMWs) |
| 0x12 | DME — engine |
| 0x29 | DSC — stability control / ABS |
| 0x40 | CAS — car access system |
| 0x60 | KOMBI — instrument cluster (refuses init but answers requests; handled automatically) |
| 0x63 | steering column module |
| 0x64 | PDC — park distance control |
| 0x72 | LM — light module |
| 0x78 | IHKA — climate control |

Addresses 0xE9–0xEF are aliases of other modules and are excluded from scans.

## Car-specific notes

- **Battery voltage**: this 2005 DME does not support OBD PID 0x42. The
  equivalent is KWP `readDataByLocalIdentifier` record `21 5A` on the DME —
  byte 0 × 0.1 V. `monitor` uses it automatically.
- **DTC decoding**: DME codes are shown with a P-code style rendering, but
  BMW codes are internal hex — look them up as BMW codes (e.g. `2C55`), not
  SAE codes. Body module codes (93xx, A0xx, A6xx, 9Cxx…) are BMW-only.
- **Healthy charging** on this car: steady 14.4–14.9 V at idle. A spread of
  more than ~0.5 V at constant RPM means a battery/connection/regulator
  problem (see case history).

## Troubleshooting

- **`pids`/`scan` silent, and `--raw` shows no echo of transmitted bytes**:
  the K-line has no power — ignition off, or the car's 12 V supply to the
  OBD socket is dead. (The cable echoes everything you send when the bus is
  powered; no echo = no bus.)
- **Port won't open (`EINVAL`) or errno 83**: the macOS FTDI driver wedges
  after the adapter drops off USB. The tool resets it automatically if
  pyusb+libusb are installed; otherwise unplug/replug the cable.
- **KOMBI "refused init"**: normal, it answers anyway.
- **`7F xx 78` in raw output**: "response pending" — handled, not an error.

## Bonus: DS2 support for pre-2001 BMWs (`ds2_diag.py`)

Older BMWs (E39/E38/E36 era) don't speak KWP2000 — they use **DS2**
(9600 baud 8E1, XOR-checksummed frames). `ds2_diag.py` covers them with the
same transport:

```sh
python3 ds2_diag.py scan          # ident + fault memory of known E39 ECUs
python3 ds2_diag.py sweep         # probe all 256 addresses
python3 ds2_diag.py live          # stream DME + cluster status blocks
python3 ds2_diag.py faults 56     # one ECU's fault memory (hex addr)
python3 ds2_diag.py clear 56 --yes
```

Verified on a 1998 523i (M52, MS41): DME 0x12, EWS 0x44, ABS 0x56,
IHKA 0x5B, PDC 0x60, RADIO 0x68, IKE cluster 0x80, LCM 0xD0 all respond
through the OBD socket. 0xBF/0xFF are broadcast addresses. The airbag
(MRS) is only on the round 20-pin engine-bay connector on cars this old.

Fault codes are decoded to text: the DME via `ms41_dtc.json` (OpenMS41)
and the body modules via `e39_body_dtc_en.json` — fault location + fault
type tables for EWS3, ABS5, cluster, IHKA, LCM, PDC and FBZV, extracted
from openly published BMW SGBD job documentation
(github.com/emdzej/ediabasx-docs-sgbd) and translated to English (BMW's
original German texts are kept in the same file under `ort_de`/`art_de`);
the raw bytes are always shown alongside.

## Web dashboard (`diag_ui.py`)

A real-time browser UI covering both cars — fault viewing/clearing and live
graphs:

```sh
python3 diag_ui.py        # then open http://localhost:8039
```

- Auto-detects the connected car (DS2 for the E39, KWP2000 for the E87);
  manual protocol override in the header.
- **Modules panel**: scan, per-module fault list with decoded texts where
  tables exist, re-read and clear buttons. Every clear saves a snapshot of
  the memory to `fault_snapshots.log` first and re-reads afterwards.
- **Live data**: on the E39, 17 MS41 engine parameters (RPM, TPS, load,
  MAF, injection time, fuel trims, ignition advance, knock retard, VANOS,
  temps, voltages) at ~9 Hz via the DS2 address-list mechanism
  (`0B 01` arm / `0B 00` read, addresses from `ms41_ram_params.json`,
  extracted from the RomRaider MS41 logger definition for ECU 1429861).
  Grouped gauge tiles; click any tile to add its strip chart.
- **Drive recording**: ⏺ button streams every sample to
  `drive_log_*.csv` for post-drive analysis (throttle-blip/bog-down
  debugging).
- **Service**: oil-service (SIA) reset button — experimental; the cluster
  rejected the reconstructed command byte, manual odometer-button reset
  documented in the UI as fallback.
- **Raw K-line traffic** pane mirrors every frame for protocol debugging.
- Stdlib only, same as the rest; the server is the single owner of the
  serial port, so close it before running the CLI tools.

## Desktop app (`desktop_app.py`)

An optional native-window wrapper so the dashboard launches like a normal
Mac app instead of "run a server, open a browser". It uses **pywebview**
(the OS's built-in WebKit — no Chromium bundled) and spawns `diag_ui.py`
as a child process, so the core stays stdlib-only.

```sh
# macOS: just double-click "BMW Diagnostics.command" in Finder
#        (first run auto-creates .venv and installs pywebview)

# or from a shell:
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python desktop_app.py
```

- Opens the full dashboard in a titled 1280×860 window.
- Reuses an already-running server on port 8039 if one is up; otherwise
  starts one with `--no-connect` (connect to the car from the header).
- Closing the window terminates the spawned server.
- Only this wrapper needs a dependency; `power_diag.py`, `ds2_diag.py` and
  `diag_ui.py` still run with bare `python3`.

### Native `.app` bundle

For a real double-clickable app (icon in Finder/Applications, no Terminal
window):

```sh
python3 build_app.py            # builds ./BMW Diagnostics.app
open "BMW Diagnostics.app"      # or double-click it; drag to /Applications
```

The bundle is a thin launcher — its executable runs `desktop_app.py`
through the project's `.venv`, so the real source files run in place and
every `__file__`-relative path (ui.html, the *.json tables) just works.
The project path is baked in at build time, so it keeps working after you
move the app to `/Applications`; rebuild if you move the *project*. The
icon is generated by `build_app.py` (a gauge dial, pure-stdlib PNG →
`sips`/`iconutil`).

> This is a **launcher** bundle — it depends on this project folder + its
> `.venv` staying put, so it's for personal use on one Mac. For a
> self-contained app you can hand to someone else, use the frozen build
> below.

## Distributable apps (frozen)

Prebuilt, self-contained **Windows `.exe`** and **macOS `.app`** are
published on the [Releases](../../releases) page — no Python needed. They're
built from source by GitHub Actions ([`.github/workflows/build.yml`](.github/workflows/build.yml))
on every version tag. To build one yourself:

```sh
pip install pyinstaller pywebview pyserial segno
pyinstaller --noconfirm kline-diag.spec   # -> dist/OpenDiag.app (mac) or .exe (win)
```

The frozen app finds its bundled `ui.html`/JSON tables inside the bundle and
writes logs/backups to a per-user folder (`%APPDATA%\BMWDiag` on Windows,
`~/Library/Application Support/BMWDiag` on macOS) — see [`paths.py`](paths.py).

> The builds aren't code-signed yet, so the OS shows an "unidentified
> developer" warning (macOS: right-click → Open; Windows: SmartScreen → Run
> anyway). See the Release notes.

## Files

- `power_diag.py` — the toolkit (self-contained)
- `ds2_diag.py` — DS2 protocol tool for pre-2001 BMWs (imports power_diag)
- `diag_ui.py` + `ui.html` — web dashboard on top of both
- `desktop_app.py` + `requirements-desktop.txt` + `BMW Diagnostics.command`
  — optional native-window wrapper (pywebview)
- `build_app.py` — builds the `BMW Diagnostics.app` bundle (launcher + icon)
- `ms41_dtc.json`, `e87_dtc.json`, `e39_body_dtc_en.json` — fault-code text
  tables
- `ms41_ram_params.json`, `ms43_ram_params.json` — live-data parameter maps
- `transaction.py`, `coding.py` — read→backup→write→verify→rollback layer

Generated at runtime (git-ignored, kept out of the repo): `kline_raw.log`
(every frame), `fault_snapshots.log` (pre-clear snapshots), `backups/`
(per-VIN module backups), and the `*_log_*.csv` recordings.

## Case history

July 2026: after a flat battery and jump start, the car had momentary total
power losses at idle, clock resets, flickering headlights, and airbag +
seatbelt lights. Generic OBD showed nothing. This toolkit found undervoltage
/ power-supply codes in seven modules, recorded brownout voltages of
9.7–11.8 V in the fault environment data, and live-measured charging
instability of 13.5–15.9 V at idle. **Root cause: a loose negative battery
terminal.** After tightening: 14.4–14.9 V steady, all faults cleared, all
lamps out. Note: the car runs a 3 Ω resistor in place of the BST pyro
element (MRS accepts it; the crash battery-disconnect function is absent).
