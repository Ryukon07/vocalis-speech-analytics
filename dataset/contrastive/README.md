# Vocalis controlled contrastive dataset

Ten reference excerpts and seventy variants use matching transcripts. Audio is mono 16 kHz PCM WAV. manifest.json records paths, hashes, transcripts, alignment, source provenance, split, severity and exact edit bounds.

## Spectrum

| Variant | Transformation | Label |
| --- | --- | --- |
| Near-perfect | Global gain 0.95 | No injected flaw |
| Rushed mild | Local time stretch 1.35x | Rushed pacing, level 2 |
| Rushed severe | Local time stretch 1.8x | Rushed pacing, level 5 |
| Slow | Local time stretch 0.6x | Slow pacing, level 4 |
| Pause | Insert 2.2 s mid-phrase | Awkward pause, level 4 |
| Low energy | Local gain 0.08 | Low energy, level 4 |
| Monotone | Pitch variation ratio 0.03, overlap-add resynthesis | Monotone delivery, level 4 |

Edits affect about eight words. Exact mappings record stretching/insertion. Labels describe known edits, not listener-certified judgments.

## Splits and provenance

Training: four Challenger-address excerpts. Validation: three Reagan-farewell excerpts. Testing: three Eisenhower-farewell excerpts. All excerpts/variants of a source stay together. Reagan occurs in training/validation; Eisenhower is held out by speaker.

Explicit time ranges and ASR/source comparisons select passages. wav2vec2 CTC supplies word boundaries. Published text corrections and number spellings stay in transcript.txt.

Source metadata is in ../reference_speeches/sources.json. Original audio stays local and is excluded from Git; recording-specific rights/attribution notes stay with each group.

Primary archive reuse evidence and original-file provenance qualifications are finalized in [dataset license notes](../LICENSE_NOTES.md). No blanket Creative Commons license is claimed for the historical recordings.

Near-perfect means no injected flaw. References are relative baselines, not human-certified ideal delivery. Word alignment is model-generated; flaw labels are exact controlled-edit bounds.

## Reproduction

Run dataset/build_dataset.py to rebuild, dataset/evaluate_dataset.py to evaluate, and backend/app/import_dataset.py to import into the website. Use --from-paired to rebuild variants from the bundled references without original archive downloads. Source acquisition can also be reproduced from retained originals and transcripts.

The importer rejects changed hashes. Edit labels are never detector inputs. Results are in ../../docs/benchmarks/summary.json. Human-reviewed natural recordings are the next dataset extension.
