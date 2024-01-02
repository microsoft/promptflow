# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata

datas = [('../resources/CLI_LICENSE.rtf', '.'), ('../../../../src/promptflow/NOTICE.txt', '.'),
('../../../../src/promptflow/promptflow/_sdk/data/executable/', './promptflow/_sdk/data/executable/'),
('../../../../src/promptflow-tools/promptflow/tools/', './promptflow/tools/'),
('./pf.bat', '.'), ('./pfs.bat', '.'), ('./pfazure.bat', '.'), ('./pfsvc.bat', '.')]

datas += collect_data_files('streamlit')
datas += copy_metadata('streamlit')
datas += collect_data_files('streamlit_quill')
datas += collect_data_files('promptflow')
hidden_imports = ['streamlit.runtime.scriptrunner.magic_funcs', 'win32timezone', 'promptflow']

block_cipher = None

pfcli_a = Analysis(
    ['pfcli.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pfcli_pyz = PYZ(pfcli_a.pure, pfcli_a.zipped_data, cipher=block_cipher)
pfcli_exe = EXE(
    pfcli_pyz,
    pfcli_a.scripts,
    [],
    exclude_binaries=True,
    name='pfcli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
    icon='../resources/logo32.ico',
    version="./version_info.txt",
)

coll = COLLECT(
    pfcli_exe,
    pfcli_a.binaries,
    pfcli_a.zipfiles,
    pfcli_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='promptflow',
)
