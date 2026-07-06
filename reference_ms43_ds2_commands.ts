/**
 * BMW MS43 DS2 Job Library
 *
 * Complete DS2 command set for the MS43 DME (Siemens Motronic, M54 engine),
 * reconstructed from the BMW EDIABAS SGBD file MS430DS0.prg (BEST/1 bytecode).
 *
 * All commands target ECU address 0x12. Checksum is computed and appended
 * automatically.
 *
 * EDIABAS job names are preserved in JSDoc comments for cross-reference.
 *
 * Usage:
 *   import { MS43 } from "./ms43-jobs";
 *   const cmd = MS43.readIdent();                // [0x12, 0x04, 0x00, 0x16]
 *   const cmd2 = MS43.readStatusGroup(0x03);     // group read
 *   const cmd3 = MS43.controlFuelPump(true);     // fuel pump on
 */

// ─── Constants ────────────────────────────────────────────────────

const ECU_ADDR = 0x12;

// DS2 Service IDs
export const DS2_SERVICE = {
  IDENT: 0x00,
  READ_FAULTS: 0x04,
  END_SESSION: 0x05,
  READ_MEMORY: 0x06,
  STOP_CONTROL: 0x0a,
  READ_STATUS_GROUP: 0x0b,
  READ_APP_INFO: 0x0d,
  STOP_FUNCTION: 0x0e,
  READ_SHADOW_FAULTS: 0x14,
  ACTUATOR_CONTROL: 0x22,
  STOP_DIAGNOSTIC: 0x23,
  SYSTEM_CHECK: 0x2b,
  READ_ADJUSTMENT: 0x40,
  WRITE_ADJUSTMENT: 0x42,
  RESET_ADAPTATION: 0x43,
  MODIFY_ADJUSTMENT: 0x44,
  READ_LINEAR_MEMORY: 0x6c,
  READ_CHECK_CODE: 0x6d,
  INSPECTION_STAMP: 0x90,
  SEED_REQUEST: 0x9e,
  KEY_RESPONSE: 0x9f,
} as const;

// Actuator IDs for ACTUATOR_CONTROL (0x22) commands
export const ACTUATOR_ID = {
  SECONDARY_AIR_PUMP: 0x81,
  LEAK_DETECTION_MOTOR: 0x82,       // DMTL motor
  MAP_THERMOSTAT: 0x83,
  FUEL_PUMP: 0x84,                  // EKP relay
  LEAK_DETECTION_VALVE: 0x86,       // DMTL valve
  INTAKE_MANIFOLD: 0x87,            // DISA
  EXHAUST_FLAP: 0x88,
  CHECK_ENGINE_LIGHT: 0x8a,         // MIL
  ELECTRIC_FAN: 0x92,               // 2-byte value
  SECONDARY_AIR_VALVE: 0x91,
  EVAP_PURGE_VALVE: 0x94,           // TEV
  TEMP_GAUGE: 0x95,                 // 2-byte value
  O2_HEATER_PRE_CAT_B1: 0x9a,
  O2_HEATER_PRE_CAT_B2: 0x9b,
  O2_HEATER_POST_CAT_B1: 0x9c,
  O2_HEATER_POST_CAT_B2: 0x9d,
  VANOS_INTAKE_SETPOINT: 0xa4,
  VANOS_EXHAUST_SETPOINT: 0xa5,
  VANOS_INTAKE_VALVE: 0xa6,
  VANOS_EXHAUST_VALVE: 0xa7,
  INJECTOR_CYL_1: 0xb1,
  INJECTOR_CYL_2: 0xb2,
  INJECTOR_CYL_3: 0xb3,
  INJECTOR_CYL_4: 0xb4,
  INJECTOR_CYL_5: 0xb5,
  INJECTOR_CYL_6: 0xb6,
  IDLE_ACTUATOR: 0xb7,
  LEAK_DETECTION_HEATER: 0xba,      // DMTL heater
  EVAP_COMBINED: 0xbb,              // TEV + DMTL combined
  AC_COMPRESSOR: 0x8e,
} as const;

// Status group IDs for READ_STATUS_GROUP (0x0B)
export const STATUS_GROUP = {
  ADC_SENSORS: 0x02,                // Analog sensor ADC values
  ENGINE_PARAMS: 0x03,              // Engine parameters (RPM, temps, voltages)
  DIGITAL_IO: 0x04,                 // Digital I/O states
  FGR_ABSCHALTUNG: 0x05,            // Cruise control cutoff reasons
  VANOS_IST_SOLL: 0x90,             // VANOS actual/target/reference positions
  ADAPTATION_ACTIVE: 0x91,          // Adaptation active flags
  IDLE_ADAPTATION: 0x92,            // Idle adaptation values
  ECU_CONFIG: 0x94,                 // ECU configuration / EWS status
  LEAK_DETECTION_COUNTER: 0x95,     // DMTL release counter
  OBD_READINESS: 0xa3,              // OBD-II readiness / MIL status / km since MIL
} as const;

// ACK/NAK response codes
export const DS2_ACK = {
  OK: 0xa0,
  NAK: 0xb0,
} as const;

// ─── Frame Builder ────────────────────────────────────────────────

function ds2Checksum(data: number[]): number {
  let xor = 0;
  for (const b of data) xor ^= b;
  return xor;
}

/**
 * Build a DS2 frame: [addr] [length] [payload...] [checksum]
 * Length = addr + length + payload + checksum
 */
function ds2Build(payload: number[]): number[] {
  const length = 2 + payload.length + 1;
  const frame = [ECU_ADDR, length, ...payload];
  frame.push(ds2Checksum(frame));
  return frame;
}

// ─── MS43 Job Library ─────────────────────────────────────────────

