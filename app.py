"""WebUI local moderna y oscura con Gradio para Audio Normalizer (FFmpeg Rubberband 44.1 kHz)."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
from typing import Optional, Tuple

# Añadir src al path tanto en modo desarrollo como en bundle PyInstaller
if getattr(sys, "frozen", False):
    _meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    sys.path.insert(0, str(_meipass / "src"))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from audio_normalizer.pipeline import (
    get_runtime_base_dir,
    normalize_song_tempo,
    resolve_ffmpeg_executable,
)

# Pre-configurar el PATH con el ffmpeg portable antes de importar gradio/pydub
try:
    resolve_ffmpeg_executable("ffmpeg.exe")
except Exception:
    pass

import gradio as gr

TIME_SIGNATURE_MAP = {
    "4/4": 4,
    "3/4": 3,
    "6/8": 6,
}

DARK_CSS = """
:root, .dark {
    --body-background-fill: #0b0d13 !important;
    --background-fill-primary: #131722 !important;
    --background-fill-secondary: #1a2030 !important;
    --border-color-primary: #252c3f !important;
    --color-accent: #7c5cff !important;
}
.gradio-container {
    max-width: 1020px !important;
    margin: 0 auto !important;
    font-family: 'Segoe UI', Inter, system-ui, sans-serif !important;
}
.header-banner {
    background: linear-gradient(135deg, #131722 0%, #1a1f35 100%);
    border: 1px solid #252c3f;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 12px;
}
.header-banner h1 {
    margin: 0;
    font-size: 1.65rem;
    font-weight: 700;
    color: #f8fafc;
}
.header-banner p {
    margin: 6px 0 0 0;
    font-size: 0.92rem;
    color: #94a3b8;
}
"""

FORCE_DARK_JS = """
() => {
    document.body.classList.add('dark');
    document.documentElement.classList.add('dark');
}
"""


def find_free_port(host: str = "127.0.0.1", start_port: int = 7860, end_port: int = 7890) -> Optional[int]:
    """Busca dinámicamente el primer puerto TCP disponible en el rango [start_port, end_port]."""
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((host, port)) != 0:
                return port
    return None


def _toggle_manual_bpm(auto_detect: bool):
    return gr.update(interactive=not auto_detect)


def process_audio_ui(
    input_audio_path: Optional[str],
    auto_bpm: bool,
    manual_bpm: Optional[float],
    time_signature: str,
    progress: gr.Progress = gr.Progress(track_tqdm=False),
) -> Tuple[Optional[str], str, str, str, str]:
    """Ejecuta el pipeline de normalización y devuelve el archivo de salida y las métricas."""
    if not input_audio_path:
        raise gr.Error("Por favor, sube o selecciona un archivo de audio primero.")

    in_path = Path(input_audio_path)
    if not in_path.is_file():
        raise gr.Error(f"No se encontró el archivo de entrada: {input_audio_path}")

    target_bpm: Optional[float] = None
    if not auto_bpm:
        if manual_bpm is None or not (30.0 <= float(manual_bpm) <= 300.0):
            raise gr.Error("Ingresa un BPM manual válido entre 30 y 300.")
        target_bpm = float(manual_bpm)

    beats_per_bar = TIME_SIGNATURE_MAP.get(time_signature, 4)

    # Guardar junto al ejecutable (o raíz del proyecto en modo dev)
    workspace_dir = get_runtime_base_dir()
    base_stem = in_path.stem
    if base_stem.endswith("_normalizado"):
        out_name = f"{base_stem}.mp3"
    else:
        out_name = f"{base_stem}_normalizado.mp3"
    out_path = workspace_dir / out_name

    def _on_status(msg: str) -> None:
        if msg.startswith("1/3"):
            progress(0.2, desc=msg)
        elif msg.startswith("2/3"):
            progress(0.5, desc=msg)
        elif msg.startswith("3/3"):
            progress(0.8, desc=msg)
        else:
            progress(1.0, desc=msg)

    stats = normalize_song_tempo(
        input_path=in_path,
        output_path=out_path,
        target_bpm=target_bpm,
        beats_per_bar=beats_per_bar,
        status_callback=_on_status,
    )

    bpm_card = f"{stats['target_bpm']} BPM (Nativo: {stats['native_bpm']} BPM)"
    bars_card = f"{stats['bars_adjusted']} ajustados de {stats['total_bars']} compases ({time_signature})"
    stretch_card = (
        f"{stats['min_stretch_rate']:.4f}x – {stats['max_stretch_rate']:.4f}x  "
        f"(t0 = {stats['t0_sec']}s, Δt = {stats['bar_interval_sec']}s)"
    )
    details_card = (
        f"Archivo exportado: {stats['output']}\n"
        f"Formato: {stats['output_format']}\n"
        f"Binario FFmpeg: {stats['ffmpeg_binary']}"
    )

    return str(out_path), bpm_card, bars_card, stretch_card, details_card


def build_interface() -> gr.Blocks:
    base_dir = get_runtime_base_dir()
    default_input = base_dir / "audio.mp3"
    initial_audio = str(default_input) if default_input.is_file() else None

    default_output = base_dir / "audio_normalizado.mp3"
    initial_output = str(default_output) if default_output.is_file() else None

    with gr.Blocks(title="Audio Normalizer · Rubberband Studio") as demo:
        gr.HTML(
            """
            <div class="header-banner">
                <h1>Audio Normalizer · Bar-Level Rubberband Studio</h1>
                <p>Normalización elástica continua a 44,100 Hz · Preserva el swing, groove y transientes de batería (FFmpeg R3)</p>
            </div>
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                input_audio = gr.Audio(
                    value=initial_audio,
                    type="filepath",
                    label="Audio de Entrada (.mp3, .wav, .flac)",
                )

                with gr.Group():
                    auto_bpm_chk = gr.Checkbox(
                        value=True,
                        label="Auto-detectar BPM nominal (Mediana por compás)",
                    )
                    manual_bpm_num = gr.Number(
                        value=138.74,
                        minimum=30.0,
                        maximum=300.0,
                        step=0.1,
                        precision=2,
                        label="Forzar BPM Objetivo Manual",
                        interactive=False,
                    )
                    meter_radio = gr.Radio(
                        choices=["4/4", "3/4", "6/8"],
                        value="4/4",
                        label="Selector de Compás (Bar-Level Quantization)",
                    )

                normalize_btn = gr.Button(
                    "Normalizar BPM",
                    variant="primary",
                    size="lg",
                )

            with gr.Column(scale=1):
                output_audio = gr.Audio(
                    value=initial_output,
                    type="filepath",
                    label="Audio Normalizado (Escuchar / Descargar MP3 320 kbps · 44.1 kHz)",
                    interactive=False,
                )

                with gr.Row():
                    kpi_bpm = gr.Textbox(
                        label="BPM Detectado / Objetivo",
                        value="138.74 BPM (Nativo: 138.74 BPM)" if initial_output else "—",
                        interactive=False,
                    )
                    kpi_bars = gr.Textbox(
                        label="Compases Ajustados",
                        value="81 ajustados de 130 compases (4/4)" if initial_output else "—",
                        interactive=False,
                    )

                kpi_stretch = gr.Textbox(
                    label="Rango Elástico e Intervalo de Compás",
                    value="0.9530x – 1.0134x  (t0 = 0.12771s, Δt = 1.729887s)" if initial_output else "—",
                    interactive=False,
                )
                kpi_details = gr.Textbox(
                    label="Detalles de Exportación y Motor DSP",
                    value=(
                        f"Archivo exportado: {initial_output}\n"
                        "Formato: MP3 320 kbps 44100 Hz Stereo (libmp3lame)\n"
                        "Motor DSP: FFmpeg rubberband (transients=crisp:detector=compound:phase=independent:pitchq=quality)"
                    )
                    if initial_output
                    else "Listo para procesar.",
                    lines=3,
                    interactive=False,
                )

        auto_bpm_chk.change(
            fn=_toggle_manual_bpm,
            inputs=[auto_bpm_chk],
            outputs=[manual_bpm_num],
        )

        normalize_btn.click(
            fn=process_audio_ui,
            inputs=[input_audio, auto_bpm_chk, manual_bpm_num, meter_radio],
            outputs=[output_audio, kpi_bpm, kpi_bars, kpi_stretch, kpi_details],
        )

        demo.load(fn=None, js=FORCE_DARK_JS)

    return demo


def main() -> None:
    os.environ.setdefault("GRADIO_NUM_PORTS", "31")
    selected_port = find_free_port("127.0.0.1", 7860, 7890)
    port_info = f"http://127.0.0.1:{selected_port}" if selected_port else "puerto dinámico libre"

    print("==========================================================", flush=True)
    print("  Audio Normalizer · Bar-Level Rubberband Studio (WebUI)", flush=True)
    print(f"  Iniciando servidor local en {port_info} ...", flush=True)
    print("==========================================================", flush=True)

    app = build_interface()
    app.launch(
        server_name="127.0.0.1",
        server_port=selected_port,
        inbrowser=True,
        css=DARK_CSS,
    )


if __name__ == "__main__":
    main()
