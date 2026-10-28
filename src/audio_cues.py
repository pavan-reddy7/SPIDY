# src/audio_cues.py
"""
SPIDY Futuristic Audio Cues

Synthesizes and plays lightweight sci-fi sound effects:
- wake: Two-tone ascending Stark wake chime
- listening: Soft acoustic ping
- confirm: Crisp tactical blip
- done: Warm harmonic success chord
- error: Subdued low-frequency warning tone

Uses sounddevice or winsound; zero external audio files required.
Thread-safe and non-blocking by default.
"""

import os
import threading
import wave
import io
import struct
import numpy as np

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    SOUNDDEVICE_AVAILABLE = False

try:
    import winsound
    WINSOUND_AVAILABLE = True
except Exception:
    WINSOUND_AVAILABLE = False

# Global toggle for audio cues (can be disabled via env var)
CUES_ENABLED = os.environ.get("SPIDY_AUDIO_CUES", "true").lower() in ("true", "1", "yes")

# In-memory WAV cache for instant zero-latency playback
_CUE_CACHE: dict[str, tuple[np.ndarray, int, bytes]] = {}
_PLAYBACK_LOCK = threading.Lock()


def _synthesize_tone(freqs: list[float], duration: float, decay_rate: float = 8.0, sample_rate: int = 44100) -> np.ndarray:
    """Synthesize harmonic frequencies with smooth exponential decay."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    signal = np.zeros_like(t)
    weight = 1.0 / len(freqs)
    for f in freqs:
        signal += weight * np.sin(2 * np.pi * f * t)
    # Exponential decay envelope
    envelope = np.exp(-decay_rate * t)
    # Smooth start attack (first 3ms) to avoid click
    attack_samples = int(sample_rate * 0.003)
    if attack_samples > 0 and attack_samples < len(t):
        envelope[:attack_samples] *= np.linspace(0, 1, attack_samples)
    audio = signal * envelope
    # Normalize to 16-bit integer range
    max_val = np.max(np.abs(audio)) if np.max(np.abs(audio)) > 0 else 1.0
    audio_int16 = (audio / max_val * 28000).astype(np.int16)
    return audio_int16


def _create_wav_bytes(audio_int16: np.ndarray, sample_rate: int = 44100) -> bytes:
    """Package 16-bit PCM numpy array into in-memory WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()


def _generate_cue(cue_name: str) -> tuple[np.ndarray, int, bytes]:
    """Generate audio waveform and WAV bytes for a named cue."""
    sample_rate = 44100
    if cue_name == "wake":
        # Ascending dual-tone Stark chime (587Hz D5 -> 880Hz A5)
        part1 = _synthesize_tone([587.33, 1174.66], duration=0.10, decay_rate=6.0, sample_rate=sample_rate)
        part2 = _synthesize_tone([880.0, 1760.0], duration=0.22, decay_rate=7.0, sample_rate=sample_rate)
        audio = np.concatenate([part1, part2])
    elif cue_name == "listening":
        # Soft prompt ping (987.77Hz B5)
        audio = _synthesize_tone([987.77], duration=0.12, decay_rate=14.0, sample_rate=sample_rate)
    elif cue_name == "confirm":
        # Tactical confirmation blip (1046.5Hz C6 -> 1318.5Hz E6)
        part1 = _synthesize_tone([1046.5], duration=0.04, decay_rate=12.0, sample_rate=sample_rate)
        part2 = _synthesize_tone([1318.5], duration=0.08, decay_rate=10.0, sample_rate=sample_rate)
        audio = np.concatenate([part1, part2])
    elif cue_name == "done":
        # Warm harmonic success chord (C-E-G triad: 523.25Hz, 659.25Hz, 783.99Hz)
        audio = _synthesize_tone([523.25, 659.25, 783.99, 1046.5], duration=0.35, decay_rate=6.5, sample_rate=sample_rate)
    elif cue_name == "error":
        # Subdued low warning tone (220Hz + 233Hz slight dissonance)
        part1 = _synthesize_tone([220.0, 233.0], duration=0.10, decay_rate=10.0, sample_rate=sample_rate)
        part2 = _synthesize_tone([185.0, 196.0], duration=0.18, decay_rate=8.0, sample_rate=sample_rate)
        audio = np.concatenate([part1, part2])
    else:
        # Default neutral blip
        audio = _synthesize_tone([800.0], duration=0.08, decay_rate=12.0, sample_rate=sample_rate)

    wav_bytes = _create_wav_bytes(audio, sample_rate)
    return audio, sample_rate, wav_bytes


def _get_cue(cue_name: str) -> tuple[np.ndarray, int, bytes]:
    """Retrieve or synthesize a cached cue."""
    if cue_name not in _CUE_CACHE:
        _CUE_CACHE[cue_name] = _generate_cue(cue_name)
    return _CUE_CACHE[cue_name]


def play_cue(cue_name: str, async_play: bool = True) -> None:
    """
    Play a sci-fi audio cue by name.
    Supported cues: 'wake', 'listening', 'confirm', 'done', 'error'.
    """
    if not CUES_ENABLED:
        return

    def _play():
        try:
            audio, sample_rate, wav_bytes = _get_cue(cue_name)
            if SOUNDDEVICE_AVAILABLE:
                with _PLAYBACK_LOCK:
                    sd.play(audio, sample_rate)
                    if not async_play:
                        sd.wait()
            elif WINSOUND_AVAILABLE:
                flags = winsound.SND_MEMORY
                if async_play:
                    flags |= winsound.SND_ASYNC
                winsound.PlaySound(wav_bytes, flags)
        except Exception:
            # Audio playback must never crash the assistant
            pass

    if async_play:
        threading.Thread(target=_play, daemon=True).start()
    else:
        _play()

