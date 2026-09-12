"""Speech-to-text helpers for Vamsi Companion."""

from __future__ import annotations

import json
import wave
from pathlib import Path


class TranscriptionUnavailable(RuntimeError):
    """Raised when local speech transcription is not configured."""


class TranscriptionInputError(ValueError):
    """Raised when uploaded audio cannot be transcribed."""


class VoskTranscriber:
    def __init__(self, model_path: Path) -> None:
        self.model_path = Path(model_path)
        self._model = None

    def is_available(self) -> bool:
        return self.model_path.exists() and self.model_path.is_dir()

    def _load_model(self):
        if not self.is_available():
            raise TranscriptionUnavailable(
                "Voice model is not installed. Run scripts\\setup_voice.ps1, restart the backend, then try Talk again."
            )
        try:
            from vosk import Model  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionUnavailable(
                "Vosk is not installed. Run scripts\\setup_voice.ps1, restart the backend, then try Talk again."
            ) from exc
        if self._model is None:
            self._model = Model(str(self.model_path))
        return self._model

    def transcribe_wav_bytes(self, audio: bytes) -> str:
        if not audio or len(audio) < 44:
            raise TranscriptionInputError("Audio was empty. Try again closer to the phone mic.")
        model = self._load_model()
        try:
            from vosk import KaldiRecognizer  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionUnavailable("Vosk recognizer is not installed.") from exc

        import io

        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                sample_rate = wav.getframerate()
                if channels != 1 or sample_width != 2:
                    raise TranscriptionInputError("Voice audio must be 16-bit mono WAV.")
                recognizer = KaldiRecognizer(model, sample_rate)
                recognizer.SetWords(False)
                while True:
                    data = wav.readframes(4000)
                    if not data:
                        break
                    recognizer.AcceptWaveform(data)
                result = json.loads(recognizer.FinalResult() or "{}")
        except wave.Error as exc:
            raise TranscriptionInputError("Voice audio format was not readable.") from exc
        text = str(result.get("text", "")).strip()
        if not text:
            raise TranscriptionInputError("No speech was captured. Try again closer to the phone mic.")
        return text
