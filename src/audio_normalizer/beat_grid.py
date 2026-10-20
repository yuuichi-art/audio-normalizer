"""Análisis rítmico y generación de curva continua de tempo a nivel de compás (44,100 Hz)."""

from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import librosa

TARGET_SR = 44100


@dataclass
class BarSegment:
    """Representa un compás entre dos downbeats consecutivos y su factor de tiempo objetivo."""
    index: int
    start_sample: int
    end_sample: int
    target_start_sample: int
    target_end_sample: int

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
    """Contiene la rejilla global sample-exacta y los parámetros para la curva continua."""
    sr: int
    beats_per_bar: int
    native_bpm: float
    target_bpm: float
    t0_sample: int
    t0_sec: float
    delta_t_sec: float
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
) -> BarGrid:
    """
    Usa librosa únicamente para el análisis de ritmo a 44,100 Hz y construye la
    rejilla matemática de compases desde el primer pulso real (t0):

        delta_t = (60.0 / BPM_objetivo) * beats_per_bar
        target_sample(k) = round((t0 + k * delta_t) * sr)
    """
    if sr != TARGET_SR:
        raise ValueError(f"El análisis requiere estrictamente sr={TARGET_SR} Hz (recibido: {sr} Hz).")

    y_mono = librosa.to_mono(y) if y.ndim > 1 else y
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

    bar_boundaries_samples = beat_samples[::beats_per_bar].astype(int)
    bar_boundaries_sec = bar_boundaries_samples / float(sr)

    t0_sample = int(bar_boundaries_samples[0])
    t0_sec = float(bar_boundaries_sec[0])

    bar_durations_sec = np.diff(bar_boundaries_sec)
    median_bar_sec = float(np.median(bar_durations_sec))
    native_bpm = (60.0 * beats_per_bar) / median_bar_sec

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
            )
        )

    return BarGrid(
        sr=sr,
        beats_per_bar=beats_per_bar,
        native_bpm=float(native_bpm),
        target_bpm=float(target_bpm),
        t0_sample=t0_sample,
        t0_sec=t0_sec,
        delta_t_sec=delta_t_sec,
        bar_boundaries_samples=bar_boundaries_samples,
        bar_boundaries_sec=bar_boundaries_sec,
        segments=segments,
    )
