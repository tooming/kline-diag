# Operation Database

Auto-generated from operations.json. Each operation carries a graded evidence level, not a binary status.

**Grades:** verified (implemented + tested) · implemented-safe · observed (seen in a trace) · documented (in a BMW SGBD job, not yet on the wire).

**Totals:** 418 operations across 9 ECUs; {'verified': 6, 'observed': 2, 'documented': 410}; 6 usable on car.


## ABS (62 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| ABS_REGELSIMULATION | actuate | documented | gated | Ansteuern mehrerer digitaler Ausgaenge |
| DOWNLOAD_D4_STELLGLIED | actuate | documented | gated | Stellglied ansteuern ABS5 |
| DOWNLOAD_STELLGLIED | actuate | documented | gated | Stellglied ansteuern ABS5 |
| DRUCKABBAU_HA | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| DRUCKABBAU_VL | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| DRUCKABBAU_VR | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| DRUCKAUFBAU_HA | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| DRUCKAUFBAU_VL | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| DRUCKHALTEN | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| NA_ENTLUEFTUNG_LI | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| NA_ENTLUEFTUNG_RE | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| PUMPENFOERDERLEISTUNG_HA | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| PUMPENFOERDERLEISTUNG_VO | actuate | documented | gated | Steuern_Digital ansteueren u. ruecksetzen |
| STEUERN | actuate | documented | gated | Dimensions: 8 rows × 3 columns |
| STEUERN_DIGITAL | actuate | documented | gated | Parameter: 1.: E oder W,  2. bis 7.: EVVL,AVVL,EVVR,AVVR,EVH |
| TEST_D4_STELLGLIED | actuate | documented | gated | Digitale Stellglieder ansteuern ABS |
| TEST_D_STELLGLIED | actuate | documented | gated | Digitale Stellglieder ansteuern ABS5 |
| A_VENTIL_TABELLE | read | documented | gated | Dimensions: 5 rows × 2 columns |
| ABGLEICHWERTE_LESEN | read | documented | gated | Triggerschwellen der 4 Radsensoren |
| ABS_SIMULATION_3_KANAL | read | documented | gated | Simulation ABS5 |
| ABS_SIMULATION_4_KANAL | read | documented | gated | Simulation ABS5 |
| DIAGNOSE_ENDE | read | documented | gated | Diagnose beenden |
| DIAGNOSE_WEITER | read | documented | gated | Diagnose beenden |
| DOWNLOAD_FUEHLER_ALLE | read | documented | gated | Alle Ansprechschwellen u. Impulsraeder ABS5 |
| DOWNLOAD_FUEHLER_EINZELN | read | documented | gated | Ansprechschwelle u. Impulsrad ABS5 |
| DOWNLOAD_I_O_DIAGNOSE | read | documented | gated | I/O-Diagnose ABS5 |
| DOWNLOAD_STATISCH | read | documented | gated | Statischer Test der Komponenten ABS5 |
| DOWNLOAD_VAKUUM_LINIE | read | documented | gated | Befuelroutine in Fertigungslinie ABS5 |
| DOWNLOAD_VAKUUM_REPAIR | read | documented | gated | Befuelroutine in Nacharbeit ABS5 |
| E_A_STATUS | read | documented | gated | Dimensions: 2 rows × 2 columns |
| FARTMATRIX | read | documented | gated | Dimensions: 24 rows × 5 columns |
| FARTTEXTE | read | documented | gated | Dimensions: 5 rows × 2 columns |
| FORTTEXTE | read | documented | gated | Dimensions: 25 rows × 2 columns |
| FS_LESEN_KB90 | read | documented | gated | Fehlerspeicher lesen fuer ABS_MK20 mit KB90 |
| FUMWELTMATRIX | read | documented | gated | Dimensions: 24 rows × 5 columns |
| FUMWELTTEXTE | read | documented | gated | Dimensions: 2 rows × 3 columns |
| HERSTELLDATEN_LESEN | read | documented | gated | HERSTELL_Daten fuer ABSMK20 |
| IDENT | read | documented | gated | Ident-Daten fuer ABS5 |
| INFO | read | documented | gated | Information SGBD |
| INITIALISIERUNG | read | documented | gated | Init-Job fuer ABS5 |
| JOBRESULT | read | documented | gated | Dimensions: 7 rows × 2 columns |
| LIEFERANTEN | read | documented | gated | Dimensions: 27 rows × 2 columns |
| RAD_NR_TABELLE | read | documented | gated | Dimensions: 4 rows × 2 columns |
| RAEDER | read | documented | gated | Dimensions: 4 rows × 2 columns |
| STATUS_IO_LESEN | read | documented | gated | Status Eingaenge ABS5 |
| STG_TABELLE | read | documented | gated | Dimensions: 11 rows × 2 columns |
| TEST_FUEHLER_ALLE | read | documented | gated | Alle Ansprechschwellen u. Impulsraeder ABS5 |
| TEST_FUEHLER_EINZELN | read | documented | gated | Ansprechschwelle ABS5 |
| TEST_FUEHLER_IMPULS | read | documented | gated | Test Fuehler u. Impulsrad |
| TEST_I_O_DIAGNOSE | read | documented | gated | I/O-Diagnose |
| TEST_PUMPENLEISTUNG_HINTEN | read | documented | gated | Test der Pumpenfoerderleistung ABS_ASC5 |
| TEST_PUMPENLEISTUNG_VORNE | read | documented | gated | Test der Pumpenfoerderleistung ABS_ASC5 |
| TEST_STATISCH | read | documented | gated | Statischer Test der Komponenten ABS5 |
| TEST_VAKUUM_LINIE | read | documented | gated | Befuelroutine in Fertigungslinie ABS5 |
| TEST_VAKUUM_REPAIR | read | documented | gated | Befuelroutine in Nacharbeit ABS5 |
| TRIGGERSCHWELLE | read | documented | gated | Dimensions: 16 rows × 3 columns |
| DOWNLOAD_FS_RESET | write | documented | gated | Fehlerspeicher zuruecksetzen ABS5 |
| FS_INIT | write | documented | gated | Fehlerspeicher initialisieren NVRAM-Loeschen |
| FS_LESEN | write | documented | gated | Fehlerspeicher lesen fuer ABS5 High-Konzept nach Lastenheft  |
| FS_LOESCHEN | write | documented | gated | Fehlerspeicher loeschen fuer ABS5 |
| TEST_FS_SCHREIBEN | write | documented | gated | Fehlerspeicher zuruecksetzen |
| TRIG_SCHREIBEN | write | documented | gated | TRIGGERSCHWELLEN SCHREIBEN ASCMK20 |

