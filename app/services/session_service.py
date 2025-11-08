"""
Session Management Service
Manages transcription session lifecycle and coordinates STT processing.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import uuid

from app.models import Session, Transcript, get_db_session, WordInfo
from app.services.stt_service import GoogleSTTService, TranscriptResult
from app.utils.audio_utils import decode_base64_audio, validate_audio_format

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """In-memory state for active session."""
    session_id: str
    started_at: datetime
    last_activity: datetime
    language: str
    config: dict


class SessionService:
    """
    Manages transcription sessions.

    Coordinates between database, STT service, and WebSocket handlers.
    """

    def __init__(self, stt_service: GoogleSTTService, session_timeout_minutes: int = 60):
        """
        Initialize session service.

        Args:
            stt_service: Google STT service instance
            session_timeout_minutes: Session timeout in minutes (default: 60)
        """
        self.stt = stt_service
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.active_sessions: Dict[str, SessionState] = {}

        logger.info(f"SessionService initialized with {session_timeout_minutes}min timeout")

    async def start_session(self, session_id: str, config: dict) -> dict:
        """
        Start new transcription session.

        Args:
            session_id: Unique session identifier (should be UUID format)
            config: Session configuration dict with optional keys:
                   - language: Language code (default: "en-US")
                   - enable_consolidation: Enable LLM consolidation (Phase 3+)

        Returns:
            dict with status and session info

        Raises:
            ValueError: If session_id invalid or session already exists
        """
        # Validate session ID format
        try:
            uuid.UUID(session_id)
        except ValueError:
            raise ValueError(f"Invalid session_id format (must be UUID): {session_id}")

        # Check if session already exists
        if session_id in self.active_sessions:
            raise ValueError(f"Session {session_id} already active")

        # Get configuration
        language = config.get('language', 'en-US')

        try:
            # Create database session
            db = get_db_session()

            # Create Session record
            session = Session(
                id=session_id,
                created_at=datetime.utcnow(),
                status='active',
                language=language,
                config_json=str(config)  # Store as JSON string
            )
            session.config = config  # Use property setter to convert to JSON

            db.add(session)
            db.commit()

            # Start STT stream
            if self.stt.is_available():
                await self.stt.start_stream(session_id, language=language)
            else:
                logger.warning(f"STT service not available for session {session_id}")

            # Store in active sessions
            self.active_sessions[session_id] = SessionState(
                session_id=session_id,
                started_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                language=language,
                config=config
            )

            logger.info(f"Started session {session_id} with language {language}")

            return {
                'status': 'started',
                'session_id': session_id,
                'language': language,
                'stt_available': self.stt.is_available()
            }

        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {e}")
            # Cleanup on error
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            raise

        finally:
            db.close()

    async def process_audio(self, session_id: str, audio_data: str, timestamp: float) -> TranscriptResult:
        """
        Process audio chunk for a session.

        Args:
            session_id: Session identifier
            audio_data: Base64-encoded audio data (PCM16, 16kHz, mono)
            timestamp: Client timestamp

        Returns:
            TranscriptResult from STT processing

        Raises:
            ValueError: If session not found or audio invalid
        """
        # Validate session exists and is active
        if session_id not in self.active_sessions:
            raise ValueError(f"No active session found: {session_id}")

        session_state = self.active_sessions[session_id]

        try:
            # Decode audio
            audio_bytes = decode_base64_audio(audio_data)

            # Validate audio format
            validate_audio_format(audio_bytes)

            # Update last activity
            session_state.last_activity = datetime.utcnow()

            # Process through STT
            if self.stt.is_available():
                result = await self.stt.process_audio(audio_bytes, session_id)
            else:
                # STT not available - return empty result
                result = TranscriptResult(
                    text="",
                    confidence=0.0,
                    is_final=False,
                    error="STT service not available"
                )

            # Store final transcripts in database
            if result.is_final and result.text:
                self._save_transcript(session_id, result)

            return result

        except Exception as e:
            logger.error(f"Error processing audio for session {session_id}: {e}")
            raise

    def _save_transcript(self, session_id: str, result: TranscriptResult):
        """
        Save finalized transcript to database.

        Args:
            session_id: Session identifier
            result: Transcript result to save
        """
        try:
            db = get_db_session()

            transcript = Transcript(
                session_id=session_id,
                text=result.text,
                confidence=result.confidence,
                is_final=result.is_final,
                timestamp=result.timestamp
            )

            # Store word-level data
            if result.words:
                transcript.words = result.words

            db.add(transcript)
            db.commit()

            logger.debug(f"Saved transcript for session {session_id}: {result.text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to save transcript for session {session_id}: {e}")
        finally:
            db.close()

    async def stop_session(self, session_id: str) -> dict:
        """
        Stop transcription session.

        Args:
            session_id: Session identifier

        Returns:
            dict with session summary

        Raises:
            ValueError: If session not found
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"No active session found: {session_id}")

        session_state = self.active_sessions[session_id]

        try:
            db = get_db_session()

            # Update Session record in database
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.ended_at = datetime.utcnow()
                session.status = 'stopped'
                db.commit()

                # Calculate session summary
                duration = (session.ended_at - session.created_at).total_seconds()
                transcript_count = db.query(Transcript).filter(Transcript.session_id == session_id).count()

            # Stop STT stream
            if self.stt.is_available():
                await self.stt.stop_stream(session_id)

            # Remove from active sessions
            del self.active_sessions[session_id]

            logger.info(f"Stopped session {session_id}")

            return {
                'status': 'stopped',
                'session_id': session_id,
                'duration_seconds': duration,
                'transcript_count': transcript_count
            }

        except Exception as e:
            logger.error(f"Error stopping session {session_id}: {e}")
            raise
        finally:
            db.close()

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session from database.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        try:
            db = get_db_session()
            session = db.query(Session).filter(Session.id == session_id).first()
            return session
        finally:
            db.close()

    def get_transcripts(self, session_id: str) -> List[Transcript]:
        """
        Get all transcripts for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of Transcript objects
        """
        try:
            db = get_db_session()
            transcripts = db.query(Transcript).filter(
                Transcript.session_id == session_id
            ).order_by(Transcript.timestamp).all()
            return transcripts
        finally:
            db.close()

    def cleanup_expired_sessions(self):
        """
        Clean up sessions that exceeded timeout.

        This should be called periodically (e.g., every minute).
        """
        now = datetime.utcnow()
        expired_sessions = []

        for session_id, state in self.active_sessions.items():
            if now - state.last_activity > self.session_timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            logger.warning(f"Session {session_id} expired - auto-stopping")
            try:
                # Use asyncio.create_task in production
                # For now, we'll just remove it and update DB synchronously
                db = get_db_session()
                session = db.query(Session).filter(Session.id == session_id).first()
                if session:
                    session.ended_at = now
                    session.status = 'timeout'
                    db.commit()
                db.close()

                # Stop STT stream
                if self.stt.is_available():
                    # Note: This is sync, in production use async
                    pass

                del self.active_sessions[session_id]

            except Exception as e:
                logger.error(f"Error cleaning up expired session {session_id}: {e}")

        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

    def get_active_session_count(self) -> int:
        """
        Get count of active sessions.

        Returns:
            Number of active sessions
        """
        return len(self.active_sessions)

    def get_active_session_ids(self) -> List[str]:
        """
        Get list of active session IDs.

        Returns:
            List of session IDs
        """
        return list(self.active_sessions.keys())
