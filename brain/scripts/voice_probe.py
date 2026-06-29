"""Round-trip voice self-test: synth speech, then transcribe it back.

Validates both TTS and STT without a microphone:
    python -m scripts.voice_probe
"""

from __future__ import annotations

from pueblo import voice

TEXT = "There is a party at the plaza tonight at five o'clock."


def main() -> int:
    print("available:", voice.available())
    wav = voice.tts_to_wav(TEXT)
    print(f"TTS produced {len(wav)} WAV bytes")
    if len(wav) < 1000:
        print("FAIL: suspiciously small audio")
        return 1
    transcript = voice.stt_from_wav(wav)
    print("STT transcript:", repr(transcript))
    hits = [w for w in ("party", "plaza", "five", "clock", "tonight") if w in transcript.lower()]
    ok = len(hits) >= 2
    print(f"keyword hits: {hits}")
    print("ROUNDTRIP:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
