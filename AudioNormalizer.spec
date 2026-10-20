# -*- mode: python ; coding: utf-8 -*-
"""Especificación PyInstaller para generar la distribución portable de AudioNormalizer."""

from pathlib import Path
import shutil
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

project_root = Path(SPECPATH).resolve()
src_dir = project_root / "src"

# 1. Localizar binarios de FFmpeg (Gyan.dev build con librubberband y libsoxr)
GYAN_BIN_DIR = Path(
    r"C:\Users\yuichi\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin"
)

ffmpeg_path = shutil.which("ffmpeg") or str(GYAN_BIN_DIR / "ffmpeg.exe")
ffprobe_path = shutil.which("ffprobe") or str(GYAN_BIN_DIR / "ffprobe.exe")

binaries = []
for bin_candidate in (ffmpeg_path, ffprobe_path):
    if bin_candidate and Path(bin_candidate).is_file():
        binaries.append((str(Path(bin_candidate).resolve()), "."))

binaries += collect_dynamic_libs("soundfile")
binaries += collect_dynamic_libs("scipy")
binaries += collect_dynamic_libs("numba")

# 2. Recolectar archivos de datos estáticos (Gradio frontend, Librosa, etc.)
datas = [(str(src_dir), "src")]
for pkg in (
    "gradio",
    "gradio_client",
    "safehttpx",
    "groovy",
    "librosa",
    "soundfile",
    "_soundfile_data",
):
    try:
        datas += collect_data_files(pkg, include_py_files=False)
    except Exception:
        pass

# 3. Copiar metadatos requeridos en tiempo de ejecución
for meta_pkg in (
    "gradio",
    "gradio_client",
    "huggingface_hub",
    "safehttpx",
    "groovy",
    "librosa",
    "scipy",
    "numba",
    "soundfile",
    "lazy_loader",
    "pooch",
):
    try:
        datas += copy_metadata(meta_pkg)
    except Exception:
        pass

# 4. Submódulos e importaciones dinámicas de librosa / scipy / numba / audio_normalizer
hiddenimports = [
    "audio_normalizer",
    "audio_normalizer.beat_grid",
    "audio_normalizer.stretcher",
    "audio_normalizer.pipeline",
    "scipy._lib.messagestream",
    "scipy.special._cdflib",
    "sklearn.utils._typedefs",
    "sklearn.neighbors._partition_nodes",
]
for mod_pkg in ("librosa", "scipy.signal", "scipy.interpolate", "soundfile"):
    try:
        hiddenimports += collect_submodules(mod_pkg)
    except Exception:
        pass

a = Analysis(
    ["app.py"],
    pathex=[str(project_root), str(src_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["customtkinter", "windnd", "tkinter", "matplotlib", "IPython", "pytest"],
    noarchive=False,
    optimize=0,
    module_collection_mode={
        "gradio": "py",
        "gradio_client": "py",
        "librosa": "py",
    },
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AudioNormalizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AudioNormalizer",
)
