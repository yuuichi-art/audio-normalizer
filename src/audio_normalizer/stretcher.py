"""Motor de audio delegado exclusivamente al filtro nativo `rubberband` de FFmpeg."""

from pathlib import Path
import subprocess
import tempfile
from typing import List
import numpy as np

from .beat_grid import BarGrid, TARGET_SR

# Tamaño de bloque de control en muestras a 44,100 Hz (882 muestras = 20.0 ms exactos -> 50 Hz)
CONTROL_FRAME_SAMPLES = 882


def build_smooth_rubberband_commands(
    grid: BarGrid,
    control_frame_samples: int = CONTROL_FRAME_SAMPLES,
) -> List[str]:
    """
    Genera una curva continua y suave (C^1) de velocidad/tempo entre las anclas de compás,
    preservando exactamente la integral de duración objetivo (delta_t) en cada compás:

        u_k(tau) = u_lin(tau) + (u_bar[k] - m_k) * (1 - cos(2 * pi * tau))
        tempo(tau) = 1.0 / u_k(tau)
    """
    bar_times = grid.bar_boundaries_sec
    bar_durations = np.diff(bar_times)
    u_bar = grid.delta_t_sec / bar_durations
    num_bars = len(u_bar)

    u_edge = np.ones(num_bars + 1, dtype=np.float64)
    for k in range(1, num_bars):
        u_edge[k] = 0.5 * (u_bar[k - 1] + u_bar[k])

    step_sec = control_frame_samples / float(grid.sr)
    cmd_lines: List[str] = ["0.000000 rubberband tempo 1.000000;"]

    for k in range(num_bars):
        t_start = float(bar_times[k])
        t_end = float(bar_times[k + 1])
        dt_k = t_end - t_start
        m_k = 0.5 * (u_edge[k] + u_edge[k + 1])
        u_k = float(u_bar[k])

        n_steps = max(1, int(round(dt_k / step_sec)))
        for s_idx in range(n_steps):
            tau = (s_idx + 0.5) / float(n_steps)
            t_cur = t_start + tau * dt_k
            u_lin = (1.0 - tau) * u_edge[k] + tau * u_edge[k + 1]
            u_val = u_lin + (u_k - m_k) * (1.0 - np.cos(2.0 * np.pi * tau))
            tempo_val = 1.0 / float(np.clip(u_val, 0.5, 2.0))
            cmd_lines.append(f"{t_cur:.6f} rubberband tempo {tempo_val:.6f};")

    cmd_lines.append(f"{float(bar_times[-1]):.6f} rubberband tempo 1.000000;")
    return cmd_lines


def render_with_ffmpeg_rubberband(
    input_path: Path,
    output_path: Path,
    grid: BarGrid,
    ffmpeg_executable: str = "ffmpeg",
) -> None:
    """
    Invoca directamente FFmpeg (usando el binario portable o del sistema) para procesar
    el archivo de entrada a través del filtro nativo `rubberband` con alta fidelidad acústica:

        -af "aresample=44100:resampler=soxr,asetnsamples=n=882:p=0,asendcmd=f=...,
             rubberband=transients=crisp:detector=compound:phase=independent:pitchq=quality"
    """
    cmd_lines = build_smooth_rubberband_commands(grid)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd_file = Path(tmpdir) / "rubberband_cmds.txt"
        cmd_file.write_text("\n".join(cmd_lines) + "\n", encoding="utf-8")

        cmd_file_ff = cmd_file.as_posix().replace(":", r"\:")

        af_chain = (
            f"aresample={TARGET_SR}:resampler=soxr,"
            f"asetnsamples=n={CONTROL_FRAME_SAMPLES}:p=0,"
            f"asendcmd=f='{cmd_file_ff}',"
            "rubberband=transients=crisp:detector=compound:phase=independent:pitchq=quality"
        )

        is_mp3 = output_path.suffix.lower() == ".mp3"
        codec_args = (
            ["-codec:a", "libmp3lame", "-b:a", "320k"]
            if is_mp3
            else ["-codec:a", "pcm_s24le"]
        )

        ffmpeg_cmd = [
            str(ffmpeg_executable),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-af",
            af_chain,
            "-ar",
            str(TARGET_SR),
            "-ac",
            "2",
            *codec_args,
            str(output_path),
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"Error al ejecutar FFmpeg rubberband (código {result.returncode}): "
                f"{result.stderr.strip()}"
            )
