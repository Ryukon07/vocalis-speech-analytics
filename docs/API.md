# API contracts

The running `/docs` and `/openapi.json` are authoritative field-level documentation. All public IDs are UUIDs; paths and storage keys never appear in public recording responses.

| Resource | Operations |
| --- | --- |
| `/health`, `/providers`, `/providers/capabilities` | GET |
| `/recordings` | POST multipart, GET paginated/search/category |
| `/recordings/{id}` | GET, PATCH partial metadata, DELETE |
| `/recordings/{id}/audio` | GET inline audio, byte ranges supported |
| `/references` | POST, GET paginated/search/eligibility |
| `/references/{id}` | GET, PATCH full editable payload, DELETE |
| `/rubrics` / `/rubrics/{id}` | List/create, get/full edit/delete |
| `/analyses` | POST async with optional Idempotency-Key, GET paginated/search/status |
| `/analyses/{id}` | GET persisted job, DELETE terminal job |
| `/analyses/{id}/result` | GET completed typed result |
| `/analyses/{id}/retry` / `cancel` | POST |
| `/analyses/{id}/export/json` / `csv` | GET actual stored report |
| `/datasets/groups` / `/datasets/groups/{id}` | List/create, get/full edit/delete |
| `/datasets/groups/{id}/variants` | POST linked paired variant |
| `/datasets/groups/{id}/variants/{variant_id}` | DELETE link, retain audio |
| `/datasets/annotations` | GET (optional recording_id), POST |
| `/datasets/annotations/{id}` | PATCH full editable payload, DELETE |
| `/dashboard` | GET persisted totals plus real-only score/flaw aggregates |

Lists return `{items,total,offset,limit}`. Default limit 20, maximum 100. Search strings are parameterized via SQLAlchemy. Errors return `{error:{code,message,details?}}`; validation details contain field names and safe messages, never input values. Missing IDs: 404. Unsupported audio: 415. Size limit: 413. Conflict/in-use/not-ready: 409. Unsupported input: 400. Unavailable provider: 503.

Manual transcripts are embedded text records rather than a separate transcript table. References link an existing recording and supplied transcript. Rubric weights must total 100 across enabled categories. For each job, scoring considers its enabled categories and available scored dimensions, renormalizes those weights and validates the returned overall score. All-unavailable dimensions require null overall score.

Recording mode requires identical whitespace-tokenized transcripts for participant/reference; differences are reported rather than hidden. Profile mode requires populated reference profile metadata and advertised provider support. The mock advertises only recording mode and does not transcribe. Pipeline window and overlap settings are configurable only when the provider advertises them.

Flaw and word intervals contain explicit seconds. The result includes known participant duration and optional reference duration. Feature series use `{time_seconds,value}` points (value nullable), unit and `time_axis`. Arbitrary feature names are allowed so a new scalar acoustic series can render without frontend changes; an MFCC vector can be exposed as `mfcc_1`, `mfcc_2`, etc. Full raw matrices should use a future artifact contract, not an enormous JSON response.

GET /analyses/{id}/export/pdf consumes the exact stored result and rubric snapshot. It preserves real/mock labels, draws aligned acoustic curves and includes measured flaw evidence. Browser printing remains available.

## Local transcription endpoints

POST /recordings/{id}/transcriptions creates a persisted local ASR draft job. GET /transcriptions/{id} polls it. POST /transcriptions/{id}/cancel cancels active processing. Drafts do not overwrite confirmed text.

`TRANSCRIPTION_MODEL` selects the draft model (default `medium`); the job's `model_name` records the actual model used. `ASR_MODEL=base.en` remains the independently configured clarity recognizer. Optional `TRANSCRIPTION_FALLBACK_MODEL=medium` retries empty/unreliable drafts when a smaller draft model has been explicitly selected.

Real speech inputs are limited to 0.5-180 seconds. Real windows require at least 0.5 seconds. Group source_id keeps all excerpts of a source speech in the same split. The local provider supports English and all five categories. Select clarity explicitly in settings.enabled_categories and use a rubric with nonzero clarity weight. Legacy API defaults retain the four acoustic delivery categories.

Provider 3.1 adds optional AnalysisResult.clarity: availability, score, method, model, confirmed word count, baseline gates, independently recognized reference/participant texts, edit counts, raw WER and excess WER. Old saved results omit this field. recognition_difficulty flaws use category clarity and measured phrase WER; they do not claim phoneme-level diagnosis. Unavailable clarity is excluded from weighted overall scoring.
