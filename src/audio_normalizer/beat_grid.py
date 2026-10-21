"""Análisis rítmico con filtro de inercia temporal (±8%) y proyección de cierre a 44,100 Hz."""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import librosa

TARGET_SR = 44100
DEVIATION_TOLERANCE = 0.08  # ±8% de tolerancia respecto a T_bar


@dataclass
class BarSegment:
    """Representa un compás entre dos downbeats consecutivos y su factor de tiempo objetivo."""
    index: int
    start_sample: int
    end_sample: int
    target_start_sample: int
    target_end_sample: int
    is_synthetic: bool = False

    @property
    def start_time_sec(self) -> float:
        return self.start_sample / float(TARGET_SR)

    @property
    def end_time_sec(self) -> float:
        return self.end_sample / float(TARGET_SR)

    @property
    def original_duration_sec(self) -> float:
        return (self.end_sample - self.start_sample) / float(TARGET_SR)

    @property
    def target_duration_sec(self) -> float:
        return (self.target_end_sample - self.target_start_sample) / float(TARGET_SR)

    @property
    def stretch_ratio_u(self) -> float:
        """Razón de duración deseada u_k = target_duration / original_duration."""
        if self.original_duration_sec <= 0:
            return 1.0
        return self.target_duration_sec / self.original_duration_sec

    @property
    def stretch_rate(self) -> float:
        """Factor de velocidad nominal (tempo = original_duration / target_duration)."""
        if self.target_duration_sec <= 0:
            return 1.0
        return self.original_duration_sec / self.target_duration_sec


@dataclass
class BarGrid:
    """Contiene la rejilla global sample-exacta y las estadísticas del filtro de inercia."""
    sr: int
    beats_per_bar: int
    native_bpm: float
    target_bpm: float
    t0_sample: int
    t0_sec: float
    t_bar_sec: float
    delta_t_sec: float
    outliers_replaced: int
    projected_tail_bars: int
    bar_boundaries_samples: np.ndarray
    bar_boundaries_sec: np.ndarray
    segments: List[BarSegment]


