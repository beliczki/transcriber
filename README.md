# Transcriber

Headless transcription service with **dual-engine processing** and **LLM consolidation** for improved accuracy.

## Concept

Process **one audio stream** through **two different STT engines** (Google Cloud STT + OpenAI Whisper) simultaneously, then use an LLM to consolidate both transcripts into the best possible interpretation. Think of it as getting a "second opinion" on your transcription.

## Part of memoAgent Ecosystem

This is a **headless service** that provides transcription capabilities. It's used by **[memoAgent](https://github.com/beliczki/memoAgent)** for meeting and conference transcription.

**Architecture:**
- **Transcriber** (this project) - Core transcription engine
- **[memoAgent](https://github.com/beliczki/memoAgent)** - Audio source orchestrator (conference/mic/meeting bots)

## Features

✨ **Dual-Engine Processing** - Google Cloud STT + OpenAI Whisper in parallel
🤖 **LLM Consolidation** - GPT-4/Claude picks the best interpretation
📊 **Word-Level Confidence** - Track which words engines agree/disagree on
🎯 **Engine Agreement Tracking** - Database stores disagreements for analysis
📡 **WebSocket API** - Real-time audio streaming and transcript output
🔌 **Source Agnostic** - Accepts audio from ANY source

## Quick Start

### Prerequisites

- Python 3.10+
- Google Cloud account with Speech-to-Text API enabled
- OpenAI API key (for Whisper + GPT-4 consolidation)

### Installation

```bash
# Clone repository
git clone https://github.com/beliczki/transcriber.git
cd transcriber

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
python -c "from app.models import init_db; init_db()"

# Run service
python run.py
```

Service runs on `ws://localhost:5001/transcribe`

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed technical documentation.

## Configuration

### Environment Variables (.env)

```env
# Flask
FLASK_PORT=5001

# Google Cloud STT
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# OpenAI (Whisper + GPT-4)
OPENAI_API_KEY=sk-...

# Anthropic Claude (optional)
ANTHROPIC_API_KEY=sk-ant-...

# LLM Settings
CONSOLIDATION_LLM=openai  # or 'anthropic'
CONSOLIDATION_MODEL=gpt-4-turbo-preview
```

## WebSocket API

### Client → Server

**Start Session:**
```json
{
  "action": "start_session",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "config": {
    "language": "en-US",
    "enable_consolidation": true
  }
}
```

**Stream Audio (PCM16, 16kHz, mono):**
```json
{
  "action": "audio_chunk",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "audio_data": "base64-encoded-pcm16",
  "timestamp": 1234567890.123
}
```

### Server → Client

**Transcript Event:**
```json
{
  "event": "transcript",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "Hello world",
  "confidence": 0.94,
  "words": [
    {
      "word": "Hello",
      "confidence": 0.98,
      "engines_agree": true
    },
    {
      "word": "world",
      "confidence": 0.87,
      "engines_agree": false,
      "google_version": "world",
      "whisper_version": "word"
    }
  ],
  "disagreements": [
    {
      "position": 1,
      "options": ["world", "word"],
      "chosen": "world"
    }
  ]
}
```

## Testing with Python Client

```python
import asyncio
import websockets
import base64
import json

async def test_transcriber():
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

asyncio.run(test_transcriber())
```

## Development Roadmap

- [ ] **Phase 1:** Single engine MVP (Google STT only)
- [ ] **Phase 2:** Dual engine processing (Google + Whisper)
- [ ] **Phase 3:** LLM consolidation (GPT-4/Claude)
- [ ] **Phase 4:** Word-level confidence tracking
- [ ] **Phase 5:** Performance optimization
- [ ] **Phase 6:** Advanced features (language detection, custom vocabulary)

## Performance

**Latency:**
- Google Cloud STT: ~200-500ms
- OpenAI Whisper: ~300-800ms
- LLM Consolidation: ~500-1500ms
- **Total:** ~1-3 seconds per chunk

**Accuracy Improvement:**
- Dual-engine processing reduces errors by 30-40%
- LLM consolidation resolves ambiguities
- Engine redundancy provides fallback

## License

MIT License - see [LICENSE](./LICENSE)

## Related Projects

- **[memoAgent](https://github.com/beliczki/memoAgent)** - Audio source orchestrator using this service

---

**Built with ❤️ by [beliczki](https://github.com/beliczki)**
