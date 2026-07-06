# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds the desktop app frozen and self-contained.

  pyinstaller --noconfirm kline-diag.spec

Produces `dist/KlineDiag.exe` on Windows and `dist/KlineDiag.app` on macOS.
The read-only tables + ui.html are bundled as data (found via
paths.resource_dir() -> sys._MEIPASS at runtime); writable data (logs,
backups) goes to a per-user folder via paths.data_dir().
"""
import sys

# Read-only resources the running app loads by name from resource_dir().
datas = [(f, '.') for f in (
    'ui.html',
    'e39_body_dtc_en.json',
    'e87_dtc.json',
    'gear_ratios.json',
    'ms41_dtc.json',
    'ms41_ram_params.json',
    'ms43_ram_params.json',
    'operations.json',
    'reference_ms43_ds2_commands.ts',
)]

# diag_ui pulls most of these in via endpoint-level imports; list them so
# PyInstaller's static analysis can't miss any.
hiddenimports = [
    'diag_ui', 'power_diag', 'ds2_diag', 'transaction', 'coding',
    'operations', 'dme_registry', 'verification', 'snapshot', 'adaptations',
    'actuators', 'compare', 'correlate', 'plugins', 'vehicle_profiles',
    'trace', 'dev_console', 'paths',
]
if sys.platform.startswith('win'):
    hiddenimports += ['serial', 'serial.tools.list_ports']

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    # onedir + BUNDLE -> a proper .app (onefile .app clashes with Gatekeeper)
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True,
        name='KlineDiag', debug=False, strip=False, upx=False,
        console=False, disable_windowed_traceback=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
                   name='KlineDiag')
    app = BUNDLE(
        coll,
        name='KlineDiag.app',
        icon='app.icns',
        bundle_identifier='com.tooming.klinediag',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.13',
            'CFBundleShortVersionString': '1.0',
        },
    )
else:
    # Windows/Linux: single-file executable, easiest to hand over
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name='KlineDiag', debug=False, bootloader_ignore_signals=False,
        strip=False, upx=False, runtime_tmpdir=None,
        console=False, disable_windowed_traceback=False,
        icon='app.ico',
    )
