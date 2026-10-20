"""CLI principal para normalizar canciones analógicas usando análisis librosa + FFmpeg rubberband."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from audio_normalizer.pipeline import normalize_song_tempo


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Normaliza canciones analógicas a un BPM plano a 44,100 Hz usando librosa "
            "para el análisis rítmico y FFmpeg rubberband exclusivo para el renderizado de alta fidelidad."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Ruta al archivo de audio de entrada (WAV, FLAC, MP3; admite nombre sin extensión).",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Ruta al archivo de salida (.wav o .mp3 a 320 kbps y 44,100 Hz).",
    )
    parser.add_argument(
        "--bpm",
        type=float,
        default=None,
        help="BPM objetivo fijo. Si se omite, se usa la mediana exacta del tempo original.",
    )
    parser.add_argument(
        "--beats-per-bar",
        type=int,
        default=4,
        help="Pulsos por compás (por defecto: 4 para 4/4).",
    )

    args = parser.parse_args()
    stats = normalize_song_tempo(
        input_path=args.input,
        output_path=args.output,
        target_bpm=args.bpm,
        beats_per_bar=args.beats_per_bar,
    )

    print("=== Normalización completada ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