export const MS43 = {
  // ── Identification ────────────────────────────────────────────

  /** Read ECU identification block (ASCII). EDIABAS: IDENT */
  readIdent: () => ds2Build([DS2_SERVICE.IDENT]),

  /** Read application info field (VIN, odometer, etc.). EDIABAS: AIF_LESEN */
  readAppInfo: () => ds2Build([DS2_SERVICE.READ_APP_INFO]),

  /** Combined IDENT + AIF read. EDIABAS: IDENT_AIF */
  readIdentAndAppInfo: () => [MS43.readIdent(), MS43.readAppInfo()] as [number[], number[]],

  /** Read check code data. EDIABAS: PRUEFCODE_LESEN */
  readCheckCode: () => ds2Build([DS2_SERVICE.READ_CHECK_CODE]),

  // ── Status Groups ─────────────────────────────────────────────

  /** Read a status data group by ID */
  readStatusGroup: (group: number) => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, group]),

  /** Read engine parameters (RPM, temps, voltages). EDIABAS: STATUS_MESSWERTEBLOCK */
  readEngineParams: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.ENGINE_PARAMS]),

  /** Read digital I/O states. EDIABAS: STATUS_DIGITAL */
  readDigitalIO: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.DIGITAL_IO]),

  /** Read cruise control cutoff reasons. EDIABAS: STATUS_FGR_ABSCHALTUNG */
  readFgrAbschaltung: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.FGR_ABSCHALTUNG]),

  /** Read OBD-II readiness / MIL status. EDIABAS: STATUS_DIGITAL_OBDII */
  readObdReadiness: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.OBD_READINESS]),

  /** Read adaptation active flags (bank 1/2). EDIABAS: STATUS_ADAP_AKTIV */
  readAdaptationActive: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.ADAPTATION_ACTIVE]),

  /** Read idle adaptation values. EDIABAS: STATUS_LL_ADAPTION */
  readIdleAdaptation: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.IDLE_ADAPTATION]),

  /** Read ECU configuration flags / EWS status. EDIABAS: ECU_CONFIG */
  readEcuConfig: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.ECU_CONFIG]),

  /** Read DMTL release counter. EDIABAS: STATUS_FREIGABEZAEHLER_DMTL */
  readLeakDetectionCounter: () => ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.LEAK_DETECTION_COUNTER]),

  /**
   * Read analog sensor ADC value.
   * Group 0x02, 8-byte template with channel selector at byte 7.
   * EDIABAS: STATUS_*_ADC jobs
   * @param channel ADC channel selector byte
   */
  readAdcSensor: (channel: number) =>
    ds2Build([DS2_SERVICE.READ_STATUS_GROUP, STATUS_GROUP.ADC_SENSORS, 0x0e, 0x00, 0x00, 0x00, channel]),

  // ── Fault Memory ──────────────────────────────────────────────

  /** Quick fault read (count + operating hours). EDIABAS: FS_QUICK_LESEN */
  readFaultsQuick: () => ds2Build([DS2_SERVICE.READ_FAULTS, 0x00]),

  /**
   * Full fault memory read.
   * Sends IDENT first (0x00) then parses response.
   * EDIABAS: FS_LESEN
   */
  readFaults: () => ds2Build([DS2_SERVICE.IDENT]),

  /** Read shadow (stored) fault memory. EDIABAS: FS_SHADOW_LESEN */
  readShadowFaults: () => ds2Build([DS2_SERVICE.READ_SHADOW_FAULTS, 0x01]),

  /** Clear entire fault memory. EDIABAS: FS_LOESCHEN */
  clearFaults: () => ds2Build([DS2_SERVICE.END_SESSION]),

  /**
   * Clear specific fault codes.
   * EDIABAS: FS_SELEKTIV_LOESCHEN
   * @param faultBytes 10 bytes identifying faults to clear
   */
  clearFaultsSelective: (faultBytes: number[]) => {
    if (faultBytes.length !== 10) {
      throw new Error("clearFaultsSelective requires exactly 10 fault bytes");
    }
    return ds2Build([DS2_SERVICE.READ_FAULTS, ...faultBytes]);
  },

  // ── Actuator Control ──────────────────────────────────────────

  /**
   * Generic single-byte actuator control.
   * Frame: 12 06 22 <actuator> <value> <checksum>
   */
  controlActuator: (actuator: number, value: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, actuator, value & 0xff]),

  /**
   * Generic two-byte actuator control (fan, temp gauge, etc.)
   * Frame: 12 07 22 <actuator> <hi> <lo> <checksum>
   */
  controlActuator2: (actuator: number, hi: number, lo: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, actuator, hi & 0xff, lo & 0xff]),

  // Convenience wrappers:

  /** Secondary air pump on/off. EDIABAS: STEUERN_SEK_PUMPE */
  controlSecondaryAirPump: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.SECONDARY_AIR_PUMP, on ? 0xff : 0x00]),

  /** Fuel pump relay on/off. EDIABAS: STEUERN_EKP */
  controlFuelPump: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.FUEL_PUMP, on ? 0xff : 0x00]),

  /** DMTL leak detection motor on/off. EDIABAS: STEUERN_DMTL_MOTOR */
  controlLeakDetectionMotor: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.LEAK_DETECTION_MOTOR, on ? 0xff : 0x00]),

  /** DMTL leak detection valve open/close. EDIABAS: STEUERN_DMTL_VENTIL */
  controlLeakDetectionValve: (open: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.LEAK_DETECTION_VALVE, open ? 0xff : 0x00]),

  /** DISA intake manifold on/off. EDIABAS: STEUERN_DISA */
  controlIntakeManifold: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.INTAKE_MANIFOLD, on ? 0xff : 0x00]),

  /** Exhaust flap open/close. EDIABAS: STEUERN_ABGASKLAPPE */
  controlExhaustFlap: (open: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.EXHAUST_FLAP, open ? 0xff : 0x00]),

  /** Check engine light (MIL) on/off. EDIABAS: STEUERN_MIL */
  controlCheckEngineLight: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.CHECK_ENGINE_LIGHT, on ? 0xff : 0x00]),

  /** AC compressor relay on/off. EDIABAS: STEUERN_KO */
  controlAcCompressor: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.AC_COMPRESSOR, on ? 0xff : 0x00]),

  /** Secondary air valve on/off. EDIABAS: STEUERN_SEK_VENTIL */
  controlSecondaryAirValve: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.SECONDARY_AIR_VALVE, on ? 0xff : 0x00]),

  /** DMTL leak detection heater on/off. EDIABAS: STEUERN_DMTL_HEIZUNG */
  controlLeakDetectionHeater: (on: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.LEAK_DETECTION_HEATER, on ? 0xff : 0x00]),

  /**
   * Map thermostat duty cycle. EDIABAS: STEUERN_KF_THERMOSTAT
   * @param dutyPercent 0-100 (default 80)
   */
  controlMapThermostat: (dutyPercent: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.MAP_THERMOSTAT, Math.round(dutyPercent * 255 / 100) & 0xff]),

  /**
   * Evap purge valve (TEV) duty cycle. EDIABAS: STEUERN_TEV
   * @param dutyPercent 0-100
   */
  controlEvapPurgeValve: (dutyPercent: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.EVAP_PURGE_VALVE, Math.round(dutyPercent * 255 / 100) & 0xff]),

  /** Combined TEV + DMTL duty cycle. EDIABAS: STEUERN_DMTL_TEV */
  controlEvapCombined: (dutyPercent: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.EVAP_COMBINED, Math.round(dutyPercent * 255 / 100) & 0xff]),

  /**
   * Idle actuator duty cycle. EDIABAS: STEUERN_LL_STELLER
   * @param dutyPercent 5-94
   */
  controlIdleActuator: (dutyPercent: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.IDLE_ACTUATOR, Math.round(dutyPercent * 255 / 100) & 0xff]),

  /**
   * O2 sensor heater duty cycle. EDIABAS: STEUERN_LS_HEIZUNG_*
   * @param sensor Which O2 heater actuator ID
   * @param dutyPercent 0-99
   */
  controlO2Heater: (sensor: 0x9a | 0x9b | 0x9c | 0x9d, dutyPercent: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, sensor, Math.round(dutyPercent * 255 / 100) & 0xff]),

  /**
   * VANOS intake cam spread setpoint. EDIABAS: STEUERN_VANOS_E_SOLLWERT
   * @param spread Cam spread value (80-120 °KW)
   */
  controlVanosIntakeSetpoint: (spread: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.VANOS_INTAKE_SETPOINT, spread & 0xff]),

  /**
   * VANOS exhaust cam spread setpoint. EDIABAS: STEUERN_VANOS_A_SOLLWERT
   * @param spread Cam spread value (-80 to -105 °KW)
   */
  controlVanosExhaustSetpoint: (spread: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.VANOS_EXHAUST_SETPOINT, spread & 0xff]),

  /** VANOS intake valve duty cycle. EDIABAS: STEUERN_VANOS_E_VENTIL */
  controlVanosIntakeValve: (duty: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.VANOS_INTAKE_VALVE, duty & 0xff]),

  /** VANOS exhaust valve duty cycle. EDIABAS: STEUERN_VANOS_A_VENTIL */
  controlVanosExhaustValve: (duty: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.VANOS_EXHAUST_VALVE, duty & 0xff]),

  /**
   * Electric fan duty cycle (2-byte value). EDIABAS: STEUERN_E_LUEFTER
   * @param dutyPercent 0-100
   */
  controlElectricFan: (dutyPercent: number) => {
    const val = Math.round(dutyPercent * 255 / 100);
    return ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.ELECTRIC_FAN, val & 0xff, 0x00]);
  },

  /**
   * Set temperature gauge display. EDIABAS: STEUERN_TEMP_ANZEIGE_KOMBI
   * @param tempValue Temperature value
   * @param overheat true to set overheat flag
   */
  controlTempGauge: (tempValue: number, overheat: boolean) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, ACTUATOR_ID.TEMP_GAUGE, tempValue & 0xff, overheat ? 0xff : 0x00]),

  /**
   * Injector control for cylinder 1-6. EDIABAS: STEUERN_EV_x_ARG
   * @param cylinder 1-6
   * @param pulseHi Pulse width high byte (default 0x5D)
   * @param pulseLo Pulse width low byte (default 0x0A)
   */
  controlInjector: (cylinder: 1 | 2 | 3 | 4 | 5 | 6, pulseHi = 0x5d, pulseLo = 0x0a) => {
    const actuator = 0xb0 + cylinder; // B1-B6
    return ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, actuator, pulseHi, pulseLo]);
  },

  /**
   * Selectively blank an injector. EDIABAS: STEUERN_EV_SELEKTIV_AUSBLENDEN
   * @param cylinder 1-6
   */
  blankInjector: (cylinder: 1 | 2 | 3 | 4 | 5 | 6) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, 0xb0 + cylinder, 0x5d, 0x0a]),

  /**
   * Throttle body angle control. EDIABAS: STEUERN_DK_WINKEL
   * @param angle New throttle angle value
   */
  controlThrottle: (angle: number) =>
    ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, 0xa2, angle & 0xff, 0x00]),

  /**
   * Idle speed adjustment. EDIABAS: STEUERN_LL_DREHZAHL_VERSTELLEN
   * @param rpm Target RPM (512-1792)
   */
  controlIdleSpeed: (rpm: number) => {
    const rpmByte = Math.round(rpm / 7.8) & 0xff;
    return ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, 0xa2, rpmByte, 0x00]);
  },

  // ── Stop / End ────────────────────────────────────────────────

  /** Stop actuator control. EDIABAS: STEUERN_STOP */
  stopControl: () => ds2Build([DS2_SERVICE.STOP_FUNCTION]),

  /** Stop specific diagnostic function */
  stopFunction: () => ds2Build([DS2_SERVICE.STOP_CONTROL]),

  /**
   * Stop individual diagnostic function. EDIABAS: DIAGNOSE_STOP
   * @param funcByte Function byte
   */
  stopDiagnosticFunction: (funcByte: number) =>
    ds2Build([DS2_SERVICE.STOP_DIAGNOSTIC, funcByte & 0xff]),

  /** Keep diagnostic session alive. EDIABAS: DIAGNOSE_AUFRECHT */
  keepAlive: () => ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, 0x01]),

  /** End diagnostic session. EDIABAS: DIAGNOSE_ENDE */
  endSession: () => ds2Build([DS2_SERVICE.STOP_DIAGNOSTIC, 0x00]),

  // ── Adaptation Reset ──────────────────────────────────────────

  /** Reset ALL adaptations. EDIABAS: ADAPT_LOESCHEN */
  resetAllAdaptations: () => ds2Build([DS2_SERVICE.RESET_ADAPTATION, 0xff, 0xff]),

  /**
   * Reset specific adaptation via bitmask. EDIABAS: ADAPT_*_LOESCHEN
   * @param maskHi High byte of adaptation mask
   * @param maskLo Low byte of adaptation mask
   */
  resetAdaptation: (maskHi: number, maskLo: number) =>
    ds2Build([DS2_SERVICE.RESET_ADAPTATION, maskHi & 0xff, maskLo & 0xff]),

  // ── Adjustment Values ─────────────────────────────────────────

  /** Read CO adjustment value. EDIABAS: CO_ABGLEICH_LESEN */
  readCoAdjustment: () => ds2Build([DS2_SERVICE.READ_ADJUSTMENT, 0x01]),

  /** Read idle adjustment value. EDIABAS: LL_ABGLEICH_LESEN */
  readIdleAdjustment: () => ds2Build([DS2_SERVICE.READ_ADJUSTMENT, 0x02]),

  /** Read fuel consumption factor. EDIABAS: VERBRAUCH_ABGLEICH_LESEN */
  readFuelConsumptionFactor: () => [
    ds2Build([DS2_SERVICE.MODIFY_ADJUSTMENT, 0x02]),
    ds2Build([DS2_SERVICE.MODIFY_ADJUSTMENT, 0x03]),
  ] as [number[], number[]],

  /** Write CO adjustment permanently. EDIABAS: CO_ABGLEICH_PROGRAMMIEREN */
  writeCoAdjustment: () => ds2Build([DS2_SERVICE.WRITE_ADJUSTMENT, 0x01]),

  /** Write idle adjustment permanently. EDIABAS: LL_ABGLEICH_PROGRAMMIEREN */
  writeIdleAdjustment: () => ds2Build([DS2_SERVICE.WRITE_ADJUSTMENT, 0x02]),

  // ── Memory Read ───────────────────────────────────────────────

  /**
   * Read arbitrary RAM cells. EDIABAS: SPEICHER_LIN_LESEN
   * @param address 24-bit start address
   * @param count Number of bytes to read
   */
  readMemory: (address: number, count: number) =>
    ds2Build([
      DS2_SERVICE.READ_MEMORY,
      (address >> 16) & 0xff,
      (address >> 8) & 0xff,
      address & 0xff,
      0x00,
      count & 0xff,
    ]),

  // ── System Checks ─────────────────────────────────────────────

  /** Start EWS synchronization. EDIABAS: STEUERN_SYNC_MODE */
  startEwsSync: (mode: number) => ds2Build([DS2_SERVICE.SYSTEM_CHECK, 0x01]),

  /** Read EWS sync status. EDIABAS: STATUS_SYNC_MODE */
  readEwsSyncStatus: () => ds2Build([DS2_SERVICE.SYSTEM_CHECK, 0x03]),

  /** Start misfire/roughness test. EDIABAS: START_SYSTEMCHECK_LAUFUNRUHE */
  startMisfireTest: () => ds2Build([DS2_SERVICE.SYSTEM_CHECK, 0x05]),

  /** Start secondary air test. EDIABAS: START_SYSTEMCHECK_SEK_LUFT */
  startSecondaryAirTest: () => ds2Build([DS2_SERVICE.SYSTEM_CHECK, 0xa0]),

  /** Stop secondary air test. EDIABAS: STOP_SYSTEMCHECK_SEK_LUFT */
  stopSecondaryAirTest: () => ds2Build([DS2_SERVICE.SYSTEM_CHECK, 0xa1]),

  // ── Security Access ───────────────────────────────────────────

  /** Request seed for security access. EDIABAS: SEED_KEY (step 1) */
  requestSeed: () => ds2Build([DS2_SERVICE.SEED_REQUEST]),

  /** Send computed key response. EDIABAS: SEED_KEY (step 2) */
  sendKey: () => ds2Build([DS2_SERVICE.KEY_RESPONSE]),

  // ── Inspection Stamp ──────────────────────────────────────────

  /** Read inspection stamp (3 bytes). EDIABAS: PRUEFSTEMPEL_LESEN */
  readInspectionStamp: () => ds2Build([DS2_SERVICE.READ_LINEAR_MEMORY, 0x00]),

  /**
   * Write inspection stamp. EDIABAS: PRUEFSTEMPEL_SCHREIBEN
   * @param b1 Byte 1 (0-255)
   * @param b2 Byte 2 (0-255)
   * @param b3 Byte 3 (0-255)
   */
  writeInspectionStamp: (b1: number, b2: number, b3: number) =>
    ds2Build([DS2_SERVICE.INSPECTION_STAMP, 0x42, 0x4d, 0x57, b1 & 0xff, b2 & 0xff, b3 & 0xff]),

  // ── Misc ──────────────────────────────────────────────────────

  /** Clear pedal misuse entries. EDIABAS: FUSSHEBELFEHLBEDIENUNG_LOESCHEN */
  clearPedalMisuse: () => ds2Build([DS2_SERVICE.RESET_ADAPTATION, 0x00, 0x00]),

  /** Clear cruise control shutdown entries. EDIABAS: ABSCHALTBEDINGUNG_FGR_LOESCHEN */
  clearCruiseControlShutdown: () => ds2Build([DS2_SERVICE.RESET_ADAPTATION, 0x00, 0x00]),

  /**
   * Adjust idle speed and read back result. EDIABAS: STEUERN_LL_MANIPULATION
   * @param rpm Target RPM (512-1792)
   */
  adjustIdleSpeed: (rpm: number) => {
    const rpmByte = Math.round(rpm / 7.8) & 0xff;
    return ds2Build([DS2_SERVICE.ACTUATOR_CONTROL, 0xa2, rpmByte, 0x00]);
  },
} as const;

