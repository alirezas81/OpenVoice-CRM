"""Run the local-microphone OpenVoice-CRM agent with Pipecat audio orchestration."""
from __future__ import annotations

import asyncio
import io
import logging
import wave
from typing import Any

from groq import Groq
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

from .config import settings
from .custom_edge_tts import EdgeTTSStreamer
from .rag_engine import get_rag_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("openvoice-crm-agent")


class VoiceAgentProcessor(FrameProcessor):
    """Transport-independent turn handler for PCM input -> STT -> RAG -> TTS.

    The transport feeds standard Pipecat frames into this processor. Replacing
    ``LocalAudioTransport`` with a WebSocket or AudioSocket transport does not
    require changing STT, retrieval, or speech synthesis.
    """

    def __init__(self, groq_client: Groq, rag: Any, tts: EdgeTTSStreamer) -> None:
        super().__init__()
        self.groq = groq_client
        self.rag = rag
        self.tts = tts
        self._audio = bytearray()
        self._sample_rate = settings.audio_sample_rate
        self._channels = settings.audio_channels
        self._response_task: asyncio.Task[None] | None = None
        self._max_buffer_bytes = 45 * settings.audio_sample_rate * settings.audio_channels * 2

    async def process_frame(self, frame: Any, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, InputAudioRawFrame):
            raw = bytes(frame.audio)
            self._sample_rate = int(getattr(frame, "sample_rate", settings.audio_sample_rate))
            self._channels = int(getattr(frame, "num_channels", settings.audio_channels))
            self._audio.extend(raw)
            if len(self._audio) > self._max_buffer_bytes:
                del self._audio[:len(self._audio) - self._max_buffer_bytes]
            # Mic frames are consumed here; never send caller audio to the speaker.
            return

        if isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame)):
            # Cancel any in-flight answer so the caller can barge in naturally.
            if self._response_task and not self._response_task.done():
                self._response_task.cancel()
            await self.push_frame(InterruptionFrame())
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (UserStoppedSpeakingFrame, VADUserStoppedSpeakingFrame)):
            audio = bytes(self._audio)
            self._audio.clear()
            if audio:
                if self._response_task and not self._response_task.done():
                    self._response_task.cancel()
                self._response_task = asyncio.create_task(
                    self._respond(audio, self._sample_rate, self._channels),
                    name="voice-agent-turn",
                )
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    async def _respond(self, pcm: bytes, sample_rate: int, channels: int) -> None:
        try:
            wav_bytes = self._to_wav(pcm, sample_rate, channels)
            transcription = await asyncio.to_thread(self._transcribe, wav_bytes)
            user_text = transcription.strip()
            if not user_text:
                return
            logger.info("Transcription complete (%d characters)", len(user_text))
            answer = await self.rag.answer(user_text)
            async for chunk in self.tts.stream(answer):
                await self.push_frame(OutputAudioRawFrame(
                    audio=chunk.audio,
                    sample_rate=chunk.sample_rate,
                    num_channels=chunk.num_channels,
                ))
        except asyncio.CancelledError:
            logger.info("Response interrupted by caller")
            raise
        except Exception:
            logger.exception("Turn failed")
            fallback = "Sorry, I ran into a temporary issue. Please try again in a moment."
            try:
                async for chunk in self.tts.stream(fallback):
                    await self.push_frame(OutputAudioRawFrame(
                        audio=chunk.audio,
                        sample_rate=chunk.sample_rate,
                        num_channels=chunk.num_channels,
                    ))
            except Exception:
                logger.exception("Could not synthesize the fallback response")

    def _transcribe(self, wav_bytes: bytes) -> str:
        result = self.groq.audio.transcriptions.create(
            file=("caller.wav", wav_bytes, "audio/wav"),
            model=settings.groq_stt_model,
            language=settings.stt_language,
            response_format="text",
            temperature=0.0,
        )
        return result if isinstance(result, str) else str(getattr(result, "text", ""))

    @staticmethod
    def _to_wav(pcm: bytes, sample_rate: int, channels: int) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # Pipecat InputAudioRawFrame uses signed 16-bit PCM.
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return buffer.getvalue()

    async def cleanup(self) -> None:
        if self._response_task and not self._response_task.done():
            self._response_task.cancel()
            await asyncio.gather(self._response_task, return_exceptions=True)
        await super().cleanup()


async def run() -> None:
    settings.validate()
    # Initialize the vector index/embeddings away from Pipecat's event loop.
    rag = await asyncio.to_thread(get_rag_engine)
    groq_client = Groq(api_key=settings.groq_api_key)

    vad = SileroVADAnalyzer(params=VADParams(
        stop_secs=settings.vad_stop_secs,
        confidence=settings.vad_confidence,
    ))
    transport = LocalAudioTransport(params=LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_in_sample_rate=settings.audio_sample_rate,
        audio_in_channels=settings.audio_channels,
        audio_out_enabled=True,
        audio_out_sample_rate=24_000,
        audio_out_channels=1,
    ))
    agent = VoiceAgentProcessor(
        groq_client=groq_client,
        rag=rag,
        tts=EdgeTTSStreamer(voice=settings.edge_tts_voice),
    )
    pipeline = Pipeline([transport.input(), VADProcessor(vad_analyzer=vad), agent, transport.output()])
    task = PipelineTask(pipeline, params=PipelineParams(
        audio_in_sample_rate=settings.audio_sample_rate,
        audio_out_sample_rate=24_000,
        enable_metrics=True,
        enable_usage_metrics=True,
    ))
    logger.info("OpenVoice-CRM agent is ready. Speak when prompted; press Ctrl+C to stop.")
    await PipelineRunner().run(task)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Shutting down voice agent")


if __name__ == "__main__":
    main()
