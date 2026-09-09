# Build on the target OS: python -m PyInstaller packaging/AllenReferencePainter.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH).parent
hiddenimports = ['PySide6.QtSvg', 'matplotlib.backends.backend_qtagg', 'openpyxl', 'xlrd', 'scipy.spatial._ckdtree']
datas = [(str(root/'LICENSE'),'.'), (str(root/'README.md'),'.')]
binaries = []
for package in ['brainglobe_atlasapi','pyvista','pyvistaqt','wasmtime']:
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
for distribution in ['brainglobe-atlasapi','pyvista','pyvistaqt']:
    datas += copy_metadata(distribution)

a = Analysis([str(root/'packaging/launcher.py')],pathex=[str(root/'src')],binaries=binaries,datas=datas,hiddenimports=hiddenimports,hookspath=[str(root/'packaging/hooks')],runtime_hooks=[],excludes=['PyQt5','PyQt6','PySide2','tkinter'],noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='AllenReferencePainter',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='AllenReferencePainter')
