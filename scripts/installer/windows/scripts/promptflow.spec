# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata

datas = [('../resources/CLI_LICENSE.rtf', '.'), ('../../../../src/promptflow/NOTICE.txt', '.'),
('../../../../src/promptflow/promptflow/_sdk/data/executable/', './promptflow/_sdk/data/executable/')]

datas += collect_data_files('streamlit')
datas += copy_metadata('streamlit')
datas += collect_data_files('streamlit_quill')
datas += collect_data_files('promptflow')
hidden_imports = ['streamlit.runtime.scriptrunner.magic_funcs', 'promptflow-tools']

service_hidden_imports = ['win32timezone']

block_cipher = None

pf_a = Analysis(
    ['pf.py'],
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
pf_pyz = PYZ(pf_a.pure, pf_a.zipped_data, cipher=block_cipher)
pf_exe = EXE(
    pf_pyz,
    pf_a.scripts,
    [],
    exclude_binaries=True,
    name='pf',
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


pfazure_a = Analysis(
    ['pfazure.py'],
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
pfazure_pyz = PYZ(pfazure_a.pure, pfazure_a.zipped_data, cipher=block_cipher)
pfazure_exe = EXE(
    pfazure_pyz,
    pfazure_a.scripts,
    [],
    exclude_binaries=True,
    name='pfazure',
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


pfs_a = Analysis(
    ['pfs.py'],
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
pfs_pyz = PYZ(pfs_a.pure, pfs_a.zipped_data, cipher=block_cipher)
pfs_exe = EXE(
    pfs_pyz,
    pfs_a.scripts,
    [],
    exclude_binaries=True,
    name='pfs',
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
    pf_exe,
    pf_a.binaries,
    pf_a.zipfiles,
    pf_a.datas,
    pfazure_exe,
    pfazure_a.binaries,
    pfazure_a.zipfiles,
    pfazure_a.datas,
    pfs_exe,
    pfs_a.binaries,
    pfs_a.zipfiles,
    pfs_a.datas,
    pfsvc_exe,
    pfsvc_a.binaries,
    pfsvc_a.zipfiles,
    pfsvc_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='promptflow',
)
