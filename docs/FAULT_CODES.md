# Fault Code Reference

Auto-generated. Sources: OpenMS41 (DME), BMW SGBD docs (body modules), researched E87 codes.


## 0x44 — EWS (immobiliser)

| Code | Location |
|------|----------|
| 0x00 | Key No.0 invalid due to faulty identification |
| 0x01 | Key No.0 invalid due to faulty password |
| 0x02 | Key No.0 invalid due to faulty rolling code |
| 0x03 | Rolling code tolerance increased for key number 0 |
| 0x0E | DME rolling code XOR error |
| 0x0F | Power-on reset |
| 0x10 | Key No.1 invalid due to faulty identification |
| 0x11 | Key No.1 invalid due to faulty password |
| 0x12 | Key No.1 invalid due to faulty rolling code |
| 0x13 | Rolling code tolerance increased for key number 1 |
| 0x1E | DME rolling code lost |
| 0x1F | Clock monitor reset |
| 0x20 | Key No.2 invalid due to faulty identification |
| 0x21 | Key No.2 invalid due to faulty password |
| 0x22 | Key No.2 invalid due to faulty rolling code |
| 0x23 | Rolling code tolerance increased for key number 2 |
| 0x2F | Watchdog reset |
| 0x30 | Key No.3 invalid due to faulty identification |
| 0x31 | Key No.3 invalid due to faulty password |
| 0x32 | Key No.3 invalid due to faulty rolling code |
| 0x33 | Rolling code tolerance increased for key number 3 |
| 0x3F | Illegal opcode trap |
| 0x40 | Key No.4 invalid due to faulty identification |
| 0x41 | Key No.4 invalid due to faulty password |
| 0x42 | Key No.4 invalid due to faulty rolling code |
| 0x43 | Rolling code tolerance increased for key number 4 |
| 0x50 | Key No.5 invalid due to faulty identification |
| 0x51 | Key No.5 invalid due to faulty password |
| 0x52 | Key No.5 invalid due to faulty rolling code |
| 0x53 | Rolling code tolerance increased for key number 5 |
| 0x60 | Key No.6 invalid due to faulty identification |
| 0x61 | Key No.6 invalid due to faulty password |
| 0x62 | Key No.6 invalid due to faulty rolling code |
| 0x63 | Rolling code tolerance increased for key number 6 |
| 0x70 | Key No.7 invalid due to faulty identification |
| 0x71 | Key No.7 invalid due to faulty password |
| 0x72 | Key No.7 invalid due to faulty rolling code |
| 0x73 | Rolling code tolerance increased for key number 7 |
| 0x7F | Software interrupt |
| 0x80 | Key No.8 invalid due to faulty identification |
| 0x81 | Key No.8 invalid due to faulty password |
| 0x82 | Key No.8 invalid due to faulty rolling code |
| 0x83 | Rolling code tolerance increased for key number 8 |
| 0x90 | Key No.9 invalid due to faulty identification |
| 0x91 | Key No.9 invalid due to faulty password |
| 0x92 | Key No.9 invalid due to faulty rolling code |
| 0x93 | Rolling code tolerance increased for key number 9 |
| 0xFF | General reset |

**Fault types:** 0x00=intermittent fault, 0x01=permanent fault

## 0x56 — ABS/DSC

| Code | Location |
|------|----------|
| 0x04 | Rear left wheel speed sensor |
| 0x05 | Rear right wheel speed sensor |
| 0x06 | Front right wheel speed sensor |
| 0x07 | Front left wheel speed sensor |
| 0x0E | Valve relay fault |
| 0x0F | Return pump fault |
| 0x15 | Control unit fault |
| 0x18 | Wrong toothed wheel on one of the 4 wheels |
| 0x19 | Brake light switch wire break |
| 0x1E | Rear left wheel speed sensor |
| 0x1F | Rear right wheel speed sensor |
| 0x20 | Front right wheel speed sensor |
| 0x21 | Front left wheel speed sensor |
| 0x2F | ABS outlet valve rear left or rear axle |
| 0x30 | ABS outlet valve rear right |
| 0x31 | ABS outlet valve front right |
| 0x32 | ABS outlet valve front left |
| 0x33 | ABS inlet valve rear left or rear axle |
| 0x34 | ABS inlet valve rear right |
| 0x35 | ABS inlet valve front right |
| 0x36 | ABS inlet valve front left |
| 0x3F | Speed comparison fault |
| 0x40 | Continuous regulation / activation |
| 0x42 | Speed sensor supply voltage (active sensors), control unit fault (passive sensors) |

