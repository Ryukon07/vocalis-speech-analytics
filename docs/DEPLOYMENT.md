# Deployment and submission preview

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
