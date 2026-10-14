# Clarity verification samples

Nine deterministic additive-noise variants (10, 0, -5 dB SNR) of three corpus excerpts, one per source-isolated split. Originals and confirmed transcripts remain in dataset/contrastive. Noise edits use NumPy seed 20261014; samples are gain scaled to avoid clipping. These are separate from the frozen 70-variant delivery benchmark. Reproduce with scripts/verify_clarity.py. Results include hashes and independently recognized texts in docs/benchmarks/clarity-verification.json. This checks recognition sensitivity, not human intelligibility or accent fairness.