## DME (142 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| STEUERN_* | actuate | observed | gated | Component activation (fuel pump, fan, VANOS valve, purge…);  |
| STEUERN_ABGASKLAPPE | actuate | documented | gated | Abgasklappe ansteuern |
| STEUERN_ABSPERRVENTIL | actuate | documented | gated | Absperrventil ansteuern |
| STEUERN_EKP | actuate | documented | gated | EKP-Relais ansteuern |
| STEUERN_EV_1 | actuate | documented | gated | EV  1 ansteuern |
| STEUERN_EV_2 | actuate | documented | gated | EV  2 ansteuern |
| STEUERN_EV_3 | actuate | documented | gated | EV 3 ansteuern |
| STEUERN_EV_4 | actuate | documented | gated | EV 4 ansteuern |
| STEUERN_EV_5 | actuate | documented | gated | EV  5 ansteuern |
| STEUERN_EV_6 | actuate | documented | gated | EV  6 ansteuern |
| STEUERN_KO | actuate | documented | gated | Klimakompressorrelais ansteuern |
| STEUERN_LL_STELLER | actuate | documented | gated | Leerlaufsteller ansteuern |
| STEUERN_LOSSES_VENTIL | actuate | documented | gated | Running Losses Ventil ansteuern |
| STEUERN_MIL | actuate | documented | gated | Fehlerlampe MIL ansteuern |
| STEUERN_SEK_PUMPE | actuate | documented | gated | Sekundaerluftpumpe ansteuern |
| STEUERN_SEK_VENTIL | actuate | documented | gated | Sekundaerluftventil ansteuern |
| STEUERN_TEV | actuate | documented | gated | Tankentlueftungsventil  ansteuern |
| STEUERN_VANOS | actuate | documented | gated | VANOS ansteuern |
| ABGAS_VARIANTE_LESEN | read | documented | gated | Auslesen der Abgasvariante |
| AIF_LESEN | read | documented | gated | Auslesen des Anwender-Info-Feldes |
| BETRIEBSWMATRIX | read | documented | gated | Dimensions: 28 rows × 8 columns |
| BITS | read | documented | gated | Dimensions: 14 rows × 4 columns |
| CO_ABGLEICH_LESEN | read | documented | gated | CO-Abgleich lesen |
| CO_ABGLEICH_VERSTELLEN | read | documented | gated | CO-Abgleich lesen |
| ECU_CONFIG | read | documented | gated | Ident-Daten fuer DME |
| FARTMATRIX | read | documented | gated | Dimensions: 50 rows × 17 columns |
| FARTTEXTE | read | documented | gated | Dimensions: 10 rows × 2 columns |
| FORTTEXTE | read | documented | gated | Dimensions: 52 rows × 6 columns |
| FS_LESEN | read | documented | gated | Auslesen des Fehlerspeichers |
| FS_QUICK_LESEN | read | documented | gated | Auslesen des QUICK Fehlerspeichers |
| FS_SHADOW_LESEN | read | documented | gated | Auslesen des Fehlerspeichers |
| FUMWELTTEXTE | read | documented | gated | Dimensions: 29 rows × 5 columns |
| IDENT | read | documented | gated | Ident-Daten fuer DME |
| INFO | read | documented | gated | Information SGBD |
| initialisierung | read | documented | gated | Default Init-Job |
| ISN_LESEN | read | documented | gated |  |
| JOBRESULT | read | documented | gated | Dimensions: 8 rows × 2 columns |
| LESEN_SYSTEMCHECK_LAUFUNRUHE | read | documented | gated | Systemcheck Laufunruhe lesen |
| LESEN_SYSTEMCHECK_SEK_LUFT | read | documented | gated | Systemcheck  Sekundaerluft stoppen |
| LESEN_SYSTEMCHECK_SONDENHEIZUNG | read | documented | gated | Systemcheck Lambdasondenheizung lesen |
| LESEN_SYSTEMCHECK_TANK_LECK | read | documented | gated | Systemcheck Tankentlueftungssystem Leckdiagnose lesen |
| LESEN_SYSTEMCHECK_TEV_FUNC | read | documented | gated | Systemcheck TEV Functionalcheck lesen |
| LESEN_TANK_LECK | read | documented | gated | Systemcheck Tankentlueftungssystem Leckdiagnose lesen |
| NULLEINSTEXTE | read | documented | gated | Dimensions: 4 rows × 3 columns |
| PRUEFSTEMPEL_LESEN | read | documented | gated | Auslesen des Pruefstempels |
| RAM_LESEN | read | documented | gated | Beliebige RAM - Zellen auslesen |
| ram_read | read | verified | yes | Read-only RAM via address list |
| FS_LESEN | read | verified | yes | Read fault memory |
| IDENT | read | verified | yes | ECU identification |
| STATUS_* | read | verified | yes | MS41 status/live block |
| ROM_LESEN | read | documented | gated | Beliebige EPROM - Zellen auslesen |
| START_SYSTEMCHECK_LAUFUNRUHE | read | documented | gated | Systemcheck Laufunruhe starten |
| START_SYSTEMCHECK_SEK_LUFT | read | documented | gated | Systemcheck  Sekundaerluft starten |
| START_SYSTEMCHECK_SONDENHEIZUNG | read | documented | gated | Systemcheck Lambdasondenheizung starten |
| START_SYSTEMCHECK_TANK_LECK | read | documented | gated | Systemcheck Tankentlueftungssystem Leckdiagnose starten |
| START_SYSTEMCHECK_TEV_FUNC | read | documented | gated | Systemcheck TEV Functionalcheck starten |
| STATUS_1_OR_2_KAT | read | documented | gated | Abfrage ueber Konfigurationsbyte ob MONO oder Stereo-Lambdar |
| STATUS_ADD | read | documented | gated | ADD-Signal |
| STATUS_ADD_2 | read | documented | gated | ADD-Signal Bank 2 |
| STATUS_AN_LUFTTEMPERATUR | read | documented | gated | Ansauglufttemperatur auslesen |
| STATUS_ATM_DRUCKSENSOR | read | documented | gated | Atmosp.drucksensor |
| STATUS_DIGITAL | read | documented | gated | Status Schalteingaenge |
| STATUS_DKP | read | documented | gated | Drosselklappenstellung  auslesen |
| STATUS_DKP_VOLT | read | documented | gated | Drosselklappenstellung  auslesen |
| STATUS_EINSPRITZZEIT | read | documented | gated | Wert Einspritzzeit auslesen |
| STATUS_FLAG_BELADUNG | read | documented | gated | Auslesen des Statusflags AKF Beladung |
| STATUS_GESCHWINDIGKEIT | read | documented | gated | Fahrzeuggeschwindigkeit |
| STATUS_H_SONDE | read | documented | gated | Lambdasondenheizung  1  auslesen |
| STATUS_H_SONDE_2 | read | documented | gated | Lambdasondenheizung  2  auslesen |
| STATUS_INT | read | documented | gated | INT-Signal |
| STATUS_INT_2 | read | documented | gated | INT-Signal Bank 2 |
| STATUS_K_MW_1 | read | documented | gated | Wert Ubat auslesen |
| STATUS_K_MW_2 | read | documented | gated | Wert Ubat auslesen |
| STATUS_K_MW_3 | read | documented | gated | Wert Ubat auslesen |
| STATUS_K_MW_4 | read | documented | gated | Wert Ubat auslesen |
| STATUS_K_MW_5 | read | documented | gated | Wert Ubat auslesen |
| STATUS_K_MW_6 | read | documented | gated | Wert Ubat auslesen |
| STATUS_KLOPF_ADC1 | read | documented | gated | ADC Spannung Klopfsensor 1 |
| STATUS_KLOPF_ADC2 | read | documented | gated | ADC Spannung Klopfsensor 2 |
| STATUS_L_SONDE | read | documented | gated | Spannug Lambdasonde vor KAT auslesen |
| STATUS_L_SONDE_2 | read | documented | gated | Spannug Lambdasonde vor KAT auslesen Sonde 2 |
| STATUS_L_SONDE_2_H | read | documented | gated | Spannug Lambdasonde vor KAT auslesen Sonde 2 |
| STATUS_L_SONDE_H | read | documented | gated | Spannug Lambdasonde vor KAT auslesen |
| STATUS_LAMBDA_ADD_1 | read | documented | gated | ADD-Signal |
| STATUS_LAMBDA_ADD_2 | read | documented | gated | ADD-Signal Bank 2 |
| STATUS_LAMBDA_COUNTER | read | documented | gated | Counter fuer die Einschaltbedingung Lambdasonde |
| STATUS_LAMBDA_INTEGRATOR_1 | read | documented | gated | INT-Signal |
| STATUS_LAMBDA_INTEGRATOR_2 | read | documented | gated | INT-Signal Bank 2 |
| STATUS_LAMBDA_MUL_1 | read | documented | gated | MUL-Signal |
| STATUS_LAMBDA_MUL_2 | read | documented | gated | MUL-Signal Bank 2 |
| STATUS_LAST | read | documented | gated | Wert Last  auslesen |
| STATUS_LDP_PERIODENDAUER | read | documented | gated | auslesen |
| STATUS_LDP_START | read | documented | gated | auslesen |
| STATUS_LL_LUFTBEDARF | read | documented | gated | Luftbedarf LL - Steller |
| STATUS_LL_REGLER | read | documented | gated | Wert LL-REGLER auslesen |
| STATUS_LMM | read | documented | gated | Wert Luftmasse  auslesen |
| STATUS_LMM_MASSE | read | documented | gated | Wert Luftmasse  auslesen |
| STATUS_LMM_VOLT | read | documented | gated | HLM Spannung |
| STATUS_LS_NKAT_SIGNAL_1 | read | documented | gated | Spannug Lambdasonde vor KAT auslesen |
| STATUS_LS_NKAT_SIGNAL_2 | read | documented | gated | Spannug Lambdasonde vor KAT auslesen Sonde 2 |
| STATUS_LS_VKAT_HEIZUNG_TV_1 | read | documented | gated | Lambdasondenheizung  1  auslesen |
| STATUS_LS_VKAT_HEIZUNG_TV_2 | read | documented | gated | Lambdasondenheizung  2  auslesen |
| STATUS_LS_VKAT_SIGNAL_1 | read | documented | gated | Spannug Lambdasonde vor KAT auslesen |
| STATUS_LS_VKAT_SIGNAL_2 | read | documented | gated | Spannug Lambdasonde vor KAT auslesen Sonde 2 |
| STATUS_MOTORDREHZAHL | read | documented | gated | Motordrehzahl auslesen |
| STATUS_MOTORTEMPERATUR | read | documented | gated | Motortemperatur auslesen |
| STATUS_MUL | read | documented | gated | MUL-Signal |
| STATUS_MUL_2 | read | documented | gated | MUL-Signal Bank 2 |
| STATUS_NW_IST_POSITION | read | documented | gated | Wert Nockenwellenposition  auslesen |
| STATUS_NW_POSITION | read | documented | gated | Wert Nockenwellenposition  auslesen |
| STATUS_SYSTEMCHECK_LAUFUNRUHE | read | documented | gated | Systemcheck Laufunruhe lesen |
| STATUS_TANK_DIFF_DRUCK | read | documented | gated | Tank Differenzdruck |
| STATUS_TANKDRUCKSENSOR | read | documented | gated | Tankdrucksensor |
| STATUS_TAST_LL_STELLER | read | documented | gated | Wert Tastverhaeltnis LL-Steller auslesen |
| STATUS_TEV_TAST | read | documented | gated | Tank Differenzdruck |
| STATUS_TIMER_NB_SP_DTE | read | documented | gated | Timer Spuelzeit im Normalbetrieb zur Freigabe DTE |
| STATUS_TIMER_TE_DIAG | read | documented | gated | Status TIMER TE-Diagnose |
| STATUS_TIMER_TL_SP_DTE | read | documented | gated | Timer Spuelzeit im Normalbetrieb zur Freigabe DTE |
| STATUS_UBATT | read | documented | gated | Batteriespannung |
| STATUS_VANOS_FRUEH_VERST_ZEIT | read | documented | gated | Wert Vanos Verstellzeit Frueh  auslesen |
| STATUS_VANOS_SPAET_VERST_ZEIT | read | documented | gated | Wert Vanos Verstellzeit Spaet  auslesen |
| STATUS_VANOS_VERSTELLWINKEL | read | documented | gated | Wert VANOS_VERSTELLWINKEL auslesen |
| STATUS_ZSR | read | documented | gated | ZSR Spannung |
| STATUS_ZUENDWINKEL | read | documented | gated | Wert Zuendwinkel  auslesen |
| STOP_SYSTEMCHECK_LAUFUNRUHE | read | documented | gated | Systemcheck Laufunruhe stoppen |
| STOP_SYSTEMCHECK_SEK_LUFT | read | documented | gated | Systemcheck  Sekundaerluft stoppen |
| STOP_SYSTEMCHECK_SONDENHEIZUNG | read | documented | gated | Systemcheck Lambdasondenheizung stoppen |
| STOP_SYSTEMCHECK_TANK_LECK | read | documented | gated | Systemcheck Tankentlueftungssystem Leckdiagnose stoppen |
| STOP_SYSTEMCHECK_TEV_FUNC | read | documented | gated | Systemcheck TEV Functionalcheck starten |
| ADAP_SELEKTIV_LOESCHEN | write | documented | gated | Adaptionen selektiv loeschen |
| ADAPT_LOESCHEN | write | documented | gated | Adaptionen loeschen |
| FS_LOESCHEN | write | verified | yes | Clear fault memory (has rollback snapshot) |
| CO_ABGLEICH_PROGRAMMIEREN | write | documented | gated | CO-Abgleich programmieren |
| DIAGNOSE_ENDE | write | documented | gated | Loeschen des Fehlerspeichers |
| EDIC_RESET | write | documented | gated | EDIC-Reset |
| ADAP_SELEKTIV_LOESCHEN | write | observed | gated | Selective adaptation erase — opcode 0x43+mask confirmed by T |
| FS_LOESCHEN | write | documented | gated | Loeschen des Fehlerspeichers |
| PRUEFSTEMPEL_SCHREIBEN | write | documented | gated | Beschreiben des Pruefstempels Es muessen immer alle drei Arg |
| STATUS_CODIER_CHECKSUMME | write | documented | gated | Codier - Checksumme abfragen |
| STATUS_GEBERRAD_ADAPTION | write | documented | gated | Geberradadaption |
| UPROG_AUS | write | documented | gated | Programmierspannung ausschalten |
| UPROG_EIN | write | documented | gated | Programmierspannung einschalten |