def detect_bar_grid(
    y: np.ndarray,
    sr: int = TARGET_SR,
    beats_per_bar: int = 4,
    target_bpm: Optional[float] = None,
    start_bpm: float = 120.0,
    tightness: float = 800.0,
    onset_fmax: float = 4000.0,
    deviation_tolerance: float = DEVIATION_TOLERANCE,
) -> BarGrid:
    """
    Detecta la grilla de compases a 44,100 Hz aplicando:
    1. Duración de referencia nominal:
         T_bar = (60.0 / BPM_nominal) * beats_per_bar
    2. Filtro de inercia temporal y rechazo de anomalías (±8%):
         Verifica 0.92 * T_bar <= Δt_k <= 1.08 * T_bar.
         Si Δt_k cae fuera del rango, descarta t_{k+1} y lo establece sintéticamente
         usando la mediana de los compases válidos previos o T_bar.
    3. Fade-out final / Cierre:
         Si en la sección final la confianza de onsets cae o termina la detección antes
         del final del audio, continúa proyectando pasos constantes de T_bar hasta cubrir la pista.
    """
    if sr != TARGET_SR:
        raise ValueError(f"El análisis requiere estrictamente sr={TARGET_SR} Hz (recibido: {sr} Hz).")

    y_mono = librosa.to_mono(y) if y.ndim > 1 else y
    total_samples = len(y_mono)
    total_duration_sec = total_samples / float(sr)
    hop_length = 512

    onset_env = librosa.onset.onset_strength(
        y=y_mono,
        sr=sr,
        hop_length=hop_length,
        fmax=onset_fmax,
        aggregate=np.median,
    )
    _, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop_length,
        start_bpm=start_bpm,
        tightness=tightness,
        trim=False,
    )
    beat_samples = librosa.frames_to_samples(beat_frames, hop_length=hop_length)

    if len(beat_samples) < beats_per_bar * 2:
        raise ValueError(
            f"No se detectaron suficientes pulsos ({len(beat_samples)}) "
            f"para agrupar en compases de {beats_per_bar} tiempos."
        )

    raw_bar_samples = beat_samples[::beats_per_bar].astype(int)
    raw_bar_sec = raw_bar_samples / float(sr)

    # 1. Cálculo de BPM nominal y duración base de referencia T_bar
    raw_durations = np.diff(raw_bar_sec)
    median_bar_sec = float(np.median(raw_durations))
    native_bpm = (60.0 * beats_per_bar) / median_bar_sec
    t_bar_sec = (60.0 / native_bpm) * beats_per_bar

    # Evaluar confianza de onsets en el cierre (fade-out) para descartar cola sin señal rítmica
    frame_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr, hop_length=hop_length)
    global_onset_ref = float(np.percentile(onset_env, 75)) if len(onset_env) > 0 else 1.0
    confidence_threshold = 0.12 * global_onset_ref

    confident_end_idx = len(raw_bar_sec)
    while confident_end_idx > 2:
        t_prev = raw_bar_sec[confident_end_idx - 2]
        t_last = raw_bar_sec[confident_end_idx - 1]
        mask = (frame_times >= t_prev) & (frame_times < t_last)
        bar_peak_onset = float(np.max(onset_env[mask])) if np.any(mask) else 0.0
        if bar_peak_onset < confidence_threshold:
            confident_end_idx -= 1
        else:
            break

    bar_sec_list = list(raw_bar_sec[:confident_end_idx].astype(np.float64))
    synthetic_flags: List[bool] = [False] * (len(bar_sec_list) - 1)

    # 2. Filtro de rechazo por desviación (±8% de T_bar) con inercia temporal
    min_dt = (1.0 - deviation_tolerance) * t_bar_sec
    max_dt = (1.0 + deviation_tolerance) * t_bar_sec
    valid_durations: List[float] = []
    outliers_replaced = 0

    for k in range(len(bar_sec_list) - 1):
        dt_k = bar_sec_list[k + 1] - bar_sec_list[k]
        if min_dt <= dt_k <= max_dt:
            valid_durations.append(dt_k)
        else:
            ref_step = float(np.median(valid_durations)) if valid_durations else t_bar_sec
            bar_sec_list[k + 1] = bar_sec_list[k] + ref_step
            synthetic_flags[k] = True
            outliers_replaced += 1

    # Recalcular BPM nominal refinado sobre los intervalos válidos filtrados
    if valid_durations:
        t_bar_sec = float(np.median(valid_durations))
        native_bpm = (60.0 * beats_per_bar) / t_bar_sec

    # 3. Fade-out final / Cierre: proyectar pasos constantes de T_bar hasta el final del audio
    projected_tail_bars = 0
    while bar_sec_list[-1] + t_bar_sec <= total_duration_sec:
        next_t = bar_sec_list[-1] + t_bar_sec
        bar_sec_list.append(next_t)
        synthetic_flags.append(True)
        projected_tail_bars += 1

    # Recortar cualquier frontera que haya excedido ligeramente total_duration_sec por sustitución
    while len(bar_sec_list) > 2 and bar_sec_list[-1] > total_duration_sec:
        bar_sec_list.pop()
        synthetic_flags.pop()

    bar_boundaries_sec = np.array(bar_sec_list, dtype=np.float64)
    bar_boundaries_samples = np.clip(
        np.round(bar_boundaries_sec * sr).astype(int), 0, total_samples - 1
    )
    bar_boundaries_sec = bar_boundaries_samples / float(sr)

    t0_sample = int(bar_boundaries_samples[0])
    t0_sec = float(bar_boundaries_sec[0])

    if target_bpm is None:
        target_bpm = native_bpm

    delta_t_sec = (60.0 / float(target_bpm)) * beats_per_bar
    num_bars = len(bar_boundaries_samples) - 1

    target_bar_samples = [
        int(round((t0_sec + k * delta_t_sec) * sr)) for k in range(num_bars + 1)
    ]

    segments: List[BarSegment] = []
    for k in range(num_bars):
        segments.append(
            BarSegment(
                index=k,
                start_sample=int(bar_boundaries_samples[k]),
                end_sample=int(bar_boundaries_samples[k + 1]),
                target_start_sample=int(target_bar_samples[k]),
                target_end_sample=int(target_bar_samples[k + 1]),
                is_synthetic=synthetic_flags[k],
            )
        )

    return BarGrid(
        sr=sr,
        beats_per_bar=beats_per_bar,
        native_bpm=float(native_bpm),
        target_bpm=float(target_bpm),
        t0_sample=t0_sample,
        t0_sec=t0_sec,
        t_bar_sec=float(t_bar_sec),
        delta_t_sec=delta_t_sec,
        outliers_replaced=outliers_replaced,
        projected_tail_bars=projected_tail_bars,
        bar_boundaries_samples=bar_boundaries_samples,
        bar_boundaries_sec=bar_boundaries_sec,
        segments=segments,
    )