// ─── Response Parsers ─────────────────────────────────────────────

export interface DS2Response {
  address: number;
  length: number;
  ack: number;
  payload: Uint8Array;
  checksumOk: boolean;
  raw: Uint8Array;
}

/**
 * Parse a DS2 response frame
 */
export function parseDS2Response(data: Uint8Array, size: number): DS2Response | null {
  if (size < 4) return null;

  const address = data[0];
  const length = data[1];

  if (size < length) return null;

  const raw = data.subarray(0, length);
  const ack = data[2];
  const payload = data.subarray(3, length - 1);

  let xor = 0;
  for (let i = 0; i < length - 1; i++) xor ^= data[i];
  const checksumOk = xor === data[length - 1];

  return {
    address,
    length,
    ack,
    payload: new Uint8Array(payload),
    checksumOk,
    raw: new Uint8Array(raw),
  };
}

/**
 * Parse IDENT response payload (ASCII-encoded).
 * Field offsets from RomRaider DS2EcuInit and SGBD disassembly.
 */
export function parseIdent(payload: Uint8Array): Record<string, string> {
  const raw = new TextDecoder().decode(payload);
  return {
    partNumber: raw.substring(0, 7),
    softwareNumber: raw.substring(7, 21),
    codingIndex: raw.substring(21, 25),
    diagnosticIndex: raw.substring(25, 29),
    busIndex: raw.substring(29, 31),
    productionWeek: raw.substring(31, 33),
    productionYear: raw.substring(33, 35),
    supplierNumber: raw.substring(35, 40),
    productionNumber: raw.substring(40),
    raw,
  };
}

