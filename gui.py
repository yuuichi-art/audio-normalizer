"""Interfaz gráfica de escritorio moderna (estilo Material 3 Dark / Dashboard) para Audio Normalizer."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import threading
from tkinter import filedialog
from typing import Optional
import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Paleta Material 3 Dark / Dashboard minimalista
BG_MAIN = "#0B0D13"
SURFACE_CARD = "#131722"
SURFACE_ELEVATED = "#1A2030"
BORDER_SUBTLE = "#252C3F"
BORDER_ACCENT = "#7C5CFF"
ACCENT_PRIMARY = "#7C5CFF"
ACCENT_HOVER = "#6846F7"
ACCENT_SUCCESS = "#10B981"
ACCENT_SUCCESS_HOVER = "#059669"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

TIME_SIGNATURE_MAP = {
    "4/4": 4,
    "3/4": 3,
    "6/8": 6,
}


class AudioNormalizerApp(ctk.CTk):
    """Ventana principal de Audio Normalizer con estética Material 3 Dark."""

    def __init__(self, enable_windnd: bool = False) -> None:
        print("[GUI] 1/5 Configurando tema oscuro en CustomTkinter...", flush=True)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        print("[GUI] 2/5 Creando instancia principal CTk()...", flush=True)
        super().__init__()

        self.enable_windnd = enable_windnd
        self.title("Audio Normalizer · Bar-Level Rubberband Studio")

        # Centrar la ventana en la pantalla
        width, height = 760, 760
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        self.minsize(680, 700)
        self.configure(fg_color=BG_MAIN)

        self.selected_input_path: Optional[Path] = None
        self.last_output_path: Optional[Path] = None
        self.is_processing: bool = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        print("[GUI] 3/5 Construyendo paneles y widgets de la interfaz...", flush=True)
        self._build_header()
        self._build_dropzone_card()
        self._build_settings_card()
        self._build_action_row()
        self._build_status_and_log_card()

        # Preseleccionar audio.mp3 si existe en el workspace actual
        default_audio = Path(__file__).resolve().parent / "audio.mp3"
        if default_audio.is_file():
            self._set_input_file(default_audio)

        print("[GUI] 4/5 Forzando ventana visible al frente (deiconify / lift / focus_force)...", flush=True)
        self.after(50, self._bring_to_front)
        self.after(250, self._safe_init_drag_and_drop)

    def _bring_to_front(self) -> None:
        """Fuerza que la ventana aparezca al frente, restaurada y con foco activo."""
        try:
            self.update_idletasks()
            self.deiconify()
            self.state("normal")
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self.after(300, lambda: self.attributes("-topmost", False))
            print("[GUI] -> Ventana renderizada y traída al frente correctamente.", flush=True)
        except Exception as exc:
            print(f"[GUI] Advertencia al traer ventana al frente: {exc}", flush=True)

    def _safe_init_drag_and_drop(self) -> None:
        """
        Inicializa drag & drop después de que la ventana ya está completamente visible.
        Por seguridad en Windows 64-bit, está envuelto y desactivado por defecto salvo que se solicite.
        """
        if not self.enable_windnd:
            print(
                "[GUI] -> Drag & Drop nativo (windnd) omitido por seguridad para evitar bloqueo de WNDPROC; "
                "usa el panel interactivo o el botón 'Seleccionar archivo...'.",
                flush=True,
            )
            return

        try:
            import windnd
            print("[GUI] -> Registrando windnd.hook_dropfiles tras renderizado inicial...", flush=True)
            windnd.hook_dropfiles(self, func=self._on_files_dropped)
            print("[GUI] -> Drag & Drop (windnd) registrado con éxito.", flush=True)
        except Exception as exc:
            print(f"[GUI] -> No se pudo registrar windnd ({exc}); continuando sin él.", flush=True)

    def _build_header(self) -> None:
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=28, pady=(24, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Audio Normalizer",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        subtitle_lbl = ctk.CTkLabel(
            header_frame,
            text="Cuantización elástica continua por compás · preserva el groove y swing original",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        subtitle_lbl.grid(row=1, column=0, pady=(2, 0), sticky="w")

        badge = ctk.CTkLabel(
            header_frame,
            text="  FFMPEG RUBBERBAND · 44.1 kHz  ",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color=SURFACE_ELEVATED,
            text_color="#A78BFA",
            corner_radius=8,
            height=28,
        )
        badge.grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_dropzone_card(self) -> None:
        self.drop_card = ctk.CTkFrame(
            self,
            fg_color=SURFACE_CARD,
            border_color=BORDER_SUBTLE,
            border_width=2,
            corner_radius=16,
        )
        self.drop_card.grid(row=1, column=0, padx=28, pady=10, sticky="ew")
        self.drop_card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(self.drop_card, fg_color="transparent")
        inner.grid(row=0, column=0, padx=24, pady=20, sticky="ew")
        inner.grid_columnconfigure(0, weight=1)

        self.drop_icon_lbl = ctk.CTkLabel(
            inner,
            text="♫  Haz clic aquí para seleccionar tu archivo de audio",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.drop_icon_lbl.grid(row=0, column=0, pady=(2, 4))

        self.file_info_lbl = ctk.CTkLabel(
            inner,
            text="Formatos soportados: .mp3, .wav, .flac, .ogg, .m4a (salida a 44,100 Hz / 320 kbps)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        )
        self.file_info_lbl.grid(row=1, column=0, pady=(0, 12))

        self.browse_btn = ctk.CTkButton(
            inner,
            text="Seleccionar archivo...",
            command=self._browse_file,
            fg_color=SURFACE_ELEVATED,
            hover_color="#252E44",
            border_color=BORDER_SUBTLE,
            border_width=1,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=36,
            width=190,
            corner_radius=10,
        )
        self.browse_btn.grid(row=2, column=0)

        for widget in (self.drop_card, inner, self.drop_icon_lbl, self.file_info_lbl):
            widget.bind("<Button-1>", lambda _e: self._browse_file())

    def _build_settings_card(self) -> None:
        settings_card = ctk.CTkFrame(
            self,
            fg_color=SURFACE_CARD,
            border_color=BORDER_SUBTLE,
            border_width=1,
            corner_radius=16,
        )
        settings_card.grid(row=2, column=0, padx=28, pady=10, sticky="ew")
        settings_card.grid_columnconfigure(0, weight=1)
        settings_card.grid_columnconfigure(1, weight=1)

        section_lbl = ctk.CTkLabel(
            settings_card,
            text="PARÁMETROS DE CUANTIZACIÓN",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        section_lbl.grid(row=0, column=0, columnspan=2, padx=22, pady=(16, 10), sticky="w")

        # Columna izquierda: Auto-detectar BPM / Manual
        bpm_box = ctk.CTkFrame(settings_card, fg_color=SURFACE_ELEVATED, corner_radius=12)
        bpm_box.grid(row=1, column=0, padx=(22, 10), pady=(0, 18), sticky="nsew")
        bpm_box.grid_columnconfigure(0, weight=1)

        self.auto_bpm_var = ctk.BooleanVar(value=True)
        self.auto_bpm_switch = ctk.CTkSwitch(
            bpm_box,
            text="Auto-detectar BPM nominal",
            variable=self.auto_bpm_var,
            command=self._toggle_bpm_entry,
            progress_color=ACCENT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.auto_bpm_switch.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        entry_row = ctk.CTkFrame(bpm_box, fg_color="transparent")
        entry_row.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
        entry_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            entry_row,
            text="BPM Manual:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.manual_bpm_entry = ctk.CTkEntry(
            entry_row,
            placeholder_text="Ej. 139.0",
            height=32,
            corner_radius=8,
            fg_color=SURFACE_CARD,
            border_color=BORDER_SUBTLE,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.manual_bpm_entry.grid(row=0, column=1, sticky="ew")
        self._toggle_bpm_entry()

        # Columna derecha: Selector de compás
        meter_box = ctk.CTkFrame(settings_card, fg_color=SURFACE_ELEVATED, corner_radius=12)
        meter_box.grid(row=1, column=1, padx=(10, 22), pady=(0, 18), sticky="nsew")
        meter_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            meter_box,
            text="Métrica del compás (Bar-Level)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        self.meter_var = ctk.StringVar(value="4/4")
        self.meter_selector = ctk.CTkSegmentedButton(
            meter_box,
            values=["4/4", "3/4", "6/8"],
            variable=self.meter_var,
            selected_color=ACCENT_PRIMARY,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=SURFACE_CARD,
            unselected_hover_color="#22293C",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=32,
            corner_radius=8,
        )
        self.meter_selector.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")

    def _build_action_row(self) -> None:
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=3, column=0, padx=28, pady=(4, 10), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)

        self.normalize_btn = ctk.CTkButton(
            action_frame,
            text="Normalizar Audio",
            command=self._start_normalization,
            fg_color=ACCENT_PRIMARY,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            height=48,
            corner_radius=12,
        )
        self.normalize_btn.grid(row=0, column=0, sticky="ew")

        self.open_folder_btn = ctk.CTkButton(
            action_frame,
            text="Abrir carpeta",
            command=self._open_output_folder,
            fg_color=SURFACE_ELEVATED,
            hover_color="#26304A",
            border_color=BORDER_SUBTLE,
            border_width=1,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=48,
            width=160,
            corner_radius=12,
            state="disabled",
        )
        self.open_folder_btn.grid(row=0, column=1, padx=(12, 0))

    def _build_status_and_log_card(self) -> None:
        status_card = ctk.CTkFrame(
            self,
            fg_color=SURFACE_CARD,
            border_color=BORDER_SUBTLE,
            border_width=1,
            corner_radius=16,
        )
        status_card.grid(row=4, column=0, padx=28, pady=(6, 24), sticky="nsew")
        status_card.grid_columnconfigure((0, 1, 2), weight=1)
        status_card.grid_rowconfigure(3, weight=1)

        self.status_lbl = ctk.CTkLabel(
            status_card,
            text="Listo para procesar",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.status_lbl.grid(row=0, column=0, columnspan=3, padx=22, pady=(16, 6), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(
            status_card,
            mode="indeterminate",
            progress_color=ACCENT_PRIMARY,
            fg_color=SURFACE_ELEVATED,
            height=8,
            corner_radius=4,
        )
        self.progress_bar.grid(row=1, column=0, columnspan=3, padx=22, pady=(0, 14), sticky="ew")
        self.progress_bar.set(0)

        # Tarjetas rápidas de métricas (KPIs)
        self.kpi_bpm_val = self._create_kpi_pill(status_card, 0, "BPM OBJETIVO", "—")
        self.kpi_bars_val = self._create_kpi_pill(status_card, 1, "COMPASES AJUSTADOS", "—")
        self.kpi_rate_val = self._create_kpi_pill(status_card, 2, "RANGO ELÁSTICO", "—")

        # Cuadro de log detallado
        self.log_box = ctk.CTkTextbox(
            status_card,
            fg_color="#0D1018",
            border_color=BORDER_SUBTLE,
            border_width=1,
            text_color="#CBD5E1",
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=10,
            height=130,
        )
        self.log_box.grid(row=3, column=0, columnspan=3, padx=22, pady=(12, 18), sticky="nsew")
        self._append_log(
            "Sistema inicializado.\n"
            "• Frecuencia interna y de exportación: 44,100 Hz Estéreo (320 kbps CBR)\n"
            "• Motor DSP: FFmpeg librubberband (transients=crisp:detector=compound:phase=independent:pitchq=quality)"
        )

    def _create_kpi_pill(
        self, parent: ctk.CTkFrame, col: int, title: str, initial_value: str
    ) -> ctk.CTkLabel:
        padx = (22, 6) if col == 0 else ((6, 6) if col == 1 else (6, 22))
        pill = ctk.CTkFrame(parent, fg_color=SURFACE_ELEVATED, corner_radius=10)
        pill.grid(row=2, column=col, padx=padx, pady=0, sticky="ew")

        ctk.CTkLabel(
            pill,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(8, 0))

        val_lbl = ctk.CTkLabel(
            pill,
            text=initial_value,
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        val_lbl.pack(anchor="w", padx=14, pady=(0, 8))
        return val_lbl

    def _toggle_bpm_entry(self) -> None:
        if self.auto_bpm_var.get():
            self.manual_bpm_entry.configure(state="disabled", fg_color="#10131C")
        else:
            self.manual_bpm_entry.configure(state="normal", fg_color=SURFACE_CARD)
            self.manual_bpm_entry.focus_set()

    def _on_files_dropped(self, files: list) -> None:
        if self.is_processing or not files:
            return
        raw = files[0]
        path_str = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
        candidate = Path(path_str)
        if candidate.is_file():
            self._set_input_file(candidate)

    def _browse_file(self) -> None:
        if self.is_processing:
            return
        chosen = filedialog.askopenfilename(
            title="Seleccionar archivo de audio",
            initialdir=str(Path(__file__).resolve().parent),
            filetypes=[
                ("Archivos de Audio", "*.mp3 *.wav *.flac *.ogg *.m4a"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if chosen:
            self._set_input_file(Path(chosen))

    def _set_input_file(self, path: Path) -> None:
        self.selected_input_path = path.resolve()
        size_mb = self.selected_input_path.stat().st_size / (1024 * 1024)
        self.drop_card.configure(border_color=BORDER_ACCENT)
        self.drop_icon_lbl.configure(
            text=f"✓  {self.selected_input_path.name}",
            text_color="#E2E8F0",
        )
        self.file_info_lbl.configure(
            text=f"{size_mb:.2f} MB  ·  {self.selected_input_path.parent}",
            text_color="#A78BFA",
        )
        self._append_log(f"\nArchivo cargado: {self.selected_input_path}")

    def _append_log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _start_normalization(self) -> None:
        if self.is_processing:
            return

        if self.selected_input_path is None or not self.selected_input_path.is_file():
            self.status_lbl.configure(
                text="⚠ Selecciona un archivo de audio válido primero.",
                text_color="#F59E0B",
            )
            return

        target_bpm: Optional[float] = None
        if not self.auto_bpm_var.get():
            raw_bpm = self.manual_bpm_entry.get().strip().replace(",", ".")
            try:
                target_bpm = float(raw_bpm)
                if not (30.0 <= target_bpm <= 300.0):
                    raise ValueError("BPM fuera de rango (30 - 300).")
            except ValueError:
                self.status_lbl.configure(
                    text="⚠ Ingresa un BPM numérico válido (entre 30 y 300).",
                    text_color="#EF4444",
                )
                return

        meter_str = self.meter_var.get()
        beats_per_bar = TIME_SIGNATURE_MAP.get(meter_str, 4)

        in_path = self.selected_input_path
        if in_path.stem.endswith("_normalizado"):
            out_name = f"{in_path.stem}.mp3"
        else:
            out_name = f"{in_path.stem}_normalizado.mp3"
        out_path = in_path.parent / out_name

        # Preparar UI para procesamiento asíncrono
        self.is_processing = True
        self.normalize_btn.configure(state="disabled", text="Procesando con Rubberband...")
        self.browse_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.progress_bar.configure(mode="indeterminate", progress_color=ACCENT_PRIMARY)
        self.progress_bar.start()

        self._append_log(
            f"\n--- Iniciando normalización ({meter_str}, "
            f"BPM={'Auto' if target_bpm is None else target_bpm}) ---"
        )

        worker = threading.Thread(
            target=self._run_pipeline_worker,
            args=(in_path, out_path, target_bpm, beats_per_bar),
            daemon=True,
        )
        worker.start()

    def _run_pipeline_worker(
        self,
        in_path: Path,
        out_path: Path,
        target_bpm: Optional[float],
        beats_per_bar: int,
    ) -> None:
        def on_status(msg: str) -> None:
            self.after(0, self._update_live_status, msg)

        try:
            on_status("Inicializando motor de análisis (librosa)...")
            from audio_normalizer.pipeline import normalize_song_tempo

            stats = normalize_song_tempo(
                input_path=in_path,
                output_path=out_path,
                target_bpm=target_bpm,
                beats_per_bar=beats_per_bar,
                status_callback=on_status,
            )
            self.after(0, self._on_pipeline_success, stats)
        except Exception as exc:
            self.after(0, self._on_pipeline_error, str(exc))

    def _update_live_status(self, msg: str) -> None:
        self.status_lbl.configure(text=msg, text_color=TEXT_PRIMARY)
        self._append_log(f"• {msg}")

    def _on_pipeline_success(self, stats: dict) -> None:
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", progress_color=ACCENT_SUCCESS)
        self.progress_bar.set(1.0)

        self.normalize_btn.configure(state="normal", text="Normalizar Audio")
        self.browse_btn.configure(state="normal")

        self.last_output_path = Path(stats["output"]).resolve()
        self.open_folder_btn.configure(
            state="normal",
            fg_color=ACCENT_SUCCESS,
            hover_color=ACCENT_SUCCESS_HOVER,
            text_color="#FFFFFF",
        )

        self.status_lbl.configure(
            text=f"✓ Completado: {self.last_output_path.name}",
            text_color=ACCENT_SUCCESS,
        )

        self.kpi_bpm_val.configure(text=f"{stats['target_bpm']} BPM")
        self.kpi_bars_val.configure(text=f"{stats['bars_adjusted']} / {stats['total_bars']}")
        self.kpi_rate_val.configure(
            text=f"{stats['min_stretch_rate']:.3f}x – {stats['max_stretch_rate']:.3f}x"
        )

        summary = (
            f"\n=== Normalización Completada ===\n"
            f"  BPM detectado / objetivo : {stats['native_bpm']} -> {stats['target_bpm']} BPM\n"
            f"  Primer downbeat (t0)     : {stats['t0_sec']} s (Δt = {stats['bar_interval_sec']} s)\n"
            f"  Compases ajustados       : {stats['bars_adjusted']} de {stats['total_bars']}\n"
            f"  Formato exportado        : {stats['output_format']}\n"
            f"  Archivo generado         : {self.last_output_path}"
        )
        self._append_log(summary)

    def _on_pipeline_error(self, error_msg: str) -> None:
        self.is_processing = False
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", progress_color="#EF4444")
        self.progress_bar.set(0.0)

        self.normalize_btn.configure(state="normal", text="Normalizar Audio")
        self.browse_btn.configure(state="normal")
        self.status_lbl.configure(text=f"✗ Error: {error_msg}", text_color="#EF4444")
        self._append_log(f"\n[ERROR] {error_msg}")

    def _open_output_folder(self) -> None:
        target = self.last_output_path or self.selected_input_path
        if target is None:
            return
        target = target.resolve()
        if sys.platform.startswith("win") and target.is_file():
            subprocess.Popen(["explorer", f"/select,{target}"])
        elif target.parent.is_dir():
            os.startfile(str(target.parent))


def launch_gui() -> None:
    print("[GUI] Iniciando Audio Normalizer Studio...", flush=True)
    app = AudioNormalizerApp(enable_windnd=False)
    print("[GUI] 5/5 Entrando en app.mainloop()...", flush=True)
    app.mainloop()
    print("[GUI] Ventana cerrada limpiamente.", flush=True)


if __name__ == "__main__":
    launch_gui()
