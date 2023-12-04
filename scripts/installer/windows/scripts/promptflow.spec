# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata

datas = [('../resources/CLI_LICENSE.rtf', '.'), ('../../../../src/promptflow/NOTICE.txt', '.'),
('../../../../src/promptflow/promptflow/_sdk/data/executable/', './promptflow/_sdk/data/executable/'),
('../../../../src/promptflow-tools/promptflow/tools/', './promptflow/tools/'),
('./pf.cmd', '.'), ('./pfs.cmd', '.'), ('./pfazure.cmd', '.')]

datas += collect_data_files('streamlit')
datas += copy_metadata('streamlit')
datas += collect_data_files('streamlit_quill')
datas += collect_data_files('promptflow')
hidden_imports = ['streamlit.runtime.scriptrunner.magic_funcs']

service_hidden_imports = ['win32timezone']

block_cipher = None

main_a = Analysis(
    ['main.py'],
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
main_pyz = PYZ(main_a.pure, main_a.zipped_data, cipher=block_cipher)
main_exe = EXE(
    main_pyz,
    main_a.scripts,
    [],
    exclude_binaries=True,
    name='main',
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
    icon='../resources/logo32.ico',
    version="./version_info.txt",
)

pfsvc_a = Analysis(
    ['pfsvc.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=service_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pfsvc_pyz = PYZ(pfsvc_a.pure, pfsvc_a.zipped_data, cipher=block_cipher)
pfsvc_exe = EXE(
    pfsvc_pyz,
    pfsvc_a.scripts,
    [],
    exclude_binaries=True,
    name='pfsvc',
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
    icon='../resources/logo32.ico',
    version="./version_info.txt",
)

coll = COLLECT(
    main_exe,
    main_a.binaries,
    main_a.zipfiles,
    main_a.datas,
    pfsvc_exe,
    pfsvc_a.binaries,
    pfsvc_a.zipfiles,
    pfsvc_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='promptflow',
)
