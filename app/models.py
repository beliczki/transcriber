from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, scoped_session
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
import json
import os

Base = declarative_base()


@dataclass
class WordInfo:
    """Word-level transcription information."""
    word: str
    confidence: float
    start_time: float
    end_time: float

    def to_dict(self):
        return {
            'word': self.word,
            'confidence': self.confidence,
            'start_time': self.start_time,
            'end_time': self.end_time
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            word=data['word'],
            confidence=data['confidence'],
            start_time=data['start_time'],
            end_time=data['end_time']
        )


class Session(Base):
    """Transcription session model."""
    __tablename__ = 'sessions'

    id = Column(String(36), primary_key=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), default='active', nullable=False)  # active, stopped, error
    language = Column(String(10), default='en-US', nullable=False)
    config_json = Column(Text, nullable=True)  # JSON string of additional config

    # Relationships
    transcripts = relationship('Transcript', back_populates='session', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Session(id={self.id}, status={self.status}, created={self.created_at})>"

    @property
    def config(self) -> dict:
        """Get config as dictionary."""
        if self.config_json:
            return json.loads(self.config_json)
        return {}

    @config.setter
    def config(self, value: dict):
        """Set config from dictionary."""
        self.config_json = json.dumps(value)


class Transcript(Base):
    """Transcript model for storing finalized transcriptions."""
    __tablename__ = 'transcripts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey('sessions.id'), nullable=False, index=True)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    is_final = Column(Boolean, default=True, nullable=False)
    words_json = Column(Text, nullable=True)  # JSON array of WordInfo objects
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    session = relationship('Session', back_populates='transcripts')

    def __repr__(self):
        preview = self.text[:50] + '...' if len(self.text) > 50 else self.text
        return f"<Transcript(id={self.id}, session_id={self.session_id}, text='{preview}')>"

    @property
    def words(self) -> List[WordInfo]:
        """Get words as list of WordInfo objects."""
        if self.words_json:
            words_data = json.loads(self.words_json)
            return [WordInfo.from_dict(w) for w in words_data]
        return []

    @words.setter
    def words(self, value: List[WordInfo]):
        """Set words from list of WordInfo objects."""
        self.words_json = json.dumps([w.to_dict() for w in value])


# Database session management
_engine = None
_session_factory = None


def init_db(database_url: str):
    """
    Initialize database and create tables.

    Args:
        database_url: SQLAlchemy database URL (e.g., 'sqlite:///data/transcriber.db')
    """
    global _engine, _session_factory

    # Create data directory if using SQLite
    if database_url.startswith('sqlite:///'):
        db_path = database_url.replace('sqlite:///', '')
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            print(f"Created database directory: {db_dir}")

    # Create engine
    _engine = create_engine(database_url, echo=False)

    # Create tables
    Base.metadata.create_all(_engine)
    print(f"Database initialized at: {database_url}")

    # Create session factory
    _session_factory = scoped_session(sessionmaker(bind=_engine))

    return _engine


def get_db_session():
    """
    Get a database session.

    Returns:
        SQLAlchemy session object
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory()


def close_db_session():
    """Close the current database session."""
    if _session_factory:
        _session_factory.remove()
