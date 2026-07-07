# DS2 Adaptation Services — Research (Phase 2, Task 2.1)

Reference for implementing adaptation resets on the E39 (DS2). Research
only — no code changes. Sources: BMW SGBD job docs
(github.com/emdzej/ediabasx-docs-sgbd, files `MS410DS0/MS411DS1/MS411DS2`
for the DME, plus per-module docs) and RomRaider's DS2 implementation
(`DS2Protocol.java`, `DS2ResetPanel.java`, `DS2ResetPanel.properties`).

## What "adaptation reset" means here

Adaptations are learned values the ECU stores in EEPROM (idle actuator
position, lambda/fuel long-term trims, throttle closed-position, knock
retard history, etc.). Resetting them clears the learned offsets so the
ECU re-learns from defaults — the standard fix after cleaning a throttle
body, replacing sensors, or chasing drift. This is a **write/erase to the
module**, so per the safety rules it MUST go through `transaction.py`
(read adaptations → backup → erase → verify).

## DS2 command reference (verified from RomRaider)

DS2 frame is the usual `[addr, total_len, data..., XOR]`, positive reply
status `0xA0`. The relevant DME commands:

| Command bytes | Meaning | Notes |
|---|---|---|
| `0B 91` | read Lambda adaptations (group) | read-only, safe, good for before/after |
| `0B 92` | read Other adaptations (group) | read-only |
| `0B 93` | read Timing correction / fuel compensation | read-only |
| `0B 01` / `0B 00` | set address list / read (our live logger) | read-only |
| `04` | **clear fault memory** | already implemented |
| **`0C xx yy`** | **selective adaptation erase** | write — see below |

### The selective-erase command (`ADAP_SELEKTIV_LOESCHEN`)

The SGBD job `ADAP_SELEKTIV_LOESCHEN` takes two selection bytes
(`AUSWAHLBYTE_1`, `AUSWAHLBYTE_2`) — a 16-bit mask of which adaptation
groups to erase. RomRaider drives exactly this via its DS2 reset panel;
the bit→group mapping (from `DS2ResetPanel.java` + `.properties`):

| Bit (mask) | Adaptation group | Relevant to our M52? |
|---|---|---|
| 0x0100 | Knock adaptations | yes |
| 0x0200 | Idle speed adaptations | yes |
| 0x0400 | Lambda adaptations | yes |
| 0x0800 | Throttle adaptations | yes (Task 2.2) |
| 0x1000 | Altitude correction | yes |
| 0x2000 / 0x4000 / 0x8000 | Undefined | ignored by ECU |
| 0x0001 | Undefined | ignored |
| 0x0002 | External load history | M3/S52 only |
| 0x0004 / 0x0008 | Undefined (MS43 only) | not MS41 |

Unsupported bits are silently ignored by the ECU (per RomRaider's UI
tooltip), so an out-of-range selection is safe but pointless.

**Byte order / exact opcode is NOT yet wire-confirmed.** RomRaider maps
these through EDIABAS job names, and the raw DS2 opcode that carries the
two selection bytes is most likely `0C` but this must be **captured from a
real INPA/EDIABAS `ADAP_SELEKTIV_LOESCHEN` trace or tested on the demo
adapter before ever sending it to the car.** There is also a blanket
`ADAPT_LOESCHEN` (no args = erase all adaptations) in the same SGBD.
Following the same policy we used for the SIA reset and VANOS actuator
test: **do not guess-send write opcodes to the car.** Confirm first.

## Per-module availability (from SGBD job lists)

| Module | Addr | Adaptation jobs present |
|---|---|---|
| DME MS41 | 0x12 | `ADAPT_LOESCHEN`, `ADAP_SELEKTIV_LOESCHEN`, `STATUS_GEBERRAD_ADAPTION` (reluctor-wheel adaptation status, DS1/DS2 firmware only) |
| ABS5 | 0x56 | no adaptation-erase job; has `DOWNLOAD_FS_RESET` / `TEST_FS_SCHREIBEN` (fault-memory reset only) |
| EGS | 0x32 | **not fitted — this car is a manual**, no transmission adaptations |
| IKE | 0x80 | `SIA_RESET` (service interval; command byte still unknown — see CLAUDE.md) |
| EWS/IHKA/LCM/PDC | — | no adaptation-erase jobs in their SGBDs |

Note the E39 M52 (non-TU) DME is the MS41.0 family (firmware 1429861).
`STATUS_GEBERRAD_ADAPTION` appears in the MS41.1 (`DS1`) doc but should be
probed for presence on our firmware before relying on it.

## Recommended path for Task 2.2 (throttle reset)

1. Add read-only group reads (`0B 91/92/93`) to `ds2_diag.py` first — these
   are safe and give the before/after evidence the transaction layer needs.
2. Implement the erase as a `write_fn` that sends the selective-erase
   command with mask `0x0800` (throttle only), wired through
   `transaction.py` (read group → backup → erase → re-read → verify the
   learned values returned to default).
3. **Gate the actual erase opcode behind a confirmed trace.** Until the
   raw `ADAP_SELEKTIV_LOESCHEN` telegram is captured, expose it in demo
   mode only.
4. Verify: after erase, idle should briefly hunt while re-learning — a good
   functional confirmation.

## Open questions for the user / next agent

- Do we have access to an INPA/EDIABAS install to capture one
  `ADAP_SELEKTIV_LOESCHEN` trace? That single capture removes all the
  guesswork on the opcode/byte order.
- Confirm the car is manual (EGS absent) so we can drop transmission
  adaptations from the Phase-2 scope.
