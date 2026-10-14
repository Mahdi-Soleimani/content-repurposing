"""Shenava local ASR provider using sherpa-onnx.

This provider runs locally on the CPU and requires the
Reza2kn/Shenava-Koochik-v1.5-RNNT-sherpa-onnx model.
"""

import os
import time
import logging
from pathlib import Path
import struct
import asyncio
from concurrent.futures import ProcessPoolExecutor

from app.providers.base import TranscriptionProvider, TranscriptionResult
from app.config import settings

logger = logging.getLogger(__name__)

# Global executor for Shenava
_shenava_executor = None

# This variable will only be populated INSIDE the worker process
_worker_recognizer = None

def _init_worker():
    """Runs once when the worker process starts."""
    pass

def _worker_process_audio(audio_path: str, model_path_str: str) -> dict:
    """This function runs entirely inside the isolated worker process.
    It loads the model once (into the worker's RAM) and reuses it.
    This completely bypasses the FastAPI GIL!
    """
    global _worker_recognizer
    
    import sherpa_onnx
    import wave

    model_path = Path(model_path_str)

    # 1. Initialize if not already loaded in this process
    if _worker_recognizer is None:
        use_int8 = (model_path / "encoder.int8.onnx").exists()
        suffix = ".int8.onnx" if use_int8 else ".onnx"
        
        encoder = str(model_path / f"encoder{suffix}")
        decoder = str(model_path / f"decoder{suffix}")
        joiner = str(model_path / f"joiner{suffix}")
        tokens = str(model_path / "tokens.txt")
        
        _worker_recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            tokens=tokens,
            model_type="nemo_transducer",
            num_threads=os.cpu_count() or 2,
            sample_rate=16000,
            feature_dim=80,
            debug=False,
        )

    # 2. Read Audio
    with wave.open(audio_path, 'rb') as wav_file:
        frames = wav_file.readframes(wav_file.getnframes())
        num_samples = len(frames) // 2
        samples_int16 = struct.unpack(f"<{num_samples}h", frames)
        samples = [s / 32768.0 for s in samples_int16]
        sample_rate = wav_file.getframerate()
        
    audio_duration = len(samples) / sample_rate

    # 3. Decode
    stream = _worker_recognizer.create_stream()
    stream.accept_waveform(sample_rate, samples)
    _worker_recognizer.decode_stream(stream)
    result = stream.result

    # 4. Extract segments (Approximated since sherpa returns token-level)
    segments = []
    if hasattr(result, "timestamps") and result.timestamps and result.text:
        segments.append({
            "id": 0,
            "start": result.timestamps[0] if result.timestamps else 0.0,
            "end": result.timestamps[-1] if result.timestamps else audio_duration,
            "text": result.text,
        })

    return {
        "text": result.text,
        "duration": audio_duration,
        "segments": segments,
    }


class ShenavaProvider(TranscriptionProvider):
    """Local ASR provider using Shenava Koochik via sherpa-onnx (Process Pool)."""

    def __init__(self):
        self.model_path = Path(settings.SHENAVA_MODEL_PATH)
        
        # Initialize the global executor if it doesn't exist
        global _shenava_executor
        if _shenava_executor is None:
            import multiprocessing
            from concurrent.futures import ProcessPoolExecutor
            # Must use 'spawn' context, as 'fork' (Linux default) causes segfaults 
            # with C++ extensions (like ONNX Runtime) and asyncio!
            ctx = multiprocessing.get_context("spawn")
            _shenava_executor = ProcessPoolExecutor(
                max_workers=1,
                initializer=_init_worker,
                mp_context=ctx,
                max_tasks_per_child=1
            )

    @property
    def name(self) -> str:
        return "shenava"

    @property
    def model(self) -> str:
        return "Shenava-Koochik-v1.5"

    @property
    def supported_languages(self) -> list[str]:
        return ["fa"]

    async def is_available(self) -> bool:
        """Check if sherpa-onnx is installed and model files exist."""
        try:
            import sherpa_onnx
        except ImportError:
            logger.error("sherpa_onnx is not installed.")
            return False

        if not self.model_path.exists() or not self.model_path.is_dir():
            logger.error(f"Shenava model path not found: {self.model_path}")
            return False

        required_files = ["encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"]
        alt_files = ["encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt"]

        has_int8 = all((self.model_path / f).exists() for f in required_files)
        has_fp32 = all((self.model_path / f).exists() for f in alt_files)

        if not (has_int8 or has_fp32):
            return False

        return True

    async def transcribe(
        self,
        audio_path: str,
        language: str = "fa",
    ) -> TranscriptionResult:
        """Transcribe an audio file by dispatching to the worker process."""
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Shenava dispatching transcription to worker process for {audio_path}")
        start_time = time.time()

        # Run the heavy C++ inference in a separate Process to bypass the GIL
        loop = asyncio.get_running_loop()
        worker_result = await loop.run_in_executor(
            _shenava_executor, 
            _worker_process_audio, 
            audio_path, 
            str(self.model_path)
        )

        end_time = time.time()
        processing_time = end_time - start_time
        audio_duration = worker_result["duration"]
        rtf = processing_time / audio_duration if audio_duration > 0 else 0.0

        logger.info(
            f"Shenava transcription completed in worker process. "
            f"Audio duration: {audio_duration:.2f}s, "
            f"Processing time: {processing_time:.2f}s, "
            f"RTF: {rtf:.2f}"
        )

        return TranscriptionResult(
            text=worker_result["text"],
            language="fa",
            duration=audio_duration,
            segments=worker_result["segments"],
            provider=self.name,
            model=self.model,
        )
