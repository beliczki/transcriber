# Advanced Transcriber - Architecture Documentation

## Overview

Advanced Transcriber is a headless transcription service that processes audio streams through multiple STT engines and consolidates the results using LLM technology for improved accuracy.

### Core Concept

**One audio stream → Two STT engines → LLM picks best interpretation**

Think of it as getting a "second opinion" on transcription - two AI systems transcribe the same audio, and a third AI arbitrates when they disagree.

---

## Key Features

- **Dual-Engine Processing**: Google Cloud STT + OpenAI Whisper process the same audio in parallel
- **LLM Consolidation**: GPT-4 or Claude compares both transcripts and generates the best result
- **Word-Level Confidence**: Track which words engines agree/disagree on
- **Engine Agreement Tracking**: Database stores disagreements for quality analysis
- **WebSocket API**: Real-time streaming audio input and transcript output
- **No Input Integration**: Pure service - accepts audio from ANY source

---

## Architecture Diagram

```
External Client (memoAgent, VLC, etc.)
            │
            │ WebSocket
            ▼
┌─────────────────────────────────────────────────────┐
│              Advanced Transcriber                    │
│                                                       │
│   ┌───────────────────────────────────────────┐    │
│   │      WebSocket Handler                     │    │
│   │  - Accept audio chunks (PCM16, 16kHz)     │    │
│   │  - Session management                      │    │
│   │  - Emit transcript events                  │    │
│   └──────────────┬────────────────────────────┘    │
│                  │                                   │
│   ┌──────────────▼────────────────────────────┐    │
│   │      Audio Distributor Service            │    │
│   │  - Duplicate audio to both engines        │    │
│   │  - Run engines in parallel (asyncio)      │    │
│   └──────┬───────────────────────┬────────────┘    │
│          │                       │                  │
│   ┌──────▼──────────┐     ┌─────▼──────────┐      │
│   │ Google Cloud    │     │ OpenAI Whisper │      │
│   │ STT Engine      │     │ STT Engine     │      │
│   │                 │     │                │      │
│   │ - Word conf.    │     │ - Alt approach │      │
│   │ - Time offsets  │     │ - Different ML │      │
│   └──────┬──────────┘     └─────┬──────────┘      │
│          │ Transcript A          │ Transcript B     │
│          └──────────┬────────────┘                  │
│                     │                               │
│          ┌──────────▼────────────────┐             │
│          │ Consolidation Service     │             │
│          │ (LLM - GPT-4 / Claude)    │             │
│          │                            │             │
│          │ - Compare transcripts      │             │
│          │ - Pick best words          │             │
│          │ - Identify disagreements   │             │
│          │ - Calculate confidence     │             │
│          └──────────┬─────────────────┘             │
│                     │                               │
│          ┌──────────▼─────────────────┐            │
│          │  Confidence Tracker         │            │
│          │  - Color code words         │            │
│          │  - Track engine agreement   │            │
│          └──────────┬─────────────────┘            │
│                     │                               │
│          ┌──────────▼─────────────────┐            │
│          │  Database Storage           │            │
│          │  - Sessions                 │            │
│          │  - Raw transcripts          │            │
│          │  - Consolidated results     │            │
│          │  - Disagreements            │            │
│          └─────────────────────────────┘            │
│                                                       │
└─────────────────────────────────────────────────────┘
            │
            │ WebSocket
            ▼
    Client receives transcript with:
    - Consolidated text
    - Word confidences
    - Engine agreement flags
    - Disagreement markers
```

---

## Components

### 1. WebSocket Handler
**File:** `app/routes/websocket.py`

Manages client connections and audio streaming:

```python
@socketio.on('start_session')
def handle_start_session(data):
    """
    Client: { "session_id": "uuid", "config": {...} }
    Response: { "status": "started" }
    """

@socketio.on('audio_chunk')
async def handle_audio_chunk(data):
    """
    Client: {
        "session_id": "uuid",
        "audio_data": "base64-pcm16",
        "timestamp": 12345
    }
    Processing: Send to Audio Distributor
    Emit: 'transcript' event with results
    """

@socketio.on('stop_session')
def handle_stop_session(data):
    """
    Cleanup session, close engines
    """
```

### 2. Audio Distributor Service
**File:** `app/services/audio_distributor.py`

Core logic for parallel STT processing:

```python
class AudioDistributor:
    def __init__(self, engines: List[BaseSTTEngine]):
        self.engines = engines
        self.consolidator = ConsolidationService()

    async def process(self, audio_data: bytes, session_id: str):
        """
        Process audio through all engines in parallel
        """
        # Run both engines simultaneously
        tasks = [
            self.engines[0].transcribe(audio_data),  # Google
            self.engines[1].transcribe(audio_data)   # Whisper
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter failures
        valid_results = [r for r in results if not isinstance(r, Exception)]

        if len(valid_results) < 2:
            # Fallback to single engine
            return valid_results[0]

        # Consolidate both transcripts
        consolidated = await self.consolidator.consolidate(
            results[0],
            results[1],
            context=self.get_recent_context(session_id)
        )

        return consolidated
```

