"""
Audio Analysis Module for Multi-Modal Anomaly Detection.

Processes audio streams using librosa and torchaudio for feature extraction
and anomaly scoring in conjunction with video analytics.
"""

import asyncio
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import numpy as np
import librosa
import torch
import torchaudio

from services.vision_pipeline.frame_grabber import FrameGrabber


@dataclass
class AudioFeatures:
    """Extracted audio features for analysis."""

    mfcc: np.ndarray
    spectral_centroid: float
    spectral_rolloff: float
    zero_crossing_rate: float
    rms_energy: float
    duration: float


@dataclass
class AudioAnalysisResult:
    """Result of audio analysis."""

    features: AudioFeatures
    anomaly_score: float
    is_anomaly: bool
    inference_time_ms: float
    model_name: str
    model_version: str


class AudioAnalyzer:
    """
    Real-time audio analyzer for anomaly detection.

    Extracts spectral and temporal features from audio streams
    and computes anomaly scores using a trained model.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        n_mfcc: int = 13,
        n_fft: int = 2048,
        hop_length: int = 512,
        model_path: Optional[str] = None,
        device: str = "cpu",
    ):
        """
        Initialize audio analyzer.

        Args:
            sample_rate: Audio sample rate
            n_mfcc: Number of MFCC coefficients
            n_fft: FFT window size
            hop_length: Hop length for STFT
            model_path: Path to trained anomaly detection model
            device: Compute device (cpu/cuda)
        """
        self.sample_rate = sample_rate
        self.n_mfcc = n_mfcc
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.model_path = model_path
        self.device = device

        # Load model if provided
        self.model = None
        if model_path:
            self._load_model()

    def _load_model(self) -> None:
        """Load anomaly detection model."""
        try:
            self.model = torch.jit.load(self.model_path, map_location=self.device)
            self.model.eval()
            print(f"Loaded audio model from {self.model_path}")
        except Exception as e:
            print(f"Warning: Could not load audio model: {e}")
            self.model = None

    def extract_features(self, audio: np.ndarray, sr: Optional[int] = None) -> AudioFeatures:
        """
        Extract audio features from waveform.

        Args:
            audio: Audio waveform (mono)
            sr: Sample rate (uses default if None)

        Returns:
            Extracted audio features
        """
        if sr is None:
            sr = self.sample_rate

        # Ensure mono
        if audio.ndim > 1:
            audio = audio.mean(axis=0)

        # Resample if needed
        if sr != self.sample_rate:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
            sr = self.sample_rate

        # Extract features
        mfcc = librosa.feature.mfcc(
            y=audio, sr=sr, n_mfcc=self.n_mfcc,
            n_fft=self.n_fft, hop_length=self.hop_length
        )

        spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(
            y=audio, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length
        )))

        spectral_rolloff = float(np.mean(librosa.feature.spectral_rolloff(
            y=audio, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length
        )))

        zero_crossing_rate = float(np.mean(librosa.feature.zero_crossing_rate(
            y=audio, hop_length=self.hop_length
        )))

        rms_energy = float(np.mean(librosa.feature.rms(
            y=audio, hop_length=self.hop_length
        )))

        duration = len(audio) / sr

        return AudioFeatures(
            mfcc=mfcc,
            spectral_centroid=spectral_centroid,
            spectral_rolloff=spectral_rolloff,
            zero_crossing_rate=zero_crossing_rate,
            rms_energy=rms_energy,
            duration=duration,
        )

    async def analyze(self, audio: np.ndarray, sr: Optional[int] = None) -> AudioAnalysisResult:
        """
        Analyze audio segment for anomalies.

        Args:
            audio: Audio waveform
            sr: Sample rate

        Returns:
            Audio analysis result with anomaly score
        """
        start_time = time.time()

        # Extract features
        features = self.extract_features(audio, sr)

        # Compute anomaly score
        anomaly_score = 0.0
        is_anomaly = False

        if self.model:
            try:
                # Prepare input for model
                # Using MFCC features as input
                mfcc_mean = np.mean(features.mfcc, axis=1)
                input_tensor = torch.from_numpy(mfcc_mean).float().unsqueeze(0).to(self.device)

                with torch.no_grad():
                    output = self.model(input_tensor)
                    anomaly_score = float(torch.sigmoid(output).item())
                    is_anomaly = anomaly_score > 0.5
            except Exception as e:
                print(f"Model inference error: {e}")
                # Fallback to heuristic
                anomaly_score = self._heuristic_anomaly_score(features)
                is_anomaly = anomaly_score > 0.7
        else:
            # Heuristic anomaly detection
            anomaly_score = self._heuristic_anomaly_score(features)
            is_anomaly = anomaly_score > 0.7

        inference_time_ms = (time.time() - start_time) * 1000

        return AudioAnalysisResult(
            features=features,
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
            inference_time_ms=inference_time_ms,
            model_name="audio_anomaly_detector",
            model_version="1.0.0",
        )

    def _heuristic_anomaly_score(self, features: AudioFeatures) -> float:
        """
        Heuristic anomaly scoring based on audio features.

        This is a simple rule-based approach for when no trained model is available.
        """
        # Normalize features to [0, 1] range based on expected values
        # These thresholds would be calibrated for specific environments
        scores = []

        # High spectral centroid might indicate unusual high-frequency content
        centroid_norm = min(features.spectral_centroid / 4000.0, 1.0)
        scores.append(centroid_norm * 0.3)

        # High zero crossing rate might indicate noise/unusual sounds
        zcr_norm = min(features.zero_crossing_rate * 10, 1.0)
        scores.append(zcr_norm * 0.3)

        # Low RMS energy might indicate silence/dropout
        rms_norm = 1.0 - min(features.rms_energy * 10, 1.0)
        scores.append(rms_norm * 0.2)

        # Spectral rolloff
        rolloff_norm = min(features.spectral_rolloff / 8000.0, 1.0)
        scores.append(rolloff_norm * 0.2)

        return sum(scores)


class AudioStreamProcessor:
    """
    Real-time audio stream processor.

    Captures audio from microphone or file, processes in chunks,
    and yields analysis results.
    """

    def __init__(
        self,
        analyzer: AudioAnalyzer,
        chunk_duration: float = 1.0,  # seconds
        overlap: float = 0.5,  # overlap between chunks
    ):
        """
        Initialize audio stream processor.

        Args:
            analyzer: AudioAnalyzer instance
            chunk_duration: Duration of each analysis chunk (seconds)
            overlap: Overlap between consecutive chunks (0.0 to 1.0)
        """
        self.analyzer = analyzer
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.chunk_samples = int(chunk_duration * analyzer.sample_rate)
        self.hop_samples = int(self.chunk_samples * (1 - overlap))
        self.buffer = np.array([], dtype=np.float32)

    async def process_stream(
        self,
        audio_stream: asyncio.Queue,
    ) -> asyncio.Queue:
        """
        Process audio stream from queue.

        Args:
            audio_stream: Queue of audio chunks (numpy arrays)

        Returns:
            Queue of analysis results
        """
        results_queue = asyncio.Queue()

        async def process_loop():
            while True:
                try:
                    # Get audio chunk from stream
                    chunk = await audio_stream.get()

                    if chunk is None:  # End of stream signal
                        break

                    # Add to buffer
                    self.buffer = np.concatenate([self.buffer, chunk])

                    # Process complete chunks
                    while len(self.buffer) >= self.chunk_samples:
                        # Extract chunk
                        analysis_chunk = self.buffer[:self.chunk_samples]
                        self.buffer = self.buffer[self.hop_samples:]

                        # Analyze
                        result = await self.analyzer.analyze(analysis_chunk)

                        # Send to results queue
                        await results_queue.put(result)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Audio processing error: {e}")

        # Start processing loop
        asyncio.create_task(process_loop())

        return results_queue


async def main():
    """Example usage of audio analyzer."""
    # Create analyzer
    analyzer = AudioAnalyzer(
        sample_rate=16000,
        model_path=None,  # No model for heuristic demo
    )

    # Generate test audio (1 second of noise)
    duration = 1.0
    t = np.linspace(0, duration, int(16000 * duration))
    test_audio = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.1 * np.random.randn(len(t))

    # Analyze
    result = await analyzer.analyze(test_audio)
    print(f"Anomaly score: {result.anomaly_score:.4f}")
    print(f"Is anomaly: {result.is_anomaly}")
    print(f"Inference time: {result.inference_time_ms:.2f}ms")
    print(f"Features: centroid={result.features.spectral_centroid:.1f}, "
          f"zcr={result.features.zero_crossing_rate:.4f}, "
          f"rms={result.features.rms_energy:.4f}")


if __name__ == "__main__":
    asyncio.run(main())