## 0x80 — Instrument cluster (IKE)

| Code | Location |
|------|----------|
| 0x3F | Gauge driver |
| 0x44 | Oil pressure |
| 0x83 | Speedometer A |
| 0x87 | K-Bus |
| 0x88 | I-Bus |
| 0x8B | Gong 3 |
| 0x8C | Terminal R (ignition/accessories) |
| 0x8D | Signal AGS: telegram error or no telegram |
| 0x8F | Overvoltage (U>16V) |
| 0x90 | Terminal 15 (ignition) |
| 0xBE | Light module EEPROM fault |
| 0xBF | IKE EEPROM fault, coding faulty/incomplete |
| 0xC1 | Signal TWEG+ (Speedometer) |
| 0xC3 | Signal TD (Tachometer/RPM) |
| 0xC7 | Fuel tank level sender 1 |
| 0xCD | Fuel consumption signal (KVA1) |
| 0xCE | Outside temperature |
| 0xCF | SIA reset |
| 0xD3 | Coolant temperature |
| 0xD7 | Fuel tank level sender 2 |
| 0xF4 | CAN bus fault 244 |
| 0xFB | CAN bus fault 251 |
| 0xFF | unknown fault location |

**Fault types:** 0x00=--, 0x01=Short circuit to battery voltage, 0x02=Short circuit to ground, 0x03=Wire break / open circuit, 0x04=Invalid operating range, 0x05=Fault currently present, 0x06=Intermittent fault, 0xFF=unknown fault type

## 0x5B — Climate (IHKA)

| Code | Location |
|------|----------|
| 0x00 | Ventilation flap motor |
| 0x01 | Recirculation flap motor |
| 0x02 | Footwell flap motor |
| 0x03 | Defrost flap motor |
| 0x04 | Rear compartment flap motor |
| 0x05 | Fresh air flap motor |
| 0x06 | Latent heat storage temperature sensor |
| 0x07 | Heat exchanger sensor left |
| 0x08 | Heat exchanger sensor right |
| 0x09 | Evaporator sensor |
| 0x0A | AUC sensor (automatic recirculation control) |
| 0x0B | Terminal 30 (permanent power) |
| 0x0C | free 0x0C |
| 0x0D | Interior temperature sensor |
| 0x0E | AUC heater |
| 0x0F | Auxiliary fan relay |
| 0x10 | Windshield washer nozzle heater relay |
| 0x11 | Rear window defroster relay |
| 0x12 | A/C compressor magnetic clutch |
| 0x13 | DME-KO |
| 0x14 | DME-AC |
| 0x15 | Auxiliary water pump |
| 0x16 | Water valve left |
| 0x17 | Water valve right |
| 0x18 | Auxiliary heater shutoff valve, latent heat storage changeover valve |
| 0x19 | Auxiliary heater wake line |
| 0x1A | Blower control voltage |
| 0x1B | Actuator Y left |
| 0x1C | Actuator Y right |
| 0x1D | Heat exchanger target temperature left |
| 0x1E | Heat exchanger target temperature right |
| 0x1F | Outside temperature |
| 0x20 | Vehicle speed |
| 0x21 | Coolant temperature |
| 0x22 | Engine RPM |
| 0x23 | Terminal 58g (dimming) |
| 0x24 | LCD backlight |
| 0x25 | Latent heat storage shutoff valve |
| 0x26 | Engine running |
| 0x27 | Auxiliary heater on/off |
| 0x29 | AUC sensor |
| 0x2A | Interior sensor blower |
| 0x2B | free 0x2B |
| 0x2C | free 0x2C |
| 0x2D | free 0x2D |
| 0x2E | free 0x2E |
| 0x2F | unknown fault location |

## 0xD0 — Light module (LCM)