/**
 * Decode ECU_CONFIG response (group 0x94) bitfields.
 * Byte/bit positions from SGBD job results annotations.
 */
export function parseEcuConfig(payload: Uint8Array): Record<string, number> {
  if (payload.length < 4) return {};
  const b1 = payload[0], b2 = payload[1], b3 = payload[2], b4 = payload[3];
  return {
    hasAutoTransmission: (b1 >> 4) & 1,
    hasCatalyticConverter: (b1 >> 2) & 1,
    hasDualExhaust: (b1 >> 1) & 1,
    hasSingleExhaust: b1 & 1,
    hasInstrumentCluster: (b2 >> 6) & 1,
    hasSafm: (b2 >> 5) & 1,
    hasElectricFan: (b2 >> 4) & 1,
    hasMil: (b2 >> 3) & 1,
    hasExhaustFlap: (b2 >> 2) & 1,
    hasAc: (b2 >> 1) & 1,
    hasSlp: (b3 >> 5) & 1,
    hasMultiFunctionSteering: (b3 >> 3) & 1,
    hasStabilityControl: (b3 >> 1) & 1,
    hasPencilCoils: (b4 >> 5) & 1,
    hasLeakDetectionHeater: b4 & 1,
  };
}

// ─── Digital IO Decoder (group 0x04) ──────────────────────────────
// Source: SGBD MS430DS0.prg table BITS, STAT_* entries (indices 18-67)
// Payload bytes 0-5 contain digital status bits.

