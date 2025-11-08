"""
Audio Processing Utilities
Handles audio format validation, encoding/decoding, and conversion.
"""

import base64
from typing import List
import logging

logger = logging.getLogger(__name__)


def decode_base64_audio(audio_data: str) -> bytes:
    """
    Decode base64-encoded audio data to bytes.

    Args:
        audio_data: Base64-encoded audio string

    Returns:
        Raw audio bytes

    Raises:
        ValueError: If audio_data is invalid base64
    """
    try:
        return base64.b64decode(audio_data)
    except Exception as e:
        logger.error(f"Failed to decode base64 audio: {e}")
        raise ValueError(f"Invalid base64 audio data: {e}")


def encode_base64_audio(audio_bytes: bytes) -> str:
    """
    Encode audio bytes to base64 string.

    Args:
        audio_bytes: Raw audio bytes

    Returns:
        Base64-encoded string
    """
    return base64.b64encode(audio_bytes).decode('utf-8')


def validate_audio_format(audio_data: bytes, expected_sample_rate: int = 16000, max_size: int = 10485760) -> bool:
    """
    Validate audio format and size.

    Args:
        audio_data: Raw audio bytes
        expected_sample_rate: Expected sample rate (default: 16000 Hz)
        max_size: Maximum allowed size in bytes (default: 10MB)

    Returns:
        True if valid

    Raises:
        ValueError: If audio data is invalid
    """
    # Check if audio data exists
    if not audio_data:
        raise ValueError("Audio data is empty")

    # Check size
    if len(audio_data) > max_size:
        raise ValueError(f"Audio data too large: {len(audio_data)} bytes (max: {max_size})")

    # For Phase 1, we trust the client sends PCM16, 16kHz, mono
    # More sophisticated validation can be added later using pydub or wave module

    logger.debug(f"Audio data validated: {len(audio_data)} bytes")
    return True


def get_audio_duration(audio_data: bytes, sample_rate: int = 16000, bits_per_sample: int = 16, channels: int = 1) -> float:
    """
    Calculate audio duration in seconds.

    Args:
        audio_data: Raw audio bytes (PCM format)
        sample_rate: Sample rate in Hz (default: 16000)
        bits_per_sample: Bits per sample (default: 16)
        channels: Number of channels (default: 1 for mono)

    Returns:
        Duration in seconds
    """
    bytes_per_sample = bits_per_sample // 8
    bytes_per_frame = bytes_per_sample * channels
    num_frames = len(audio_data) // bytes_per_frame
    duration = num_frames / sample_rate
    return duration


def chunk_audio(audio_data: bytes, chunk_size_ms: int = 1000, sample_rate: int = 16000, bits_per_sample: int = 16, channels: int = 1) -> List[bytes]:
    """
    Split audio into chunks of specified duration.

    Args:
        audio_data: Raw audio bytes (PCM format)
        chunk_size_ms: Chunk duration in milliseconds (default: 1000ms = 1 second)
        sample_rate: Sample rate in Hz (default: 16000)
        bits_per_sample: Bits per sample (default: 16)
        channels: Number of channels (default: 1 for mono)

    Returns:
        List of audio chunks as bytes
    """
    bytes_per_sample = bits_per_sample // 8
    bytes_per_frame = bytes_per_sample * channels

    # Calculate chunk size in bytes
    frames_per_chunk = int(sample_rate * chunk_size_ms / 1000)
    chunk_size_bytes = frames_per_chunk * bytes_per_frame

    # Split into chunks
    chunks = []
    for i in range(0, len(audio_data), chunk_size_bytes):
        chunk = audio_data[i:i + chunk_size_bytes]
        chunks.append(chunk)

    logger.debug(f"Split {len(audio_data)} bytes into {len(chunks)} chunks of ~{chunk_size_bytes} bytes")
    return chunks


def validate_pcm16_format(audio_data: bytes) -> bool:
    """
    Validate that audio data appears to be valid PCM16 format.

    This is a basic sanity check - just verifies the data length is even
    (PCM16 uses 2 bytes per sample).

    Args:
        audio_data: Raw audio bytes

    Returns:
        True if valid PCM16 format

    Raises:
        ValueError: If format appears invalid
    """
    if len(audio_data) % 2 != 0:
        raise ValueError("Invalid PCM16 format: audio data length must be even (2 bytes per sample)")

    return True
