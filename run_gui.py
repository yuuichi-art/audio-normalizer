"""Script lanzador para la interfaz gráfica de Audio Normalizer."""

import sys


def main() -> None:
    print("[run_gui] Cargando módulo gui.py...", flush=True)
    from gui import launch_gui

    launch_gui()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
