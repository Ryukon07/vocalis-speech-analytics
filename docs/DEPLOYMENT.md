# Deployment and submission preview

## Free hosted report dashboard

https://ryukon07.github.io/vocalis-speech-analytics/ is a GitHub Pages deployment independent of the serving laptop. It uses the real React dashboard with hash routes and a separately configured read-only archive adapter. Ten completed real model reports, 91 allowlisted public recordings, aligned transcripts, evidence curves and JSON/CSV/PDF exports are published. No private microphone data, database, credential or model weight is published.

The viewer supports playback, word/flaw seeking, charts, browser speech synthesis and report downloads. New upload/microphone inference and editing are explicitly unavailable; the interface links to the separate full workspace. The dashboard does not claim a live model connection. A static host cannot run the current Python background workers. Vercel's serverless model also requires substantial backend/storage/job changes for this application; it is not a drop-in full deployment.

Rebuild with `scripts/build_report_archive.py` while the isolated API runs, then from frontend set `VITE_ARCHIVE_MODE=true`, `VITE_PUBLIC_DEMO=false` and run `npm run build -- --base=/vocalis-speech-analytics/ --outDir ../tmp/permanent-demo/site`. Publish with `scripts/publish_report_pages.py` using the existing GitHub credential. Run `node scripts/verify_report_pages.mjs`; it blocks all localhost/tunnel requests while checking the hosted site. Hosting payload is on `gh-pages`; source code remains on `main`.

GitHub Pages is free for public repositories and serves static files: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages. Hosting terms were checked on 14 October 2026: new Docker/Gradio Spaces generally require paid Hugging Face plans, with a limited ZeroGPU Gradio exception for verified personal accounts older than 30 days. No eligible cloud account was available here. Sources: https://huggingface.co/docs/hub/en/spaces-overview and https://huggingface.co/docs/hub/en/spaces-zerogpu.

## Temporary full inference workspace

The current temporary HTTPS preview is https://jackson-nutten-high-taken.trycloudflare.com. It runs the actual speech backend and a separately built frontend through a same-origin proxy; inference stays on the serving laptop CPU. Cloudflare Quick Tunnels have no uptime guarantee and stop when the tunnel stops. Keep the laptop connected to power and the internet for judging.

The source code, dataset and final video are independently available in the public GitHub repository. They remain downloadable if the preview is offline. A durable deployment requires a host/account and persistent storage/model cache; a frontend-only host cannot run the Python/PyTorch speech backend.

## Isolation

`prepare_public_demo.py` copies only SHA-256-allowlisted public corpus audio and selected verified reports into `tmp/public-demo`. The user's microphone recording and private local database are excluded. The API wrapper protects seeded items, assigns new items to anonymous browser sessions, hides other sessions' new records, caps uploads at 12 MB and limits the number of active CPU jobs. This is a temporary prototype; use public/test audio.

## Reproduce the preview

1. Set up the local application and real benchmark reports using README.
2. From backend, run `../.venv/Scripts/python.exe ../scripts/prepare_public_demo.py` once; it refuses to overwrite an existing guest database.
3. From frontend, set `VITE_API_BASE_URL=/api/v1` and `VITE_PUBLIC_DEMO=true`, then run `npm run build -- --outDir ../tmp/public-demo/dist`.
4. Place a checksum-verified official `cloudflared-windows-amd64.exe` at `tools-local/cloudflared.exe`.
5. Run `scripts/start-public-demo.ps1`. The new HTTPS URL appears in `tmp/public-demo/tunnel-errors.log`.
6. Run `scripts/verify_public_demo.py` to exercise HTTPS transcription, private-data exclusion, ownership and downloads.
7. Run `scripts/stop-public-demo.ps1` to stop only these project-owned preview processes.

Starting a new Quick Tunnel produces a new URL; update the README/submission links. The original local site at port 5173 and API at 8000 remain separate. No `.env`, browser cookie, database, model cache or tunnel binary is committed.

## Durable hosting preparation

Dockerfiles and compose configuration are provided for local container execution. Set the public API origin or serve frontend/API behind one HTTPS reverse proxy; configure allowed origins, persistent database/audio/model storage and enough RAM/disk for CPU inference. Import the paired dataset and warm the models before accepting judging requests. Docker execution is not claimed as verified on this laptop, which has no Docker engine.