### 3. STT Engine Interface
**File:** `app/services/stt/base.py`

Abstract base class for all STT engines:

```python
@dataclass
class TranscriptResult:
    text: str
    confidence: float
    words: List[WordInfo]
    is_final: bool
    engine: str

class BaseSTTEngine(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> TranscriptResult:
        pass
```

### 4. Google Cloud STT Engine
**File:** `app/services/stt/google_stt.py`

```python
class GoogleSTTEngine(BaseSTTEngine):
    async def transcribe(self, audio_data: bytes) -> TranscriptResult:
        """
        Use Google Cloud Speech-to-Text API
        - Returns word-level confidence
        - Provides time offsets
        - Supports multiple languages
        """
```

### 5. OpenAI Whisper Engine
**File:** `app/services/stt/whisper_stt.py`

```python
class WhisperSTTEngine(BaseSTTEngine):
    async def transcribe(self, audio_data: bytes) -> TranscriptResult:
        """
        Use OpenAI Whisper API
        - Different ML approach than Google
        - Good at accents/noise
        - Provides alternative interpretation
        """
```

### 6. LLM Consolidation Service
**File:** `app/services/consolidation_service.py`

Uses GPT-4 or Claude to merge transcripts:

```python
class ConsolidationService:
    async def consolidate(
        self,
        transcript_google: TranscriptResult,
        transcript_whisper: TranscriptResult,
        context: str = ""
    ) -> ConsolidatedResult:
        """
        Send both transcripts to LLM with prompt:

        'You are consolidating two transcriptions of the SAME audio.

        Google STT: "{transcript_google.text}"
        Whisper STT: "{transcript_whisper.text}"

        Previous context: "{context}"

        Task:
        1. Where engines agree, use that text
        2. Where they disagree, pick the best based on:
           - Word confidence scores
           - Contextual fit
           - Language model probability
        3. Mark disagreements for tracking
        4. Return word-level confidence
        '
        """

        # Call LLM API
        response = await self.llm_client.complete(prompt)

        # Parse response into structured format
        return ConsolidatedResult(
            text=response.text,
            words=response.words_with_confidence,
            disagreements=response.disagreements,
            confidence=response.overall_confidence
        )
```

### 7. Confidence Tracker
**File:** `app/services/confidence_tracker.py`

Calculates color coding for words:

```python
def calculate_word_color(google_conf, whisper_conf, agree):
    """
    Green: Both engines agree + high confidence (>0.9)
    Yellow: Engines agree, medium confidence (0.7-0.9)
    Orange: Engines disagree, LLM picked best
    Red: Low confidence or high disagreement
    """
    avg_conf = (google_conf + whisper_conf) / 2

    if agree and avg_conf >= 0.9:
        return "green"
    elif agree and avg_conf >= 0.7:
        return "yellow"
    elif not agree:
        return "orange"
    else:
        return "red"
```

### 8. Database Models
**File:** `app/models.py`

```python
class Session:
    id: str (UUID)
    created_at: datetime
    ended_at: datetime
    status: str

class RawTranscript:
    id: int
    session_id: str
    engine: str  # 'google' or 'whisper'
    text: str
    confidence: float
    words_json: str  # JSON of word-level data
    timestamp: datetime

class ConsolidatedTranscript:
    id: int
    session_id: str
    text: str
    confidence: float
    words_json: str  # With agreement flags
    disagreements_json: str
    llm_model: str  # 'gpt-4-turbo-preview'
    timestamp: datetime

class EngineDisagreement:
    id: int
    session_id: str
    position: int  # Word position
    google_text: str
    whisper_text: str
    chosen_text: str
    timestamp: datetime
```

---

## WebSocket API

### Client → Server

**Start Session:**
```json
{
  "action": "start_session",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "config": {
    "language": "en-US",
    "enable_consolidation": true,
    "llm_model": "gpt-4-turbo-preview"
  }
}
```

**Stream Audio:**
```json
{
  "action": "audio_chunk",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "audio_data": "UklGRiQAAABXQVZFZm10...",  // Base64 PCM16
  "timestamp": 1234567890.123
}
```

