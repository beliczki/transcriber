"""
Google Cloud Speech-to-Text Service
Handles streaming speech recognition using Google Cloud STT API.
"""

from google.cloud import speech_v1 as speech
from google.api_core import exceptions as google_exceptions
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
import os

from app.models import WordInfo

logger = logging.getLogger(__name__)


@dataclass
class TranscriptResult:
    """Result from STT engine transcription."""
    text: str
    confidence: float
    is_final: bool
    words: List[WordInfo] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class GoogleSTTService:
    """
    Google Cloud Speech-to-Text streaming service.

    Manages streaming recognition sessions for real-time transcription.
    """

    def __init__(self, credentials_path: Optional[str] = None, project_id: Optional[str] = None, language: str = "en-US"):
        """
        Initialize Google Cloud STT client.

        Args:
            credentials_path: Path to Google Cloud credentials JSON file
            project_id: Google Cloud project ID
            language: Language code (default: "en-US")
        """
        self.language = language
        self.project_id = project_id
        self.client: Optional[speech.SpeechClient] = None
        self.active_streams: Dict[str, Any] = {}  # session_id -> stream handle

        # Initialize client if credentials available
        if credentials_path and os.path.exists(credentials_path):
            try:
                # Set credentials environment variable
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                self.client = speech.SpeechClient()
                logger.info(f"Google STT client initialized with language: {language}")
            except Exception as e:
                logger.error(f"Failed to initialize Google STT client: {e}")
                self.client = None
        else:
            logger.warning("Google STT client not initialized - credentials not available")
            self.client = None

    def _create_streaming_config(self, language: str = None) -> speech.StreamingRecognitionConfig:
        """
        Create streaming recognition configuration.

        Args:
            language: Language code (uses self.language if not specified)

        Returns:
            StreamingRecognitionConfig object
        """
        lang = language or self.language

        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=lang,
            enable_word_time_offsets=True,
            enable_word_confidence=True,
            enable_automatic_punctuation=True,
        )

        streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=True,  # Return interim results
        )

        return streaming_config

    async def start_stream(self, session_id: str, language: str = None) -> bool:
        """
        Start streaming recognition for a session.

        Args:
            session_id: Unique session identifier
            language: Language code (optional, uses default if not specified)

        Returns:
            True if stream started successfully

        Raises:
            RuntimeError: If Google STT client not initialized
        """
        if not self.client:
            raise RuntimeError("Google STT client not initialized - check credentials")

        if session_id in self.active_streams:
            logger.warning(f"Stream already exists for session {session_id}")
            return True

        try:
            # Create streaming config
            streaming_config = self._create_streaming_config(language)

            # Store stream configuration for this session
            self.active_streams[session_id] = {
                'config': streaming_config,
                'started_at': datetime.utcnow(),
                'requests': []  # Will store audio requests
            }

            logger.info(f"Started STT stream for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start stream for session {session_id}: {e}")
            raise

    async def process_audio(self, audio_data: bytes, session_id: str) -> TranscriptResult:
        """
        Process audio chunk and return transcript.

        Args:
            audio_data: Raw audio bytes (PCM16, 16kHz, mono)
            session_id: Session identifier

        Returns:
            TranscriptResult with transcription

        Raises:
            RuntimeError: If stream not started for this session
        """
        if not self.client:
            return TranscriptResult(
                text="",
                confidence=0.0,
                is_final=False,
                error="Google STT client not initialized"
            )

        if session_id not in self.active_streams:
            raise RuntimeError(f"No active stream for session {session_id}. Call start_stream() first.")

        try:
            # Create audio request
            request = speech.StreamingRecognizeRequest(audio_content=audio_data)

            # Get streaming config for this session
            stream_info = self.active_streams[session_id]
            config_request = speech.StreamingRecognizeRequest(
                streaming_config=stream_info['config']
            )

            # For Phase 1, we'll use a simpler approach: send each chunk individually
            # and get immediate response
            # In Phase 2, we can implement true streaming with generator pattern

            # Create requests generator
            def request_generator():
                yield config_request
                yield request

            # Get responses
            responses = self.client.streaming_recognize(request_generator())

            # Parse first response
            for response in responses:
                if not response.results:
                    continue

                result = response.results[0]
                if not result.alternatives:
                    continue

                alternative = result.alternatives[0]

                # Extract word-level information
                words = []
                if alternative.words:
                    for word_info in alternative.words:
                        words.append(WordInfo(
                            word=word_info.word,
                            confidence=word_info.confidence if hasattr(word_info, 'confidence') else alternative.confidence,
                            start_time=word_info.start_time.total_seconds() if hasattr(word_info, 'start_time') else 0.0,
                            end_time=word_info.end_time.total_seconds() if hasattr(word_info, 'end_time') else 0.0
                        ))

                return TranscriptResult(
                    text=alternative.transcript,
                    confidence=alternative.confidence if hasattr(alternative, 'confidence') else 0.0,
                    is_final=result.is_final,
                    words=words,
                    timestamp=datetime.utcnow()
                )

            # No results
            return TranscriptResult(
                text="",
                confidence=0.0,
                is_final=False
            )

        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google STT API error for session {session_id}: {e}")
            return TranscriptResult(
                text="",
                confidence=0.0,
                is_final=False,
                error=f"Google STT API error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error processing audio for session {session_id}: {e}")
            return TranscriptResult(
                text="",
                confidence=0.0,
                is_final=False,
                error=f"Error: {str(e)}"
            )

    async def stop_stream(self, session_id: str) -> bool:
        """
        Stop streaming recognition for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if stream stopped successfully
        """
        if session_id not in self.active_streams:
            logger.warning(f"No active stream to stop for session {session_id}")
            return False

        try:
            # Remove stream
            del self.active_streams[session_id]
            logger.info(f"Stopped STT stream for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping stream for session {session_id}: {e}")
            return False

    def is_available(self) -> bool:
        """
        Check if Google STT service is available.

        Returns:
            True if client is initialized and ready
        """
        return self.client is not None

    def get_active_sessions(self) -> List[str]:
        """
        Get list of active session IDs.

        Returns:
            List of session IDs with active streams
        """
        return list(self.active_streams.keys())
