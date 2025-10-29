# audio_recorder.py
# ============================================================
# Cross-platform Audio Recorder with robust VAD/Hysteresis
# - Dynamic noise calibration
# - Start/End hysteresis (different thresholds)
# - Pre-roll & post-silence padding
# - Min speech duration after start
# - Windows/Linux (Raspberry Pi) with graceful fallbacks
# ============================================================

import time
import io
import audioop
import collections
from typing import Optional

try:
    import pyaudio
    _HAS_PYAUDIO = True
except Exception:
    _HAS_PYAUDIO = False
    pyaudio = None  # type: ignore

try:
    import sys
    import platform
except Exception:
    sys = None
    platform = None

try:
    from Config import Config
except Exception:
    # Minimal stub if Config is not present during import-time checks
    class Config:  # type: ignore
        REC_SAMPLE_RATE = 16000
        REC_WIDTH = 2
        REC_CHANNELS = 1
        REC_CHUNK = 1024
        REC_DEVICE_INDEX = None  # optional


class AudioRecorder:
    """
    Simple audio recorder with VAD-like stop on silence using hysteresis,
    suitable for single-thread assistants that call `record_until_silence`
    and feed the raw PCM bytes to STT.
    """

    def __init__(self, config: Optional[Config] = None):
        self.cfg = config or Config()

        # Core audio params
        self.rate = int(getattr(self.cfg, "REC_SAMPLE_RATE", 16000))
        self.width = int(getattr(self.cfg, "REC_WIDTH", 2))           # bytes per sample (2 = 16-bit)
        self.channels = int(getattr(self.cfg, "REC_CHANNELS", 1))
        self.chunk = int(getattr(self.cfg, "REC_CHUNK", 1024))
        self.device_index = getattr(self.cfg, "REC_DEVICE_INDEX", None)

        # Internals
        self._pa = None
        self._stream = None

        # Initialize backend
        self._init_backend()

    # -------------------- Backend Init/Close --------------------

    def _init_backend(self):
        """Initialize PyAudio if available; raise clear error if not."""
        if not _HAS_PYAUDIO:
            raise RuntimeError(
                "PyAudio is not installed/available. "
                "Install it first (Windows: pip install pipwin && pipwin install pyaudio) "
                "or on Linux: sudo apt-get install portaudio19-dev && pip install pyaudio."
            )
        try:
            self._pa = pyaudio.PyAudio()
        except Exception as ex:
            raise RuntimeError(f"Failed to initialize PyAudio: {ex}")

    def _ensure_stream(self):
        """Open input stream if not opened yet."""
        if self._stream is not None:
            return
        if self._pa is None:
            raise RuntimeError("PyAudio handle is not initialized")

        pa_format = self._pa.get_format_from_width(self.width)
        kwargs = dict(
            format=pa_format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        if self.device_index is not None:
            kwargs["input_device_index"] = self.device_index

        try:
            self._stream = self._pa.open(**kwargs)
        except Exception as ex:
            raise RuntimeError(f"Failed to open input stream: {ex}")

        # Prime the stream to reduce latency
        try:
            _ = self._stream.read(self.chunk, exception_on_overflow=False)
        except Exception:
            pass

    def close(self):
        """Close the stream and terminate PyAudio."""
        try:
            if self._stream is not None:
                try:
                    self._stream.stop_stream()
                except Exception:
                    pass
                try:
                    self._stream.close()
                except Exception:
                    pass
        finally:
            self._stream = None

        try:
            if self._pa is not None:
                self._pa.terminate()
        except Exception:
            pass
        finally:
            self._pa = None

    # -------------------- Public Recording APIs --------------------

    def record_fixed(self, duration_sec: float = 5.0) -> bytes:
        """
        Record a fixed duration of audio and return raw PCM bytes.
        """
        self._ensure_stream()
        total_frames = int(self.rate * duration_sec / self.chunk)
        frames = []
        for _ in range(total_frames):
            data = self._stream.read(self.chunk, exception_on_overflow=False)
            frames.append(data)
        return b"".join(frames)

    def record_until_silence(
        self,
        max_duration: float = 25.0,
        noise_calib_duration: float = 0.8,
        start_frames: int = 3,
        end_frames: int = 15,
        post_silence_hold: float = 0.35,
        pre_roll_ms: int = 300,
        min_speech_after_start: float = 1.8,
        threshold_boost: float = 2.0,
    ) -> bytes:
        """
        Record until "real" silence is detected using hysteresis & padding.
        Returns raw PCM bytes (matching self.rate/self.width/self.channels).

        Parameters:
        - max_duration:           Hard cap in seconds.
        - noise_calib_duration:   Seconds to measure ambient noise at start.
        - start_frames:           # of consecutive frames above start_threshold to start speech.
        - end_frames:             # of consecutive frames below end_threshold to end speech.
        - post_silence_hold:      Extra seconds to capture after end detected.
        - pre_roll_ms:            Milliseconds kept from before speaking started.
        - min_speech_after_start: Minimum seconds after start before allowing end.
        - threshold_boost:        Multiplier applied to noise floor to form thresholds.

        Tuning tips:
        - Cuts too early? Increase `end_frames` (e.g., 18–22) and/or `post_silence_hold`.
        - Misses soft speech? Decrease `threshold_boost` (e.g., 2.0–2.5).
        - Trims first word? Increase `pre_roll_ms` (e.g., 400–500ms).
        """

        if _HAS_PYAUDIO is False:
            raise RuntimeError("PyAudio backend not available")

        self._ensure_stream()

        bytes_per_frame = self.width * self.channels
        # How many chunk blocks to buffer for pre-roll
        pre_roll_bytes = int(self.rate * pre_roll_ms / 1000.0) * bytes_per_frame
        pre_roll_blocks = max(1, pre_roll_bytes // (self.chunk * bytes_per_frame))
        ring_pre = collections.deque(maxlen=pre_roll_blocks)

        frames = []

        # ---- 1) Noise calibration ----
        calib_end = time.time() + max(0.0, noise_calib_duration)
        noise_vals = []
        while time.time() < calib_end:
            data = self._stream.read(self.chunk, exception_on_overflow=False)
            rms = audioop.rms(data, self.width)
            noise_vals.append(rms)
            ring_pre.append(data)

        noise_floor = (sum(noise_vals) / max(1, len(noise_vals))) if noise_vals else 50
        # Two thresholds: higher to START, lower to END (hysteresis)
        start_threshold = max(150, noise_floor * threshold_boost)
        end_threshold = max(100, noise_floor * (threshold_boost * 0.55))

        # (Optional) debug print — uncomment if you want to see values
        # print(f"[VAD] noise_floor={noise_floor:.1f} start_thr={start_threshold:.1f} end_thr={end_threshold:.1f}")

        # ---- 2) State tracking ----
        speaking = False
        over_count = 0
        under_count = 0
        start_time = None
        hard_deadline = time.time() + max_duration

        # seed pre-roll
        frames.extend(list(ring_pre))

        # ---- 3) Main loop ----
        while True:
            if time.time() >= hard_deadline:
                break

            data = self._stream.read(self.chunk, exception_on_overflow=False)
            rms = audioop.rms(data, self.width)
            frames.append(data)

            if not speaking:
                if rms >= start_threshold:
                    over_count += 1
                    if over_count >= start_frames:
                        speaking = True
                        start_time = time.time()
                        under_count = 0
                else:
                    over_count = 0
            else:
                if rms < end_threshold:
                    under_count += 1
                else:
                    under_count = 0

                # Enforce minimum speech time before allowing end
                long_enough = (time.time() - start_time) >= min_speech_after_start if start_time else False
                if long_enough and under_count >= end_frames:
                    # Post-silence hold
                    hold_bytes = int(self.rate * post_silence_hold) * bytes_per_frame
                    hold_blocks = max(1, hold_bytes // (self.chunk * bytes_per_frame))
                    for _ in range(hold_blocks):
                        if time.time() >= hard_deadline:
                            break
                        extra = self._stream.read(self.chunk, exception_on_overflow=False)
                        frames.append(extra)
                    break

        return b"".join(frames) if frames else b""

    # -------------------- Utilities --------------------

    def pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        """
        Optional: wrap raw PCM into WAV header and return bytes.
        Useful if your STT expects WAV. Not used by default.
        """
        import wave
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(self.channels)
            # sample width in bytes (e.g., 2 for 16-bit)
            wf.setsampwidth(self.width)
            wf.setframerate(self.rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()
