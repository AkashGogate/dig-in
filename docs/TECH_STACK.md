# Actual stack and candidate adapters

| Component | Current source / status |
| --- | --- |
| Backend | Python 3.11+, FastAPI, uvicorn; `backend/pyproject.toml` + `uv.lock` own dependencies |
| Coordination state | Single-process in-memory domain with lock; demo sessions; no production persistence/auth |
| Frontend | Static HTML/CSS/JS, served by any static HTTP server; no npm setup/build required |
| Legacy call log | SQLAlchemy + aiosqlite SQLite; separate from coordination state |
| Legacy voice experiment | Deepgram WebSocket/prerecorded modules; Pipecat code retained with optional `live-pipeline` dependency extra; paid live integration needs configuration and verification |
| Tests/eval | pytest; transcript fixtures; synthetic WAV corpus; local mock/Deepgram eval harness |
| Position/camera/structured read-back | Mock/disabled seams; actual board, sensors, streams, accuracy, and live capture not established |
| Candidate speech output | ElevenLabs optional; not a required paid dependency |
| Optional analytics | Databricks lane only; no critical-path database dependency |
| POS/payment | Standalone demo; future research only, no real cards/payments |

Qualcomm Arduino UNO Q ingestion is the intended hardware work lane, not a verified board capability. Exactly two conceptual kitchen views do not imply two proven simultaneous real-time model feeds. Prize category/rules remain unverified. Existing Fly/Docker/CI files are retained scaffolding; no deployment is performed by this change. Coval is not integrated; mock eval is not STT quality evidence.
