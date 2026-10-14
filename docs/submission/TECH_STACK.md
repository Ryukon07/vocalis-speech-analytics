# Vocalis technology stack

**Languages:** Python, TypeScript, JavaScript, HTML, CSS and SQL.

| Part | Technologies |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy |
| Database | SQLite; SQLAlchemy ORM and Alembic migrations |
| Transcription | Faster-Whisper medium, CTranslate2, CPU int8 |
| Independent clarity recognition | Faster-Whisper base.en |
| Word alignment | Pretrained wav2vec2 CTC, PyTorch, TorchAudio |
| Acoustic features and dataset edits | librosa, pYIN, NumPy, SciPy, Praat/Parselmouth |
| Charts and audio playback | Recharts, WaveSurfer.js |
| Microphone capture | Browser getUserMedia, Web Audio API and AudioWorklet |
| Spoken feedback | Browser Web Speech API with a local English voice |
| Reports | JSON, CSV, PDF; ReportLab |
| Testing | pytest, Vitest, Testing Library, Playwright |
| Runtime/build tools | Python, Node.js, npm |
| Source hosting | Git and GitHub |
| Free report hosting | GitHub Pages, independent of the project laptop |
| Temporary full inference preview | Cloudflare Tunnel, requires the serving laptop online |

The speech recognition/alignment networks are pretrained. We implement the paired dataset, acoustic comparison, transparent scoring, temporal flaw grounding and dashboard; we do not claim training a new deep neural network. The GitHub Pages version displays saved real results and cannot run new speech inference.