interface DigitalBit {
  name: string;
  label: string;
  byte: number;
  mask: number;
  value: number;
}

/**
 * Digital IO bit definitions from SGBD BITS table.
 * Each entry: test (payload[byte] & mask) === value → active.
 *
 * Byte 0: switch inputs + load state
 * Byte 1: engine operating state flags
 * Byte 2: secondary system states
 * Byte 3: output / warning lamp states
 * Byte 4: driving mode flags
 * Byte 5: VANOS + O2 heater states
 */
const DIGITAL_IO_BITS: DigitalBit[] = [
  // Byte 0 — switch inputs + load state
  { name: "S_KO",    label: "AC Compressor Relay",    byte: 0, mask: 0x80, value: 0x80 },
  { name: "S_AC",    label: "AC Request",             byte: 0, mask: 0x40, value: 0x40 },
  { name: "S_FGR",   label: "Cruise Control Active",  byte: 0, mask: 0x20, value: 0x20 },
  { name: "S_KUP",   label: "Clutch Switch",          byte: 0, mask: 0x10, value: 0x10 },
  { name: "S_BLS",   label: "Brake Light Switch",     byte: 0, mask: 0x08, value: 0x08 },
  { name: "S_BLTS",  label: "Brake Test Switch",      byte: 0, mask: 0x04, value: 0x04 },
  // Byte 0 bits 1:0 — load state (multi-value)
  { name: "LL",      label: "Idle (Leerlauf)",        byte: 0, mask: 0x03, value: 0x01 },
  { name: "TL",      label: "Part Load (Teillast)",   byte: 0, mask: 0x03, value: 0x02 },
  { name: "VL",      label: "Full Load (Volllast)",   byte: 0, mask: 0x03, value: 0x03 },

  // Byte 1 — engine operating state
  { name: "LAMBDAREG2", label: "Lambda Control Bank 2",  byte: 1, mask: 0x80, value: 0x80 },
  { name: "LAMBDAREG1", label: "Lambda Control Bank 1",  byte: 1, mask: 0x40, value: 0x40 },
  { name: "SCHUB_AB",   label: "Fuel Cutoff (Overrun)",  byte: 1, mask: 0x20, value: 0x20 },
  { name: "SCHUB",      label: "Overrun Detected",       byte: 1, mask: 0x10, value: 0x10 },
  { name: "START",      label: "Cranking",               byte: 1, mask: 0x08, value: 0x08 },
  { name: "FS",         label: "Fault Memory Active",    byte: 1, mask: 0x04, value: 0x04 },
  { name: "EGS",        label: "EGS (Transmission) Comm", byte: 1, mask: 0x02, value: 0x02 },
  { name: "CAN",        label: "CAN Bus Active",         byte: 1, mask: 0x01, value: 0x01 },

  // Byte 2 — secondary system states
  { name: "SLV",     label: "Secondary Air Valve",      byte: 2, mask: 0x80, value: 0x80 },
  { name: "SLP",     label: "Secondary Air Pump",       byte: 2, mask: 0x40, value: 0x40 },
  { name: "SSP",     label: "Secondary Air Switchover",  byte: 2, mask: 0x20, value: 0x20 },
  { name: "RLV",     label: "Return Valve",             byte: 2, mask: 0x10, value: 0x10 },
  { name: "KLAPPE",  label: "Exhaust Flap",             byte: 2, mask: 0x08, value: 0x08 },
  { name: "DMTL",    label: "DMTL (Leak Detection)",    byte: 2, mask: 0x04, value: 0x04 },
  { name: "R_KO",    label: "AC Compressor Relay Out",  byte: 2, mask: 0x02, value: 0x02 },
  { name: "R_EKP",   label: "Fuel Pump Relay",          byte: 2, mask: 0x01, value: 0x01 },

  // Byte 3 — output / warning lamp states
  { name: "KAT_H",   label: "Catalyst Heater",         byte: 3, mask: 0x80, value: 0x80 },
  { name: "V_DMTL",  label: "DMTL Valve",              byte: 3, mask: 0x40, value: 0x40 },
  { name: "EML_IL",  label: "EML Indicator Lamp",      byte: 3, mask: 0x20, value: 0x20 },
  { name: "MIL",     label: "MIL (Check Engine)",      byte: 3, mask: 0x10, value: 0x10 },
  { name: "TEV",     label: "Tank Vent Valve (EVAP)",   byte: 3, mask: 0x08, value: 0x08 },
  { name: "DISA",    label: "DISA Valve (Intake)",      byte: 3, mask: 0x04, value: 0x04 },
  { name: "ASC",     label: "ASC/DSC Active",          byte: 3, mask: 0x02, value: 0x02 },
  { name: "TMOT",    label: "Engine Temp Warning",     byte: 3, mask: 0x01, value: 0x01 },

  // Byte 4 — driving mode flags
  { name: "RUHE",      label: "Rest Mode",              byte: 4, mask: 0x80, value: 0x80 },
  { name: "VERZ",      label: "Deceleration",           byte: 4, mask: 0x40, value: 0x40 },
  { name: "WIDERAUF",  label: "Resume (Cruise)",        byte: 4, mask: 0x20, value: 0x20 },
  { name: "BESCHL",    label: "Acceleration",           byte: 4, mask: 0x10, value: 0x10 },
  { name: "T_DOWN",    label: "Tip Down (Cruise)",      byte: 4, mask: 0x08, value: 0x08 },
  { name: "T_UP",      label: "Tip Up (Cruise)",        byte: 4, mask: 0x04, value: 0x04 },
  { name: "AUS",       label: "Cruise Off",             byte: 4, mask: 0x02, value: 0x02 },
  { name: "HAUS",      label: "Main Switch Off",        byte: 4, mask: 0x01, value: 0x01 },

  // Byte 5 — VANOS + O2 sensor heater states
  { name: "VAN_AK",     label: "VANOS Active",           byte: 5, mask: 0x80, value: 0x80 },
  { name: "VAN_BR",     label: "VANOS Ready",            byte: 5, mask: 0x40, value: 0x40 },
  { name: "VAN_PA",     label: "VANOS Parked",           byte: 5, mask: 0x20, value: 0x20 },
  { name: "GEB_OK",     label: "Crankshaft Signal OK",   byte: 5, mask: 0x10, value: 0x10 },
  { name: "LSH_NK2_B",  label: "O2 Heater Post-Cat B2",  byte: 5, mask: 0x08, value: 0x08 },
  { name: "LSH_NK1_B",  label: "O2 Heater Post-Cat B1",  byte: 5, mask: 0x04, value: 0x04 },
  { name: "LSH_VK2_B",  label: "O2 Heater Pre-Cat B2",   byte: 5, mask: 0x02, value: 0x02 },
  { name: "LSH_VK1_B",  label: "O2 Heater Pre-Cat B1",   byte: 5, mask: 0x01, value: 0x01 },
];

