import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration from environment variables."""

    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 5001))
    ENV = os.getenv('FLASK_ENV', 'development')

    # Google Cloud STT
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')

    # OpenAI (Phase 2+)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    # Anthropic Claude (Phase 3+)
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

    # LLM Consolidation Settings (Phase 3+)
    CONSOLIDATION_LLM = os.getenv('CONSOLIDATION_LLM', 'openai')
    CONSOLIDATION_MODEL = os.getenv('CONSOLIDATION_MODEL', 'gpt-4-turbo-preview')
    CONSOLIDATION_CONTEXT_WINDOW = int(os.getenv('CONSOLIDATION_CONTEXT_WINDOW', 5))
    CONSOLIDATION_MERGE_THRESHOLD = float(os.getenv('CONSOLIDATION_MERGE_THRESHOLD', 0.7))

    # Audio Processing
    MAX_AUDIO_BUFFER_SIZE = int(os.getenv('MAX_AUDIO_BUFFER_SIZE', 10485760))  # 10MB
    CHUNK_DURATION_MS = int(os.getenv('CHUNK_DURATION_MS', 1000))
    SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', 16000))
    AUDIO_CHANNELS = int(os.getenv('AUDIO_CHANNELS', 1))

    # STT Engine Defaults
    DEFAULT_STT_ENGINE = os.getenv('DEFAULT_STT_ENGINE', 'google')
    ENABLE_WORD_CONFIDENCE = os.getenv('ENABLE_WORD_CONFIDENCE', 'true').lower() == 'true'
    ENABLE_AUTO_PUNCTUATION = os.getenv('ENABLE_AUTO_PUNCTUATION', 'true').lower() == 'true'

    # Session Management
    SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT_MINUTES', 60))
    MAX_CONCURRENT_SESSIONS = int(os.getenv('MAX_CONCURRENT_SESSIONS', 10))
    AUTO_SAVE_TRANSCRIPTS = os.getenv('AUTO_SAVE_TRANSCRIPTS', 'true').lower() == 'true'

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/transcriber.db')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/transcriber.log')

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5000').split(',')

    @classmethod
    def validate(cls, strict=False):
        """
        Validate required configuration.

        Args:
            strict: If True, fail on missing Google credentials.
                   If False, only warn (for development).
        """
        errors = []
        warnings = []

        # For Phase 1, Google Cloud credentials are required for production
        if not cls.GOOGLE_APPLICATION_CREDENTIALS:
            msg = "GOOGLE_APPLICATION_CREDENTIALS is not set in .env file"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)
        elif not os.path.exists(cls.GOOGLE_APPLICATION_CREDENTIALS):
            msg = f"Google credentials file not found: {cls.GOOGLE_APPLICATION_CREDENTIALS}"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        if not cls.GOOGLE_CLOUD_PROJECT:
            msg = "GOOGLE_CLOUD_PROJECT is not set in .env file"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        # Print warnings
        if warnings:
            print("\n[WARNING] Configuration warnings:")
            for warn in warnings:
                print(f"  - {warn}")
            print("  Note: Google STT features will not work without valid credentials.")

        # Fail on errors
        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f"  - {err}" for err in errors)
            raise ValueError(error_msg)

        return True

    @classmethod
    def get_database_path(cls):
        """Get absolute path for database file."""
        db_url = cls.DATABASE_URL
        if db_url.startswith('sqlite:///'):
            # Extract path from sqlite URL
            db_path = db_url.replace('sqlite:///', '')
            return os.path.abspath(db_path)
        return None
