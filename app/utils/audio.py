"""
Audio processing utilities — WAV I/O, energy analysis, dB manipulation.
"""
import numpy as np
from pathlib import Path
from typing import Tuple


def load_wav(path: str | Path, sr: int = 44100) -> Tuple[np.ndarray, int]:
    """Load WAV file, return (samples, sample_rate)."""
    import soundfile as sf
    data, file_sr = sf.read(str(path), dtype="float32")
    if file_sr != sr:
        import librosa
        data = librosa.resample(data.T if data.ndim > 1 else data, orig_sr=file_sr, target_sr=sr)
        if data.ndim > 1:
            data = data.T
        return data, sr
    return data, file_sr


def save_wav(path: str | Path, data: np.ndarray, sr: int = 44100):
    """Save numpy array as WAV file."""
    import soundfile as sf
    sf.write(str(path), data, sr)


def get_duration(path: str | Path) -> float:
    """Get audio file duration in seconds."""
    import soundfile as sf
    info = sf.info(str(path))
    return info.duration


def adjust_volume_db(data: np.ndarray, db: float) -> np.ndarray:
    """Adjust volume by dB amount."""
    factor = 10 ** (db / 20.0)
    return data * factor


def normalize_audio(data: np.ndarray, target_db: float = -1.0) -> np.ndarray:
    """Normalize audio to target peak dB."""
    peak = np.max(np.abs(data))
    if peak == 0:
        return data
    target_peak = 10 ** (target_db / 20.0)
    return data * (target_peak / peak)


def apply_fade_edges(
    data: np.ndarray,
    sr: int = 44100,
    fade_ms: int = 12,
) -> np.ndarray:
    """Apply a short fade-in/out to reduce audible joins between segments."""
    if len(data) == 0 or fade_ms <= 0:
        return data

    fade_samples = min(int(sr * fade_ms / 1000), len(data) // 2)
    if fade_samples <= 0:
        return data

    envelope = np.ones(len(data), dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, fade_samples, endpoint=True, dtype=np.float32)
    envelope[:fade_samples] = ramp
    envelope[-fade_samples:] = ramp[::-1]
    return data * envelope


def trim_trailing_silence(
    data: np.ndarray,
    sr: int = 44100,
    threshold_db: float = -40.0,
    min_silence_ms: int = 50,
) -> np.ndarray:
    """
    Trim silence from the end of an audio segment.
    Keeps a small tail (min_silence_ms) for natural decay.
    Returns trimmed audio.
    """
    if len(data) == 0:
        return data

    threshold = 10 ** (threshold_db / 20.0)
    frame_size = int(0.01 * sr)  # 10ms frames

    # Walk backwards to find last non-silent frame
    last_loud = len(data)
    for i in range(len(data) - frame_size, 0, -frame_size):
        frame = data[i:i + frame_size]
        if np.max(np.abs(frame)) > threshold:
            last_loud = i + frame_size
            break
    else:
        # Entire signal is silent
        return data[:int(min_silence_ms / 1000.0 * sr)]

    # Keep a small tail for natural decay
    tail_samples = int(min_silence_ms / 1000.0 * sr)
    end = min(last_loud + tail_samples, len(data))

    return data[:end]


def trim_leading_silence(
    data: np.ndarray,
    sr: int = 44100,
    threshold_db: float = -40.0,
) -> Tuple[np.ndarray, float]:
    """
    Trim silence from the beginning of an audio segment.
    Returns (trimmed_audio, trimmed_seconds).
    """
    if len(data) == 0:
        return data, 0.0

    threshold = 10 ** (threshold_db / 20.0)
    frame_size = int(0.01 * sr)  # 10ms frames

    for i in range(0, len(data) - frame_size, frame_size):
        frame = data[i:i + frame_size]
        if np.max(np.abs(frame)) > threshold:
            trimmed_seconds = i / sr
            return data[i:], trimmed_seconds

    # Entire signal is silent
    return data, 0.0


def mix_audio_tracks(
    voice: np.ndarray,
    background: np.ndarray,
    bg_volume_db: float = -3.0,
    sr: int = 44100,
) -> np.ndarray:
    """Mix voice track with background music."""
    # Ensure same length
    min_len = min(len(voice), len(background))
    voice = voice[:min_len]
    background = background[:min_len]

    # Adjust background volume
    background = adjust_volume_db(background, bg_volume_db)

    # Mix
    mixed = voice + background

    # Normalize to prevent clipping
    mixed = normalize_audio(mixed, target_db=-1.0)

    return mixed


def time_stretch_segment(
    data: np.ndarray,
    target_duration: float,
    current_duration: float,
    sr: int = 44100,
    max_stretch: float = 0.10,
) -> Tuple[np.ndarray, bool]:
    """
    Time-stretch audio to match target duration.
    Returns (stretched_audio, success).
    success is False if stretch exceeds max_stretch limit.
    """
    if current_duration == 0:
        return data, False

    ratio = target_duration / current_duration
    stretch_amount = abs(1.0 - ratio)

    if stretch_amount > max_stretch:
        return data, False

    import librosa
    if data.ndim > 1:
        # Process each channel
        channels = []
        for ch in range(data.shape[1] if data.ndim > 1 else 1):
            ch_data = data[:, ch] if data.ndim > 1 else data
            stretched = librosa.effects.time_stretch(ch_data, rate=1.0/ratio)
            channels.append(stretched)
        result = np.column_stack(channels)
    else:
        result = librosa.effects.time_stretch(data, rate=1.0/ratio)

    return result, True