/**
 * Decode digital IO status (group 0x04) response payload.
 * Returns a map of bit name → active (true/false).
 */
export function parseDigitalIO(payload: Uint8Array): Array<{ name: string; label: string; active: boolean }> {
  return DIGITAL_IO_BITS.map((bit) => {
    const byteVal = bit.byte < payload.length ? payload[bit.byte] : 0;
    return {
      name: bit.name,
      label: bit.label,
      active: (byteVal & bit.mask) === bit.value,
    };
  });
}

// ─── Engine Parameters Decoder (group 0x03) ───────────────────────
// Source: SGBD MS430DS0.prg table BetriebswTab, TELEGRAM=12050B03
// BYTE column = offset from DS2 frame start (addr=0, len=1, ack=2, data starts at 3)
// So payload offset = BYTE - 3.
//
// DATA_TYPE: 2=uint8, 3=int8, 5=uint16BE, 7=int16BE
// Formula: physical = raw * FACT_A + FACT_B

interface StatusParam {
  name: string;
  label: string;
  offset: number;     // payload offset (BYTE - 3)
  size: 1 | 2;        // 1=byte, 2=uint16
  signed: boolean;
  factorA: number;
  factorB: number;
  unit: string;
  decimals: number;
}

const ENGINE_PARAMS: StatusParam[] = [
  { name: "N",           label: "Engine Speed",            offset: 0,  size: 2, signed: false, factorA: 1.0,         factorB: 0,     unit: "RPM",    decimals: 0 },
  { name: "VS",          label: "Vehicle Speed",           offset: 2,  size: 1, signed: false, factorA: 1.0,         factorB: 0,     unit: "km/h",   decimals: 0 },
  { name: "PVS_AV",      label: "Pedal Position",          offset: 3,  size: 2, signed: false, factorA: 0.0018311,   factorB: 0,     unit: "deg",    decimals: 2 },
  { name: "TPS_AV_PRJ",  label: "Throttle Position",       offset: 5,  size: 2, signed: false, factorA: 0.0018311,   factorB: 0,     unit: "deg",    decimals: 2 },
  { name: "MAF_KGH",     label: "Air Mass Flow",           offset: 7,  size: 2, signed: false, factorA: 0.25,        factorB: 0,     unit: "kg/h",   decimals: 1 },
  { name: "TIA",         label: "Intake Air Temp",         offset: 9,  size: 1, signed: false, factorA: 0.75,        factorB: -48.0, unit: "°C",     decimals: 1 },
  { name: "TCO",         label: "Coolant Temp",            offset: 10, size: 1, signed: false, factorA: 0.75,        factorB: -48.0, unit: "°C",     decimals: 1 },
  { name: "TOIL",        label: "Oil Temp",                offset: 11, size: 1, signed: false, factorA: 0.796,       factorB: -48.0, unit: "°C",     decimals: 1 },
  { name: "TCO_EX",      label: "Coolant Outlet Temp",     offset: 12, size: 1, signed: false, factorA: 0.75,        factorB: -48.0, unit: "°C",     decimals: 1 },
  { name: "IGA_1",       label: "Ignition Advance",        offset: 13, size: 1, signed: false, factorA: -0.375,      factorB: 72.0,  unit: "°KW",    decimals: 1 },
  { name: "TI_BANK_1",   label: "Injection Time",          offset: 14, size: 2, signed: false, factorA: 0.0053333,   factorB: 0,     unit: "ms",     decimals: 2 },
  { name: "ISAPWM_IS",   label: "Idle Integrator",         offset: 16, size: 2, signed: true,  factorA: 0.0015,      factorB: 0,     unit: "%",      decimals: 2 },
  { name: "ISAPWM_ISA",  label: "Idle Actuator",           offset: 18, size: 2, signed: false, factorA: 0.0015,      factorB: 0,     unit: "%",      decimals: 2 },
  { name: "CAM_AV_IN",   label: "VANOS Intake Pos",        offset: 20, size: 1, signed: false, factorA: 0.375,       factorB: 60.0,  unit: "°KW",    decimals: 1 },
  { name: "CAM_AV_EX",   label: "VANOS Exhaust Pos",       offset: 21, size: 1, signed: true,  factorA: -0.375,      factorB: -60.0, unit: "°KW",    decimals: 1 },
  { name: "VB_IGK",      label: "Battery (IGK)",           offset: 22, size: 1, signed: false, factorA: 0.10156,     factorB: 0,     unit: "V",      decimals: 2 },
  { name: "LAM_1",       label: "Lambda Integrator B1",    offset: 23, size: 2, signed: false, factorA: 0.000015259, factorB: 0.5,   unit: "",       decimals: 4 },
  { name: "LAM_2",       label: "Lambda Integrator B2",    offset: 25, size: 2, signed: false, factorA: 0.000015259, factorB: 0.5,   unit: "",       decimals: 4 },
  { name: "LSHPWM_UP_1", label: "O2 Heater Pre-Cat B1",   offset: 27, size: 1, signed: false, factorA: 0.391,       factorB: 0,     unit: "%",      decimals: 1 },
  { name: "LSHPWM_UP_2", label: "O2 Heater Pre-Cat B2",   offset: 28, size: 1, signed: false, factorA: 0.391,       factorB: 0,     unit: "%",      decimals: 1 },
  { name: "LSHPWM_DN_1", label: "O2 Heater Post-Cat B1",  offset: 29, size: 1, signed: false, factorA: 0.391,       factorB: 0,     unit: "%",      decimals: 1 },
  { name: "LSHPWM_DN_2", label: "O2 Heater Post-Cat B2",  offset: 30, size: 1, signed: false, factorA: 0.391,       factorB: 0,     unit: "%",      decimals: 1 },
  { name: "MAF_MES",     label: "Charge (per stroke)",     offset: 31, size: 2, signed: false, factorA: 0.0212,      factorB: 0,     unit: "mg/str", decimals: 2 },
  { name: "NL_2",        label: "O2 Sensor Pre-Cat B1",    offset: 33, size: 2, signed: false, factorA: 0.0000778,   factorB: 0,     unit: "V",      decimals: 4 },
  { name: "NL_5",        label: "O2 Sensor Pre-Cat B2",    offset: 35, size: 2, signed: false, factorA: 0.0000778,   factorB: 0,     unit: "V",      decimals: 4 },
  { name: "ECFPWM_ECF",  label: "Electric Fan Duty",       offset: 37, size: 1, signed: false, factorA: 0.39063,     factorB: 0,     unit: "%",      decimals: 1 },
  { name: "AMP_MES",     label: "Barometric Pressure",     offset: 38, size: 2, signed: false, factorA: 0.08292,     factorB: 0,     unit: "hPa",    decimals: 1 },
  { name: "VB",          label: "Battery Voltage",         offset: 40, size: 1, signed: false, factorA: 0.10156,     factorB: 0,     unit: "V",      decimals: 2 },
];

