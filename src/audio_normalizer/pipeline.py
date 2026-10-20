"""Pipeline de normalización rítmica usando librosa para análisis y FFmpeg rubberband portable."""

import os
from pathlib import Path
import shutil
import sys
from typing import Callable, Optional
import numpy as np
import librosa

from .beat_grid import TARGET_SR, detect_bar_grid
from .stretcher import render_with_ffmpeg_rubberband


def get_runtime_base_dir() -> Path:
    """Devuelve el directorio base donde reside el ejecutable (.exe) o la raíz del proyecto."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resolve_ffmpeg_executable(binary_name: str = "ffmpeg.exe") -> str:
    """
    Busca primero `ffmpeg.exe` en el entorno empaquetado (sys._MEIPASS, junto a sys.executable
    o en _internal/) antes de recurrir al PATH global del sistema.
    También añade la carpeta encontrada al PATH del proceso para que librosa/gradio la usen.
    """
    candidates: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / binary_name)

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / binary_name)
        candidates.append(exe_dir / "_internal" / binary_name)

    project_root = Path(__file__).resolve().parents[2]
    candidates.append(project_root / binary_name)

    for candidate in candidates:
        if candidate.is_file():
            bin_dir = str(candidate.parent)
            current_path = os.environ.get("PATH", "")
            if bin_dir not in current_path.split(os.pathsep):
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{current_path}"
            return str(candidate)

    fallback = shutil.which(binary_name) or shutil.which(Path(binary_name).stem)
    if fallback:
        return fallback

    raise FileNotFoundError(
        f"No se encontró '{binary_name}' ni en el paquete portable ni en el PATH del sistema."
    )


def resolve_input_audio_path(input_path: str | Path) -> Path:
    """
    Localiza el archivo de audio de entrada, incluso si se especificó sin extensión explícita.
    """
    candidate = Path(input_path)
    if candidate.is_file():
        return candidate

    for ext in (".mp3", ".wav", ".flac", ".ogg", ".m4a"):
        with_ext = candidate.with_suffix(ext)
        if with_ext.is_file():
            return with_ext

    raise FileNotFoundError(f"No se encontró el archivo de audio de entrada: {input_path}")


def normalize_song_tempo(
    input_path: str | Path,
    output_path: str | Path,
    target_bpm: Optional[float] = None,
    beats_per_bar: int = 4,
    status_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    1. Configura y localiza el binario `ffmpeg.exe` portable (o del sistema).
    2. Analiza los pulsos y compases a 44,100 Hz usando librosa.
    3. Construye la curva continua y suave de tempo con integral exacta por compás:
           delta_t = (60 / BPM_objetivo) * beats_per_bar
    4. Delega el renderizado acústico exclusivamente al filtro nativo `rubberband` de FFmpeg
       (transients=crisp:detector=compound:phase=independent:pitchq=quality) a 44,100 Hz.
    """
    def _notify(msg: str) -> None:
        if status_callback is not None:
            status_callback(msg)

    ffmpeg_bin = resolve_ffmpeg_executable("ffmpeg.exe")
    resolved_input = resolve_input_audio_path(input_path)
    output_path = Path(output_path)

    # 1. Cargar en mono a 44,100 Hz únicamente para el análisis de ritmo con librosa
    _notify("1/3  Cargando y remuestreando audio de análisis a 44,100 Hz...")
    y_analysis, sr = librosa.load(str(resolved_input), sr=TARGET_SR, mono=True)

    # 2. Calcular la rejilla de compases desde t0
    _notify(f"2/3  Detectando rejilla de compases ({beats_per_bar} pulsos/compás) con librosa...")
    grid = detect_bar_grid(
        y=y_analysis,
        sr=sr,
        beats_per_bar=beats_per_bar,
        target_bpm=target_bpm,
    )

    # 3. Renderizar directamente desde el archivo original con FFmpeg + librubberband
    _notify(
        f"3/3  Renderizando con FFmpeg rubberband a {grid.target_bpm:.2f} BPM "
        f"({len(grid.segments)} compases)..."
    )
    render_with_ffmpeg_rubberband(
        input_path=resolved_input,
        output_path=output_path,
        grid=grid,
        ffmpeg_executable=ffmpeg_bin,
    )

    rates = [seg.stretch_rate for seg in grid.segments]
    adjusted_bars = sum(1 for seg in grid.segments if abs(seg.stretch_rate - 1.0) > 1e-5)
    is_mp3 = output_path.suffix.lower() == ".mp3"

    _notify("¡Normalización completada con éxito!")

    return {
        "input": str(resolved_input),
        "output": str(output_path),
        "ffmpeg_binary": ffmpeg_bin,
        "audio_engine": "FFmpeg rubberband (transients=crisp:detector=compound:phase=independent:pitchq=quality)",
        "output_format": "MP3 320 kbps 44100 Hz Stereo (libmp3lame)" if is_mp3 else "WAV PCM_24 44100 Hz Stereo",
        "sample_rate": TARGET_SR,
        "t0_sec": round(grid.t0_sec, 6),
        "bar_interval_sec": round(grid.delta_t_sec, 6),
        "native_bpm": round(grid.native_bpm, 2),
        "target_bpm": round(grid.target_bpm, 2),
        "total_bars": len(grid.segments),
        "bars_adjusted": adjusted_bars,
        "min_stretch_rate": round(float(np.min(rates)), 4),
        "max_stretch_rate": round(float(np.max(rates)), 4),
    }