**Stop Session:**
```json
{
  "action": "stop_session",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Server → Client

**Transcript Event:**
```json
{
  "event": "transcript",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_final": true,
  "text": "Hello world, this is a test",
  "confidence": 0.94,
  "words": [
    {
      "word": "Hello",
      "confidence": 0.98,
      "color": "green",
      "engines_agree": true,
      "start_time": 0.0,
      "end_time": 0.5
    },
    {
      "word": "world",
      "confidence": 0.87,
      "color": "orange",
      "engines_agree": false,
      "start_time": 0.5,
      "end_time": 1.0,
      "google_version": "world",
      "whisper_version": "word"
    }
  ],
  "engine_results": {
    "google": {
      "text": "Hello world this is a test",
      "confidence": 0.95
    },
    "whisper": {
      "text": "Hello word this is a test",
      "confidence": 0.93
    }
  },
  "disagreements": [
    {
      "position": 1,
      "options": ["world", "word"],
      "chosen": "world"
    }
  ],
  "llm_reasoning": "Chose 'world' based on higher Google confidence and contextual fit"
}
```

---

## Configuration

### Environment Variables (.env)

```env
# Flask
FLASK_SECRET_KEY=your-secret-key
FLASK_PORT=5001
FLASK_DEBUG=True

# Google Cloud STT
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GOOGLE_CLOUD_PROJECT=your-project-id

# OpenAI (Whisper + GPT-4)
OPENAI_API_KEY=sk-...

# Anthropic Claude (optional)
ANTHROPIC_API_KEY=sk-ant-...

# LLM Settings
CONSOLIDATION_LLM=openai  # or 'anthropic'
CONSOLIDATION_MODEL=gpt-4-turbo-preview
CONSOLIDATION_CONTEXT_WINDOW=5  # Number of previous sentences

# Audio Processing
SAMPLE_RATE=16000
AUDIO_CHANNELS=1
CHUNK_DURATION_MS=1000

# Database
DATABASE_URL=sqlite:///data/transcriber.db
```

---

## Development Phases

### Phase 1: Single Engine MVP ✅
- [ ] Flask + SocketIO setup
- [ ] WebSocket audio streaming
- [ ] Google Cloud STT integration
- [ ] Basic transcript output
- [ ] Database models
- [ ] Session management

### Phase 2: Dual Engine Processing
- [ ] Add OpenAI Whisper integration
- [ ] Audio Distributor service
- [ ] Parallel processing (asyncio.gather)
- [ ] Store both raw transcripts
- [ ] Simple merge (choose higher confidence)

### Phase 3: LLM Consolidation
- [ ] OpenAI GPT-4 integration
- [ ] Consolidation prompt engineering
- [ ] Smart word-by-word comparison
- [ ] Disagreement detection
- [ ] Context-aware merging

### Phase 4: Confidence Visualization
- [ ] Word-level confidence calculation
- [ ] Engine agreement tracking
- [ ] Color coding logic
- [ ] Disagreement highlighting

### Phase 5: Quality & Performance
- [ ] Error handling (engine failures)
- [ ] Retry logic
- [ ] Performance optimization
- [ ] Load testing
- [ ] Logging and monitoring

### Phase 6: Advanced Features
- [ ] Multiple concurrent sessions
- [ ] Language detection
- [ ] Custom vocabulary
- [ ] Export formats (JSON, SRT, VTT)

---

## Testing

### Unit Tests
```bash
pytest tests/test_audio_distributor.py
pytest tests/test_consolidation.py
pytest tests/test_stt_engines.py
```

### Integration Test with VLC
Stream test audio file:
```python
# tests/stream_test_audio.py
import asyncio
import websockets
import base64

async def stream_audio():
    uri = "ws://localhost:5001/transcribe"
    async with websockets.connect(uri) as ws:
        # Start session
        await ws.send(json.dumps({
            "action": "start_session",
            "session_id": "test-123"
        }))

        # Stream audio file
        with open("test.wav", "rb") as f:
            while chunk := f.read(4096):
                await ws.send(json.dumps({
                    "action": "audio_chunk",
                    "session_id": "test-123",
                    "audio_data": base64.b64encode(chunk).decode()
                }))

                # Receive transcript
                response = await ws.recv()
                print(json.loads(response))

                await asyncio.sleep(0.1)

asyncio.run(stream_audio())
```

---

## Deployment

### Development
```bash
python run.py
# Runs on http://localhost:5001
```

### Production
```bash
# Using Gunicorn with eventlet
gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5001 app:app
```

### Docker
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5001
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "app:app"]
```

---

## Performance Considerations

### Latency Sources:
1. **Google STT API**: ~200-500ms
2. **Whisper API**: ~300-800ms
3. **LLM Consolidation**: ~500-1500ms (depends on context length)

**Total latency:** ~1-3 seconds per chunk

### Optimizations:
- Use streaming STT APIs where possible
- Cache LLM context (don't resend full history)
- Parallel processing of engines (asyncio)
- Consider interim results (lower latency, lower confidence)

---

## Roadmap

**Current State:** Planning
**Next:** Implement Phase 1 MVP
**Goal:** Production-ready transcription service

---

## Related Project

This service is used by **memoAgent** for meeting transcription.
See: `beliczki/memoAgent` repository
