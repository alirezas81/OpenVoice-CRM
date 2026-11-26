"""Environment-backed configuration for the OpenVoice-CRM voice agent."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _path_from_env(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True, slots=True)
class Settings:
    # Groq remains the audio transcription provider in the current MVP.
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_stt_model: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
    stt_language: str = os.getenv("STT_LANGUAGE", "en")

    # Anthropic Claude is the primary RAG/LLM provider. Haiku is a lower-latency option.
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    groq_llm_model: str = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")

    # Edge TTS has voices for 40+ languages/locales; select a compatible voice here.
    edge_tts_voice: str = os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural")

    knowledge_base_path: Path = _path_from_env("KNOWLEDGE_BASE_PATH", "data/knowledge_base.txt")
    chroma_persist_directory: Path = _path_from_env("CHROMA_PERSIST_DIRECTORY", "data/chroma_db")
    audio_sample_rate: int = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    audio_channels: int = int(os.getenv("AUDIO_CHANNELS", "1"))
    vad_stop_secs: float = float(os.getenv("VAD_STOP_SECS", "0.65"))
    vad_confidence: float = float(os.getenv("VAD_CONFIDENCE", "0.65"))

    def validate(self) -> None:
        if not self.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required for the configured Whisper STT service.")
        if not self.stt_language.strip():
            raise ValueError("STT_LANGUAGE must be a non-empty language code, such as 'en'.")
        if self.llm_provider not in {"anthropic", "groq"}:
            raise ValueError("LLM_PROVIDER must be either 'anthropic' or 'groq'.")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic.")
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq.")
        if self.audio_sample_rate not in (8000, 16000):
            raise ValueError("Silero VAD requires AUDIO_SAMPLE_RATE to be 8000 or 16000 Hz.")
