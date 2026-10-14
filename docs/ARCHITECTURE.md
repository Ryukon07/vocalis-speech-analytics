# Architecture

## Boundaries

Vocalis manages workflow and evidence presentation. Local speech processing sits behind `SpeechAnalysisProvider`. No frontend or route performs inference. HTTP schemas and provider outputs are Pydantic contracts, and frontend types mirror those shapes.

The compact implementation combines entity definitions in `models/entities.py`, schemas in `schemas/contracts.py` and routes in `api/router.py`. Services retain the substantive storage, analysis, dataset-validation and export logic. `repositories/database.py` handles sessions, retrieval and pagination. This avoids many empty per-entity modules while preserving architectural layers.

## Request flow

1. Client validates a file and uploads multipart `file` plus `category`.
2. Recording service checks format/size/signature, stores a managed UUID key and persists metadata. WAV parsing reads header metadata; it is not an acoustic-analysis algorithm.
3. Client submits a recording ID, reference ID, rubric ID, transcript and supported settings with an idempotency key.
4. Analysis service resolves IDs, validates provider capabilities and same-text reference requirements, snapshots rubric/version/settings, and inserts a queued job.
5. LocalRunner executes a registered provider on a worker thread, supplies internally resolved paths and persists progress after callbacks.
6. Result validation checks finite scores/measurements, ranges, timestamp ordering, duration bounds, provider identity and weighted overall score consistency.
7. Result summaries and indexed flaw records enter the database. Feature arrays are serialized to managed JSON files with indexed `feature_series` rows referring to them.
8. Frontend polls saved status, fetches the completed typed result and displays available evidence. JSON/CSV exports reconstruct that same stored result.

## Persistence

Recording and Reference are separate: audio metadata can exist without baseline eligibility. References point at managed recordings and carry transcript and optional processed profile metadata. ContrastiveGroup points at a source recording; Variant links paired recordings, quality level, flaw labels and provenance. Split belongs to the group; service validation prevents a recording appearing in different splits, whether used as source or variant. Annotation is attached to a recording and represents manual ground truth, independent of detected model flaws.

Analysis stores scalar searchable status/score/provider fields and variable settings/rubric/result summaries. DetectedFlaw stores indexed category/type and bounds plus evidence payload. FeatureSeries keeps unit, metadata and a managed artifact key, avoiding large array columns. Relationships use explicit foreign keys. Recording/reference/rubric deletion is restricted when a job needs them. Analysis deletion cascades its database children and removes managed feature files. Groups cascade variants but preserve recordings and labels.

SQLite foreign keys and WAL are enabled per connection. Alembic creates the schema explicitly. PostgreSQL schema creation uses the same migration and SQLAlchemy types, with `psycopg`; data migration is separate.

References consumed by saved analyses cannot switch their audio, transcript or profile; metadata such as title/license remains editable. This prevents retrying or displaying an older job against silently replaced baseline inputs.

## Jobs and failure semantics

Statuses: `queued -> processing -> completed | failed | cancelled`. Progress stage text comes from the configured provider; mock stages say `Demo simulation`. Each submitted attempt gets an in-memory token so an old timed-out/cancelled attempt cannot overwrite a later retry. A watchdog marks overdue jobs failed even if no callback arrives. Errors expose safe summaries, not provider internals or file paths. Restart recovery marks saved queued/processing jobs failed. Retries require matching provider name, version and execution mode.

The process lock serializes local transitions and persistence with cancellation. A unique idempotency key plus request hash protects submissions. A repeated successful submission returns the existing job; mismatched payloads return conflict.

Replace `JobRunner` and the local runner attachment in application lifespan for a durable queue. Cancellation and timeout are cooperative; the prototype cannot kill arbitrary Python threads. A real deployment should isolate heavy inference in worker processes with heartbeat, leases and hard timeouts. Run only one server worker with LocalRunner.

## UI and evidence

TanStack Query owns server state; React Hook Form/Zod validate the analysis form. Radix Dialog handles focus trapping, Escape and accessible labels for metadata and destructive confirmation dialogs. Mutations invalidate queries and show success only after backend confirmation.

WaveSurfer renders actual audio waveforms, with interval overlays, speed and click-to-seek. Transcript positions use supplied word timestamps. Recharts plots merge explicit timestamps without manufacturing shared sample rates. Missing values remain null/unavailable. `participant_aligned` reference features share participant time; `recording` reference features use their own recording clock. Only aligned overlays highlight participant flaws across both curves.

Demo mode appears on reports and history. Mock scores/curves/word positions are never described as measured. Aggregated delivery averages and common flaws require real results. Every flaw retains evidence provenance and separate interpretation provenance; generated explanation text cannot modify its evidence object.

## Operational limits

Authentication, durable external workers, retention, production proxy limits and public hosting are outside this local prototype. Storage exposes safe materialization paths to providers; an object-store adapter must stage managed objects locally. Filesystem and SQL transactions are not atomic together; add orphan reconciliation for crash recovery. Frontend and backend builds are independent and configured by environment variables.

## Local transcription

Persisted transcription jobs use a dedicated single-thread runner and the shared inference lock. Drafts remain separate from confirmed recording metadata. Restart, timeout and cancellation reject late output. Source speech IDs enforce split isolation across different excerpts of one source.

Draft model selection (`TRANSCRIPTION_MODEL`, default medium) is independent of the frozen clarity recognizer (`ASR_MODEL`, default base.en). The larger draft default improves measured recognition without changing historical clarity scoring or cache identities.

## Clarity and speech controls

The evaluator optionally runs independent unprompted ASR on both recordings. clarity_analysis.py calculates normalized word edits and a reference-relative recoverability score. Persisted results include typed recognition evidence and phrase intervals; no frontend calculation determines the score. A new five-category rubric preserves historical snapshots.

Microphone capture uses AudioWorklet PCM, stops media tracks on teardown, rejects silence and handles device/processor failures. Spoken feedback chunks long text, chooses local English voices, keeps utterances alive, cancels on report/selection changes and displays start/playback errors. Component tests cover these paths; live physical-device behavior requires a browser check.