| Code | Location |
|------|----------|
| 0x0A | Microprocessor RAM fault |
| 0x0B | Microprocessor ROM fault |
| 0x0C | Microprocessor EEPROM fault |
| 0x0D | Redundant inputs report contradiction |
| 0x0E | PowerMOS status line 1 constantly active |
| 0x0F | PowerMOS status line 2 constantly active |
| 0x10 | PowerMOS status line 3 constantly active |
| 0x11 | (reserved, block 1) |
| 0x14 | Brake light switch, wire open |
| 0x15 | Brake light switch, short to ground |
| 0x16 | Headlight leveling potentiometer open |
| 0x17 | Dimmer potentiometer open |
| 0x18 | Connection to AHM (trailer module) is faulty |
| 0x19 | (reserved, block 2) |
| 0x1E | Fault in headlight leveling driver IC |
| 0x1F | Headlight leveling control Q21/Q22 |
| 0x20 | Headlight leveling control Q11/Q12 |
| 0x21 | (reserved, block 3) |
| 0x28 | Thermal oil sensor defective |
| 0x29 | (undocumented fault, block 4) |
| 0x2A | (undocumented fault, block 4) |
| 0x32 | Terminal 30 missing (permanent power) |
| 0x33 | Terminal R missing (ignition/accessories) |
| 0x34 | Terminal 15 missing (ignition) |
| 0x35 | (undocumented fault, block 5) |
| 0x36 | (undocumented fault, block 5) |
| 0x3C | (undocumented fault, block 6) |
| 0x3D | (undocumented fault, block 6) |
| 0x3E | (undocumented fault, block 6) |
| 0x3F | (undocumented fault, block 6) |
| 0x40 | (undocumented fault, block 6) |
| 0x46 | Intermittent fault when controlling headlight leveling driver |
| 0x47 | (undocumented fault, block 7) |
| 0x48 | (undocumented fault, block 7) |
| 0x49 | (undocumented fault, block 7) |
| 0x4A | (undocumented fault, block 7) |
| 0xFF | unknown fault location |

## 0x60 — Park distance (PDC)

| Code | Location |
|------|----------|
| 0x01 | Front center right sensor |
| 0x02 | Front center left sensor |
| 0x04 | Front right sensor |
| 0x05 | Distance sensor |
| 0x06 | Front left sensor |
| 0x08 | Rear center right sensor |
| 0x09 | Front speaker |
| 0x0A | Rear center left sensor |
| 0x0C | Rear right sensor |
| 0x0D | Rear left sensor |
| 0x13 | Button |
| 0x15 | Rear speaker |
| 0x16 | Control signal |

**Fault types:** 0x00=--, 0x02=Sensor wire: short to ground, 0x03=Wire break / open circuit, 0x04=Decay fault (sensor oscillates too long), 0x05=Shield: short to ground, 0x06=Short circuit shield to sensor wire, 0x07=Fault currently present, 0x08=Intermittent fault, 0x10=Short circuit to battery voltage, 0x20=Short circuit to ground, 0x30=Wire break / open circuit, 0x70=Fault currently present, 0x80=Intermittent fault, 0xFF=--

## 0xE8 — Remote receiver (FBZV)

| Code | Location |
|------|----------|
| 0x01 | Battery fault in transmitter 1 |
| 0x02 | Battery fault in transmitter 2 |
| 0x03 | Battery fault in transmitter 3 |
| 0x04 | Battery fault in transmitter 4 |

## 0x12 — DME (MS41), 209 codes

See `ms41_dtc.json` for the full table (decimal code -> text).

## E87 (KWP2000) researched codes

| Code | Meaning |
|------|---------|
| 93B2 | MRS: Battery Safety Terminal (BST) |
| C947 | MRS: bus communication fault |
| A0B2 | CAS: power supply terminal 30E |
| A0C1 | CAS: output terminal 50 (starter) |
| A6D1 | JBE: auxiliary water pump |
| A6CD | JBE: wiper function (junction box) |
| A738 | JBE: power supply |
| 931D | KOMBI: overvoltage/undervoltage |
| A3AC | KOMBI: DSC distance message missing (bus) |
| 9CCE | LM: battery exhausted / deep discharge |
| 9C6C | IHKA: 12V supply switch center |
| 5DF7 | DSC: voltage above 18 V |
| 5E19 | DSC: CAN DME engine torque not adjustable |
| 5E40 | DSC: steering angle sensor implausible/offset |
| D373 | DSC: F-CAN steering angle messages missing |
| 2C45 | DME: O2 sensor before catalyst (aging) |
| 2C55 | DME: lambda probe bank 1 sensor 1 aging |
| 2C56 | DME: lambda probe signal |
| 2E95 | DME: generator (alternator) |
| 2EE0 | DME: coolant temperature sensor signal |
| 2DEB | DME: power management vehicle electrical system |
