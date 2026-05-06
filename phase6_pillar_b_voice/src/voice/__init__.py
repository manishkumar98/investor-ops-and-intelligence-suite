"""
Phase 3 — Voice Integration Layer.

Public API::

    from src.voice import (
        STTEngine, TranscriptResult,
        TTSEngine, SynthesisResult,
        VADEngine, VADResult,
        VoiceLogger, VoiceLogEntry,
        AudioPipeline, PipelineResult,
    )
"""
from __future__ import annotations

from phase6_pillar_b_voice.src.voice.stt_engine import STTEngine, TranscriptResult
from phase6_pillar_b_voice.src.voice.tts_engine import TTSEngine, SynthesisResult
from phase6_pillar_b_voice.src.voice.vad import VADEngine, VADResult
from phase6_pillar_b_voice.src.voice.voice_logger import VoiceLogger, VoiceLogEntry
from phase6_pillar_b_voice.src.voice.audio_pipeline import AudioPipeline, PipelineResult, PipelineSession

__all__ = [
    # STT
    "STTEngine",
    "TranscriptResult",
    # TTS
    "TTSEngine",
    "SynthesisResult",
    # VAD
    "VADEngine",
    "VADResult",
    # Logger
    "VoiceLogger",
    "VoiceLogEntry",
    # Pipeline
    "AudioPipeline",
    "PipelineResult",
    "PipelineSession",
]