## EWS (59 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| STEUERN_DIGITAL | actuate | documented | gated | Ansteuern / Vorgeben digitaler Stati der EWS3 |
| STEUERN_EWS4_SK | actuate | documented | gated | SK in das EWS4.3 Steuergeraet schreiben |
| STEUERN_SELBSTTEST | actuate | documented | gated | Schreibzugriff auf den Transponder via EWS-SG |
| BITS | read | documented | gated | Dimensions: 9 rows × 3 columns |
| C_AZCS_LESEN | read | documented | gated | Read out ADDITIONAL ZCS data from Customer-data area |
| C_FG_LESEN | read | documented | gated | Auslesen der Fahrgestellnummer aus der EWS |
| DIAGNOSE_ENDE | read | documented | gated | Diagnose beenden |
| DIAGNOSE_FORTSETZEN | read | documented | gated | Diagnose mit EWS3 aufrecht erhalten |
| FARTTEXTE | read | documented | gated | Dimensions: 2 rows × 2 columns |
| FDETAILSTRUKTUR | read | documented | gated | Dimensions: 3 rows × 2 columns |
| FGNR_LESEN | read | documented | gated | Auslesen der Fahrgestellnummer aus der EWS |
| FORTTEXTE | read | documented | gated | Dimensions: 49 rows × 2 columns |
| HDETAILSTRUKTUR | read | documented | gated | Dimensions: 3 rows × 2 columns |
| HERSTELLDATEN_LESEN | read | documented | gated | Auslesen der Herstelldaten der EWS3 |
| HORTTEXTE | read | documented | gated | Dimensions: 1 rows × 2 columns |
| IDENT | read | documented | gated | Identdaten |
| IDETAILSTRUKTUR | read | documented | gated | Dimensions: 3 rows × 2 columns |
| INFO | read | documented | gated | Information SGBD |
| INITIALISIERUNG | read | documented | gated | Init-Job fuer EWS3 automatischer Aufruf beim ersten Zugriff  |
| IORTTEXTE | read | documented | gated | Dimensions: 7 rows × 2 columns |
| ISN_LESEN | read | documented | gated | Auslesen der ISN-Nummer aus der EWS |
| JOBRESULT | read | documented | gated | Dimensions: 13 rows × 2 columns |
| JOBRESULTEXTENDED | read | documented | gated | Dimensions: 1 rows × 2 columns |
| KD_DATEN_LESEN | read | documented | gated | Auslesen der Kundendienstdaten aus der EWS |
| LIEFERANTEN | read | documented | gated | Dimensions: 77 rows × 2 columns |
| PASSWORT_LESEN | read | documented | gated | Auslesen des Passworts aus der EWS |
| PRUEFSTEMPEL_LESEN | read | documented | gated | Auslesen des Pruefstempels |
| ROVERPARTNUMPREFIX | read | documented | gated | Dimensions: 21 rows × 2 columns |
| SCHL_DATEN_LESEN | read | documented | gated | Auslesen der Schluesseldaten aus der EWS |
| SCHL_SPERREN_FREIGEBEN | read | documented | gated | Schluessel freischalten und sperren |
| SCHLUESSEL_DATEN_0_BIS_3_LESEN | read | documented | gated | Auslesen der Schluesseldaten aus der EWS |
| STATUS_EWS | read | documented | gated | Informationen über das EWS4 Steuergerät anzeigen |
| STATUS_EWS4_SK | read | documented | gated | EWS4.4 Steuergeraet SK lesen |
| STATUS_LESEN | read | documented | gated | Stati der EWS |
| STATUS_SW_VERSION | read | documented | gated | Ermittlung der internen SG-SW |
| WECHSELCODE_SYNC_DME | read | documented | gated | Wechselcodesynchronisation EWS 3 - DME anstossen |
| C_AZCS_AUFTRAG | write | documented | gated | Write the Rover Additional ZCS into customer-data block |
| C_C_AUFTRAG | write | documented | gated | Codierdaten schreiben und verifizieren |
| C_C_LESEN | write | documented | gated | Codierdaten lesen |
| C_FG_AUFTRAG | write | documented | gated | Schreiben der 17-stelligen Fahrgestellnummer (incl. Pruefzif |
| C_ZCS_AUFTRAG | write | documented | gated | Schreiben des Zentralen Codierschluessels in die KD-Daten |
| C_ZCS_LESEN | write | documented | gated | Auslesen des Zentralen Codierschluessels aus KD-Daten |
| COD_EWS_DME3_SCHREIBEN | write | documented | gated | Schreiben der Schaerfzeit der WS |
| COD_LESEN | write | documented | gated | Auslesen der Codierdaten der EWS3 |
| COD_ZEIT_WS_SCHREIBEN | write | documented | gated | Schreiben der Schaerfzeit der WS |
| FGNR_K_SCHREIBEN | write | documented | gated | Schreiben der 7-stelligen Fahrgestellnummer |
| FGNR_SCHREIBEN | write | documented | gated | Schreiben der 17-stelligen Fahrgestellnummer inkl. PZ |
| FS_LESEN | write | documented | gated | Fehlerspeicher lesen Low-Konzept nach Lastenheft Codierung/D |
| FS_LOESCHEN | write | documented | gated | Fehlerspeicher loeschen |
| HERSTELLDATEN_SCHREIBEN | write | documented | gated | Beschreiben der Herstellerdaten |
| ISN_SCHREIBEN | write | documented | gated | Schreiben der ISN-Nummer in die EWS |
| KD_DATEN_SCHREIBEN | write | documented | gated | Schreiben der Kundendienst in die EWS |
| KD_INIT | write | documented | gated | Schreiben der VK-Daten in das EWS |
| KD_INIT_R50 | write | documented | gated | Schreiben der VK-Daten in das EWS |
| KD_POLSTER_LACK_SCHREIBEN | write | documented | gated | Schreiben der Kundendienstdaten POLSTER und LACK in die EWS3 |
| PASSWORT_SCHREIBEN | write | documented | gated | Schreiben des Passworts in die EWS |
| PRUEFSTEMPEL_SCHREIBEN | write | documented | gated | Beschreiben des Pruefstempels |
| SCHL_DATEN_SCHREIBEN | write | documented | gated | Schreiben der Schluesseldaten in die EWS |
| ZCS_LESEN | write | documented | gated | Auslesen des Zentralen Codierschluessels aus KD-Daten |

## FBZV (16 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| STEUERN_TEST_EMPFANG | actuate | documented | gated | Steuern Selbsttestfunktion HF-Empfang |
| DIAGNOSE_AUFRECHT | read | documented | gated | Aufrechterhalten Kommuniktion mit SG |
| DIAGNOSE_ENDE | read | documented | gated | Beendet Kommuniktion mit SG DUMMY |
| FORTTEXTE | read | documented | gated | Dimensions: 4 rows × 2 columns |
| FS_LESEN | read | documented | gated | Fehlerspeicher Sg lesen und auswerten Pro Fehler wird ein Er |
| IDENT | read | documented | gated | Identifizierung SG lesen |
| INFO | read | documented | gated | Information SGBD |
| INITIALISIERUNG | read | documented | gated | Default Initialisierung der Kommunikation via EDIC |
| JOBRESULT | read | documented | gated | Dimensions: 8 rows × 2 columns |
| LIEFERANTEN | read | documented | gated | Dimensions: 27 rows × 2 columns |
| PRUEFSTEMPEL_LESEN | read | documented | gated | Auslesen des Pruefstempels |
| STATUS_KLEMME_R_EIN | read | documented | gated | Status Klemme R abfragen |
| CODE_LESEN | write | documented | gated | Auslesen der Codierdaten |
| CODE_SCHREIBEN | write | documented | gated | Schreiben der Codierdaten |
| FS_LOESCHEN | write | documented | gated | Fehlerspeicher loeschen |
| PRUEFSTEMPEL_SCHREIBEN | write | documented | gated | Beschreiben des Pruefstempels |

## IHKA (41 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| DIAGNOSE_TESTBIT | actuate | documented | gated | Ansteuern des Diagnosetest-Bits |
| KOMPRESSOR_SPERRE | actuate | documented | gated | Ansteuern des Geblaeses |
| STEUERN_DME_AC | actuate | documented | gated | Ansteuern des DME-AC-Signals |
| STEUERN_DME_KO | actuate | documented | gated | Ansteuern des DME-KO-Signals |
| STEUERN_GEBLAESE | actuate | documented | gated | Ansteuern des Geblaeses |
| STEUERN_KLIMAKOMPRESSOR | actuate | documented | gated | Ansteuern des Klimakompressors |
| STEUERN_LWS_ABSPERRVENTIL | actuate | documented | gated | Ansteuern des Absperrventils des Latentwaermespeichers |
| STEUERN_LWS_UMSCHALTVENTIL | actuate | documented | gated | Ansteuern des Umschaltventils |
| STEUERN_MOTOR_KLAPPENPOSITION | actuate | documented | gated | Ansteuern der Schrittmotoren |
| STEUERN_RELAIS_HECKSCHEIBE | actuate | documented | gated | Ansteuern des Heckscheibenrelais |
| STEUERN_RELAIS_ZUSATZLUEFTER | actuate | documented | gated | Ansteuern des Zusatzluefterrelais |
| STEUERN_SPERRVENTIL | actuate | documented | gated | Ansteuern des Sperrventils |
| STEUERN_SPRITZDUESENHEIZUNG | actuate | documented | gated | Ansteuern des Spritzduesenheizung |
| STEUERN_STANDHEIZUNG | actuate | documented | gated | Ansteuern der Standheizung |
| STEUERN_WASSERVENTIL | actuate | documented | gated | Ansteuern des linken und rechten Wasserventils |
| STEUERN_ZUSATZWASSERPUMPE | actuate | documented | gated | Ansteuern der Zusatzwasserpumpe |
| DIAGNOSE_AUFRECHT | read | documented | gated | Diagnosemode aufrechterhalten |
| DIAGNOSE_ENDE | read | documented | gated | Diagnose beenden |
| DISPLAY_TEST | read | documented | gated | Einschalten eines Testmusters in den Displays Es muss der Di |
| EICHLAUF_STARTEN | read | documented | gated | Anstossen der internen Eichlaufroutine |
| FORTTEXTE | read | documented | gated | Dimensions: 48 rows × 2 columns |
| FS_LESEN | read | documented | gated | Fehlerspeicher lesen |
| IDENT | read | documented | gated | Identifikation |
| INFO | read | documented | gated | Information SGBD |
| INITIALISIERUNG | read | documented | gated | Kommunikationsparameter |
| JOBRESULT | read | documented | gated | Dimensions: 8 rows × 2 columns |
| LIEFERANTEN | read | documented | gated | Dimensions: 30 rows × 2 columns |
| PRUEFSTEMPEL_LESEN | read | documented | gated | Auslesen des Pruefstempels |
| SLEEP_MODE | read | documented | gated | SG in Power-Down-Mode versetzen |
| SPEICHER_LESEN | read | documented | gated | Lesen des internen Speichers |
| STATUS_ANALOGEINGAENGE | read | documented | gated | Status lesen |
| STATUS_BEDIENTEIL | read | documented | gated | Status lesen |
| STATUS_IO | read | documented | gated | Status lesen |
| STATUS_MOTOR_KLAPPENPOSITION | read | documented | gated | Status lesen |
| STATUS_REGLERGROESSEN | read | documented | gated | Status lesen |
| CODIERUNG_LESEN | write | documented | gated | Auslesen der Codierdaten |
| CODIERUNG_SCHREIBEN | write | documented | gated | Codierdaten Schreiben |
| EEPROM_SCHREIBEN | write | documented | gated | Beschreiben des internen Speichers |
| FS_LOESCHEN | write | documented | gated | Fehlerspeicher loeschen |
| PRUEFSTEMPEL_SCHREIBEN | write | documented | gated | Beschreiben des Pruefstempels |
| RAM_SCHREIBEN | write | documented | gated | Beschreiben des internen Speichers |

## IKE (49 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| SELBSTTEST | actuate | documented | gated | SG - Selbsttest ausloesen |
| STEUERN_ANZEIGE | actuate | documented | gated | Anzeigenkomponenten steuern |
| STEUERN_EISWARNUNG | actuate | documented | gated | Anzeigenkomponenten steuern |
| STEUERN_GONG | actuate | documented | gated | Gong1, Gong2 oder Gong3 steuern |
| STEUERN_GONG123 | actuate | documented | gated | Gong1, Gong2 und Gong3 nacheinander fuer 2 sec. ansteuern |
| STEUERN_GONG3 | actuate | documented | gated | Anzeigenkomponenten steuern |
| STEUERN_LEUCHTE | actuate | documented | gated | Leuchten in der Anzeigeeinheit steuern |
| STEUERN_LICHTSUMMER | actuate | documented | gated | Anzeigenkomponenten steuern |
| STEUERN_SELBSTTEST | actuate | documented | gated | SG - Selbsttest ausloesen |
| STEUERN_TACHO_A | actuate | documented | gated | TACHO_A steuern |
| AIF_DATUM_FZ_LESEN | read | documented | gated | Auslesen des Herstelldatums des FZ |
| AIF_FG_NR_LESEN | read | documented | gated | Auslesen der Fahrgestellnummer |
| AIF_GWSZ_LESEN | read | documented | gated | Gesamtwegstreckenzaehlers aus Anwenderinfofeld auslesen |
| AIF_SIA_DATEN_LESEN | read | documented | gated | Anwenderinfofeld Block 3 auslesen |
| AIF_ZENTRALCODE_LESEN | read | documented | gated | Anwenderinfofeld Block 4 auslesen |
| DIAGNOSE_AUFRECHT | read | documented | gated | Fortsetzen der Diagnose |
| DIAGNOSE_ENDE | read | documented | gated | Diagnose beenden |
| EEPROM_LESEN | read | documented | gated |  |
| FARTTEXTE | read | documented | gated | Dimensions: 8 rows × 2 columns |
| FORTTEXTE | read | documented | gated | Dimensions: 26 rows × 2 columns |
| FS_LESEN | read | documented | gated | Fehlerspeicherinhalt aus SG lesen |
| GETRIEBETYPEN | read | documented | gated | Dimensions: 4 rows × 2 columns |
| GWSZ_MINUS_OFFSET_LESEN | read | documented | gated | Gesamtwegstreckenzaehler aus Anwenderinfofeld auslesen und O |
| IDENT | read | documented | gated | Default ident job |
| INFO | read | documented | gated | Information SGBD |
| INITIALISIERUNG | read | documented | gated | Init-Job fuer IKE |
| JOBRESULT | read | documented | gated | Dimensions: 8 rows × 2 columns |
| KOMPONENTEN | read | documented | gated | Dimensions: 11 rows × 2 columns |
| LEUCHTEN1 | read | documented | gated | Dimensions: 11 rows × 2 columns |
| LEUCHTEN2 | read | documented | gated | Dimensions: 11 rows × 2 columns |
| LEUCHTEN3 | read | documented | gated | Dimensions: 10 rows × 2 columns |
| LIEFERANTEN | read | documented | gated | Dimensions: 27 rows × 2 columns |
| PROD_DATUM_LESEN | read | documented | gated |  |
| PRUEFSTEMPEL_LESEN | read | documented | gated | Default pruefstempel_lesen job |
| RAM_LESEN | read | documented | gated |  |
| FS_LESEN | read | verified | yes | Read cluster fault memory |
| ROM_LESEN | read | documented | gated |  |
| SLEEP_MODE | read | documented | gated | SG in Sleep-Mode versetzen |
| STATUS_ANALOG_LESEN | read | documented | gated | Spezielle Eingaenge lesen |
| STATUS_IO_LESEN | read | documented | gated | Eingangs- und Ausgangsstati lesen |
| STATUS_TANKINHALT_LESEN | read | documented | gated | Tankinhalt lesen |
| FS_LOESCHEN | write | documented | gated | Fehlerspeicher loeschen |
| GWSZ_RESET | write | documented | gated |  |
| SIA_RESET | write | documented | gated | Reset service interval (opcode unconfirmed) |
| PRUEFSTEMPEL_SCHREIBEN | write | documented | gated | Beschreiben des Pruefstempels |
| RESET_IKE | write | documented | gated | SG Reset ausloesen |
| SIA_RESET | write | documented | gated | Ruecksetzen der Service-Intervall-Anzeige |
| SIARESET | write | documented | gated | Dimensions: 4 rows × 2 columns |
| SOFTWARE_RESET | write | documented | gated | Kombi loest selbststaendig einen Reset aus |

## LCM (27 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| STATUS_VORGEBEN | actuate | documented | gated | Ansteuern mehrerer (maximal 15) digitalen Ein- Ausgaenge |
| STEUERN | actuate | documented | gated | Dimensions: 65 rows × 3 columns |
| STEUERN_DIMMER | actuate | documented | gated | STEUERN_DIMMER job |
| STEUERN_LWR_POTI | actuate | documented | gated | STEUERN_LWR_POTI job |
| DIAGNOSE_ENDE | read | documented | gated | DIAGNOSE_ENDE job |
| DIAGNOSE_WEITER | read | documented | gated | DIAGNOSE_WEITER job |
| FG_NR_LESEN | read | documented | gated | Default FG_NR_LESEN job |
| FORTTEXTE | read | documented | gated | Dimensions: 37 rows × 2 columns |
| FS_LESEN | read | documented | gated | fs_lesen job |
| FS_ZAEHLER | read | documented | gated | Default fs_zaehler job |
| HERSTELLER_LESEN | read | documented | gated | Default ident job |
| IDENT | read | documented | gated | Default ident job |
| INFO | read | documented | gated | Information SGBD |
| INITIALISIERUNG | read | documented | gated | Default init job |
| IORTTEXTE | read | documented | gated | Dimensions: 32 rows × 2 columns |
| IS_LESEN | read | documented | gated | infospeicherlesen job |
| JOBRESULT | read | documented | gated | Dimensions: 8 rows × 2 columns |
| LIEFERANTEN | read | documented | gated | Dimensions: 27 rows × 2 columns |
| SIA_LESEN | read | documented | gated | Default SIA_LESEN job |
| SPEICHER_LESEN | read | documented | gated | Auslesen des Speicherinhaltes |
| STATUS_LESEN | read | documented | gated | STATUS_LESEN job |
| CODIERUNG_BLOCK_1_LESEN | write | documented | gated | Default CODIERUNG_BLOCK_1_LESEN job |
| CODIERUNG_LESEN | write | documented | gated | Default CODIERUNG_LESEN job |
| CODIERUNG_LESEN_ALLES | write | documented | gated | Default CODIERUNG_LESEN_ALLES job |
| FS_LOESCHEN | write | documented | gated | Default FS_LOESCHEN job |
| KALTABFRAGE_SCHREIBEN | write | documented | gated | Default KALTABFRAGE_SCHREIBEN job |
| SPEICHER_SCHREIBEN | write | documented | gated | Schreiben des Speicherinhaltes |

## PDC (19 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| STEUERN_IO_STATUS | actuate | documented | gated | Ansteuern von den I/O Stati |
| STEUERN_WEG_V | actuate | documented | gated | Ansteuern der Abstaende und der Geschwindigkeit |
| DIAGNOSE_ENDE | read | documented | gated | Diagnose beenden |
| DIAGNOSE_WEITER | read | documented | gated | Diagnose aufrechterhalten |
| FARTMATRIX | read | documented | gated | Dimensions: 13 rows × 17 columns |
| FARTTEXTE | read | documented | gated | Dimensions: 14 rows × 2 columns |
| FORTTEXTE | read | documented | gated | Dimensions: 14 rows × 2 columns |
| IDENT | read | documented | gated | Ident-Daten fuer PDC |
| INFO | read | documented | gated | Information SGBD |
| INITIALISIERUNG | read | documented | gated | Init-Job fuer PDC |
| IO_STATUS | read | documented | gated | Dimensions: 8 rows × 2 columns |
| JOBRESULT | read | documented | gated | Dimensions: 5 rows × 2 columns |
| LIEFERANTEN | read | documented | gated | Dimensions: 27 rows × 2 columns |
| SG_STATUS | read | documented | gated | Dimensions: 9 rows × 2 columns |
| STATUS_AUSSCHWINGZEIT_LESEN | read | documented | gated | AUSSCHWINGZEIT lesen |
| STATUS_IO_LESEN | read | documented | gated | Status der I/O Ports lesen |
| STATUS_WEG_V_MODE_LESEN | read | documented | gated | Status des Steuergeraets lesen |
| FS_LESEN | write | documented | gated | Fehlerspeicher lesen High-Konzept nach Lastenheft Codierung/ |
| FS_LOESCHEN | write | documented | gated | Fehlerspeicher loeschen |

## RADIO (3 operations)

| Job | Kind | Grade | Car-usable | Description |
|-----|------|-------|-----------|-------------|
| INITIALISIERUNG | read | documented | gated | Initialisierung und Kommunikationsparameter |
| KONZEPT_TABELLE | read | documented | gated | Dimensions: 4 rows × 2 columns |
| IDENTIFIKATION | write | documented | gated | !!! nur in Gruppendatei verwenden !!! Zuordnung von ADR_VAR_ |