/**
 * Decode engine parameters (group 0x03) response payload.
 * Returns array of { name, label, value, unit } for each decodable parameter.
 */
export function parseEngineParams(payload: Uint8Array): Array<{ name: string; label: string; value: string; unit: string }> {
  const result: Array<{ name: string; label: string; value: string; unit: string }> = [];

  for (const p of ENGINE_PARAMS) {
    if (p.offset >= payload.length) continue;
    if (p.size === 2 && p.offset + 1 >= payload.length) continue;

    let raw: number;
    if (p.size === 2) {
      raw = (payload[p.offset] << 8) | payload[p.offset + 1];
      if (p.signed && raw > 32767) raw -= 65536;
    } else {
      raw = payload[p.offset];
      if (p.signed && raw > 127) raw -= 256;
    }

    const physical = raw * p.factorA + p.factorB;
    result.push({
      name: p.name,
      label: p.label,
      value: physical.toFixed(p.decimals),
      unit: p.unit,
    });
  }

  return result;
}

// ─── FGR Abschaltung Decoder (group 0x05, BITS table) ─────────────
// Source: SGBD MS430DS0.prg table BITS, indices 68-95
// These are cruise control cutoff reason flags from group 0x05 response.

const FGR_BITS: DigitalBit[] = [
  // Byte 0
  { name: "ENDSTUFE_DK",            label: "Throttle Final Stage Error",    byte: 0, mask: 0x40, value: 0x40 },
  { name: "TIMEOUT_ASC",            label: "ASC/DSC Timeout",              byte: 0, mask: 0x20, value: 0x20 },
  { name: "VS_SIGNAL",              label: "Speed Signal Error",           byte: 0, mask: 0x10, value: 0x10 },
  { name: "TPS_FEHLER",             label: "Throttle Position Error",      byte: 0, mask: 0x08, value: 0x08 },
  { name: "ISA_LIH",                label: "Idle Actuator Limit",          byte: 0, mask: 0x04, value: 0x04 },
  { name: "VS_PLAUSIBILISIERUNG",   label: "Speed Plausibility Error",     byte: 0, mask: 0x02, value: 0x02 },
  { name: "MONITORING_FEHLER",      label: "Monitoring Error",             byte: 0, mask: 0x01, value: 0x01 },

  // Byte 1
  { name: "BREMSENFEHLER",          label: "Brake System Error",           byte: 1, mask: 0x20, value: 0x20 },
  { name: "TIMEOUT_EGS",            label: "EGS (Transmission) Timeout",   byte: 1, mask: 0x10, value: 0x10 },
  { name: "MFL_FEHLER",             label: "Multifunction Steering Error", byte: 1, mask: 0x08, value: 0x08 },
  { name: "KUPPLUNGSSCHALTER",      label: "Clutch Switch Active",         byte: 1, mask: 0x04, value: 0x04 },
  { name: "DYNAMIKBEGRENZUNG_2",    label: "Dynamic Limit 2",             byte: 1, mask: 0x02, value: 0x02 },
  { name: "DYNAMIKBEGRENZUNG_1",    label: "Dynamic Limit 1",             byte: 1, mask: 0x01, value: 0x01 },

  // Byte 2
  { name: "MFL_BOTSCHAFT",          label: "MFL CAN Message",             byte: 2, mask: 0x80, value: 0x80 },
  { name: "BTS_BLS_PLAUSIBILITAET", label: "Brake Switch Plausibility",   byte: 2, mask: 0x40, value: 0x40 },
  { name: "DREHZAHLBEGRENZUNG",     label: "RPM Limiter Active",          byte: 2, mask: 0x20, value: 0x20 },
  { name: "VS_FIL",                 label: "Filtered Speed Error",        byte: 2, mask: 0x10, value: 0x10 },
  { name: "UEBERTRETEN",            label: "Speed Exceeded",              byte: 2, mask: 0x08, value: 0x08 },
  { name: "HOCHLAUFSPERRE",         label: "Run-up Lock",                 byte: 2, mask: 0x04, value: 0x04 },
  { name: "BESCHL_UEW",             label: "Acceleration Monitoring",     byte: 2, mask: 0x02, value: 0x02 },
  { name: "F_V1",                   label: "Function V1",                 byte: 2, mask: 0x01, value: 0x01 },

  // Byte 3
  { name: "MFL_ANFORDERUNG_AUS",    label: "MFL Request Off",             byte: 3, mask: 0x10, value: 0x10 },
  { name: "ESP",                    label: "ESP Intervention",            byte: 3, mask: 0x08, value: 0x08 },
  { name: "VS_SP_MAX_CRU",          label: "Max Cruise Speed",            byte: 3, mask: 0x04, value: 0x04 },
  { name: "UEBERHOLFUNKTION",       label: "Overtake Function",           byte: 3, mask: 0x02, value: 0x02 },
  { name: "VS_ABWEICHUNG",          label: "Speed Deviation",             byte: 3, mask: 0x01, value: 0x01 },
];

