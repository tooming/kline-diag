# MS41 Live Parameters (RAM)

Auto-generated from ms41_ram_params.json (RomRaider logger definition, ECU 1429861).

| ID | Name | Address | Type | Units | Formula |
|----|------|---------|------|-------|---------|
| P13 | ..TPS | 0x0000E8D7 | uint8 | % | `x*100/255` |
| E2 | ..Load | 0x0000FAFC | uint16 | mg/stroke | `x*0.0212` |
| P21 | ..IPW | 0x0000ECBC | uint16 | ms | `x*0.00534` |
| E13 | .STFT1 | 0x0000ED5C | uint16 | % | `(x-32768)*100/65535` |
| E14 | .STFT2 | 0x0000ED96 | uint16 | % | `(x-32768)*100/65535` |
| E15 | O2 Heater - Front #1 | 0x0000EDE3 | uint8 | % | `x*100/255` |
| E16 | O2 Heater - Front #2 | 0x0000EDEB | uint8 | % | `x*100/255` |
| E17 | O2 Heater - Rear #1 | 0x0000F064 | uint8 | % | `x*100/255` |
| E18 | O2 Heater - Rear #2 | 0x0000F110 | uint8 | % | `x*100/255` |
| E19 | .IdleFT1 | 0x0000ED66 | uint16 | ms | `(x-32768)*.00534` |
| E20 | .IdleFT2 | 0x0000EDA0 | uint16 | ms | `(x-32768)*.00534` |
| E21 | .LTFT1 | 0x0000ED6E | uint16 | % | `(x-32768)*100/65535` |
| E22 | .LTFT2 | 0x0000EDA8 | uint16 | % | `(x-32768)*100/65535` |
| P8 | ..RPM | 0x0000DA2A | uint16 | RPM | `x` |
| P9 | /VS | 0x0000DA63 | uint8 | km/h | `x` |
| E11 | .VANOS | 0x0000E9E6 | uint8 | KW ° | `x*0.3745` |
| E217 | ..Knock | 0x0000E98D | uint8 | ° Cor | `(x-128)*0.375` |
| P11 | ..IAT | 0x0000DA50 | uint8 | °C | `x*0.747-48` |
| P2 | ..ECT | 0x0000DA5A | uint8 | °C | `x*0.747-48` |
| P10 | ..IGN | 0x0000E989 | uint8 | °BTDC | `0.373*x-23.6` |
| E23 | /TPS_Adapt | 0x0000E8DE | int16 | % | `x*1.526E-3` |
| E24 | Knock Retard - Global | 0x0000E9D9 | uint8 | ° Cor | `(x-128)*0.375` |
| E99 | Knock Adaptation Table 1 Index** | 0x00D840 | uint8 | ° Cor | `(x-128)*0.375` |
| E100 | V_IAT | 0x00000000 | uint16 | VDC | `x*0.01952` |
| E101 | V_O2_Front #1 | 0x00000001 | uint16 | VDC | `x*0.01952` |
| E102 | V_O2_Front #2 | 0x00000002 | uint16 | VDC | `x*0.01952` |
| E103 | V_ECT | 0x00000003 | uint16 | VDC | `x*0.00487` |
| P19 | .V_TPS | 0x00000004 | uint16 | VDC | `x*0.01952` |
| E105 | V_ZSR | 0x00000005 | uint16 | VDC | `x*0.01952` |
| P18 | .V_MAF | 0x00000006 | uint16 | VDC | `x*0.01952` |
| P17 | .V_Batt | 0x00000007 | uint16 | VDC | `x*0.102` |
| E123 | V_Knock #1 | 0x00000017 | uint16 | VDC | `x*0.01952` |
| E124 | V_Knock #2 | 0x00000018 | uint16 | VDC | `x*0.01952` |
| E125 | V_O2_Rear #1 | 0x00000019 | uint16 | VDC | `x*0.01952` |
| E126 | V_O2_Rear #2 | 0x0000001A | uint16 | VDC | `x*0.01952` |
| E127 | V_FuelTankPressure | 0x0000001B | uint16 | VDC | `x*0.00488` |
| P12 | ..MAF | 0x0000DA34 | uint16 | kg/h | `x*0.25` |
| E9 | .IACV | 0x0000DA36 | uint16 | % | `x*0.00153` |
| E201 | .IACV_AlphaN | 0x0000DA38 | uint16 | % | `x*0.00153` |
| E202 | PWM_Evap | 0x0000DA56 | uint8 | % | `x*100/255` |
| E204 | Knock Sensor Cylinder 1 | 0x0000DA65 | uint8 | ? | `x` |
| E205 | Knock Sensor Cylinder 2 | 0x0000DA68 | uint8 | ? | `x` |
| E206 | Knock Sensor Cylinder 3 | 0x0000DA67 | uint8 | ? | `x` |
| E207 | Knock Sensor Cylinder 4 | 0x0000DA69 | uint8 | ? | `x` |
| E208 | Knock Sensor Cylinder 5 | 0x0000DA66 | uint8 | ? | `x` |
| E209 | Knock Sensor Cylinder 6 | 0x0000DA64 | uint8 | ? | `x` |
| E210 | STATUS_VANOS_VERSTELLWINKEL | 0x0000DAA4 | uint8 | ? | `x` |
| P24 | Atmospheric Pressure** | 0x0000DAA5 | uint8 | psi | `101.325*37/255` |
| E211 | STATUS_GEBERRAD_ADAPTION | 0x0000DB0F | uint8 | ? | `x` |
| E212 | STATUS_TANK_DIFF_DRUCK | 0x0000DB10 | uint16 | ? | `x` |
| E213 | STATUS_TIMER_TE_DIAG | 0x0000DB14 | uint16 | ? | `x` |
| E214 | STATUS_LAMBDA_COUNTER | 0x0000EDE6 | uint16 | ? | `x` |
| E215 | STATUS_TIMER_TL_SP_DTE | 0x0000F576 | uint8 | ? | `x` |
| E216 | STATUS_TIMER_NB_SP_DTE | 0x0000F578 | uint8 | ? | `x` |
| E202 | .WGDC | 0x0000DA56 | uint8 | % | `x*100/255` |
| P58 | .WBO2 | 0x0000E800 | uint8 | AFR | `x*0.05+8.25` |
| E131 | .FF % | 0x0000E801 | uint8 | % | `x*0.392` |
| E85 | .FF_IPW % | 0x0000E809 | uint8 | % | `x*0.392` |
| E86 | .FF_IGN % | 0x0000E808 | uint8 | °Crk | `(x-128)*0.373` |
| P7 | .MAP | 0x0000E806 | uint16 | kPa | `x*.01` |
| E87 | .OilP | 0x0000E803 | uint8 | psi | `x*0.6` |
| E88 | .FuelP | 0x0000E802 | uint8 | psi | `x*0.6` |
| E203 | SW - BELADUNG | 0x0000DA57 | uint8 | On/Off | `x` |
| S0 | SW - Compressor Signal | 0x0000FD18 | uint8 | On/Off | `x` |
| S1 | SW - A/C (High load) | 0x0000FD18 | uint8 | On/Off | `x` |
| S2 | SW - Theft Deterrent System | 0x0000FD18 | uint8 | On/Off | `x` |
| S3 | SW - Torque Reduction Request - Gear-Shift | 0x0000FD18 | uint8 | On/Off | `x` |
| S4 | SW - Engine Drag Torque Reduction | 0x0000FD18 | uint8 | On/Off | `x` |
| S5 | SW - Torque Reduction Request | 0x0000FD18 | uint8 | On/Off | `x` |
| S6 | SW - Full Load | 0x0000FD24 | uint8 | On/Off | `x` |
| S7 | SW - Part Load | 0x0000FD14 | uint8 | On/Off | `x` |
| S8 | SW - Closed Throttle | 0x0000FD24 | uint8 | On/Off | `!BitWise(1,x,1)` |
| S9 | SW - S_REG2 | 0x0000ED92 | uint8 | On/Off | `BitWise(8,x,1)/8` |
| S10 | SW - S_REG1 | 0x0000ED58 | uint8 | On/Off | `BitWise(8,x,1)/8` |
| S11 | SW - Trailing Throttle Fuel Cut Off | 0x0000FD14 | uint8 | On/Off | `x` |
| S12 | SW - Accel. Enrich. | 0x0000FD13 | uint8 | On/Off | `x` |
| S13 | SW - Engine Start | 0x0000FD14 | uint8 | On/Off | `x` |
| S14 | SW - Drive Engaged (AT) | 0x0000FD18 | uint8 | On/Off | `x` |
| S15 | SW - Generator | 0x0000F19A | uint8 | On/Off | `x` |
| S16 | SW - S_CAN | 0x0000FD4C | uint16 | On/Off | `if(BitWise(896,x,1)&gt;0,1,0)` |
| S17 | SW - Secondary Air Valve | 0x0000FD54 | uint8 | On/Off | `x` |
| S18 | SW - Secondary Air Pump | 0x0000FD54 | uint8 | On/Off | `x` |
| S19 | SW - Tank Ventilation Valve | 0x0000FD56 | uint8 | On/Off | `x` |
| S20 | Rear Defogger Switch | 0x0000FD53 | uint8 | On/Off | `x` |
| S22 | SW - Exhaust Flap | 0x0000FD08 | uint8 | On/Off | `x` |
| S23 | SW - S_VANOS | 0x0000FFC1 | uint8 | On/Off | `!BitWise(16,x,1)/16` |
| S24 | SW - Compressor Relay | 0x0000F141 | uint8 | On/Off | `!BitWise(32,x,1)/32` |
| S25 | SW - Fuel Pump | 0x0000FFC4 | uint8 | On/Off | `!BitWise(32,x,1)/32` |
