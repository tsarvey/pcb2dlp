# PyInstaller spec for pcb2dlp.
# Build with:  pyinstaller pcb2dlp.spec
# Produces a single-file executable in dist/.
#
# The same binary serves both the CLI (`pcb2dlp convert ...`) and the GUI
# (`pcb2dlp gui`), since both live behind src/pcb2dlp/__main__.py.

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Bundle the printer profile TOMLs (currently shipped via package-data, which
# PyInstaller does not pick up automatically).
datas = collect_data_files("pcb2dlp.printers", includes=["profiles/*.toml"])

a = Analysis(
    ["src/pcb2dlp/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Imported lazily inside subcommands; PyInstaller's static analysis
        # would otherwise miss them.
        "pcb2dlp.gui.app",
        "pcb2dlp.test_pattern",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="pcb2dlp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,  # keep a console so CLI mode prints; GUI still works on top
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