/**
 * Decode FGR Abschaltung (cruise control cutoff) status (group 0x05).
 * Returns array of active cutoff reason flags.
 */
export function parseFgrAbschaltung(payload: Uint8Array): Array<{ name: string; label: string; active: boolean }> {
  return FGR_BITS.map((bit) => {
    const byteVal = bit.byte < payload.length ? payload[bit.byte] : 0;
    return {
      name: bit.name,
      label: bit.label,
      active: (byteVal & bit.mask) === bit.value,
    };
  });
}

/**
 * Decode OBD-II readiness status (group 0x05).
 * Bit positions from SGBD job results: DATA A/B/C/D at bytes 4-7.
 */
export function parseObdReadiness(payload: Uint8Array): Record<string, number> {
  if (payload.length < 5) return {};
  const a = payload[1], b = payload[2], c = payload[3], d = payload[4];
  return {
    milActive: (a >> 7) & 1,
    milFaultCount: a & 0x7f,
    monitoringComponents: (b >> 2) & 1,
    monitoringFuelSystem: (b >> 1) & 1,
    monitoringMisfires: b & 1,
    monitoringO2Heater: (c >> 6) & 1,
    monitoringO2Sensor: (c >> 5) & 1,
    monitoringSecondaryAir: (c >> 3) & 1,
    monitoringEvapSystem: (c >> 2) & 1,
    monitoringCatalyst: c & 1,
    readyO2Heater: ((d >> 6) & 1) ^ 1,       // inverted: 0 = complete
    readyO2Sensor: ((d >> 5) & 1) ^ 1,
    readySecondaryAir: ((d >> 3) & 1) ^ 1,
    readyEvapSystem: ((d >> 2) & 1) ^ 1,
    readyCatalyst: (d & 1) ^ 1,
  };
}
