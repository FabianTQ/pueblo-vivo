"""Local voice pipeline (CPU): text-to-speech and speech-to-text.

Both backends run on CPU so the GPU stays free for the LLM + 3D render:
- TTS via pyttsx3 (Windows SAPI5) — zero model download, fully offline. Swap for
  Piper for nicer voices later (see README).
- STT via faster-whisper (CTranslate2) — small model, int8, CPU.

Imports are lazy so the rest of the brain runs even when these packages aren't
installed; `available()` reports what's usable.
"""

from __future__ import annotations

import os
import tempfile
import threading

_whisper_model = None
_whisper_lock = threading.Lock()


def available() -> dict:
    out = {"tts": False, "stt": False}
    try:
        import pyttsx3  # noqa: F401
        out["tts"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        import faster_whisper  # noqa: F401
        out["stt"] = True
    except Exception:  # noqa: BLE001
        pass
    return out


def tts_to_wav(text: str) -> bytes:
    """Synthesise speech and return WAV bytes."""
    import pyttsx3

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.save_to_file(text, path)
        engine.runAndWait()
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _get_whisper(model_size: str = "base"):
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel

            _whisper_model = WhisperModel(
                os.environ.get("PUEBLO_WHISPER_MODEL", model_size),
                device="cpu",
                compute_type="int8",
            )
        return _whisper_model


def stt_from_wav(wav_bytes: bytes) -> str:
    """Transcribe WAV bytes to text."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(wav_bytes)
        model = _get_whisper()
        segments, _info = model.transcribe(path)
        return " ".join(s.text for s in segments).strip()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
