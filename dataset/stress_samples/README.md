# Combined delivery stress sample

This supplementary training case combines whole-speech rushing, pitch flattening, local attenuation and two long pauses. The same bundled Challenger reference and shared transcript provide its baseline.

The manifest preserves transformation-derived intervals and parameters. Word alignment must meet the same confidence safeguard as ordinary inputs. The sample is excluded from the frozen seventy-file accuracy benchmark.

Rebuild with dataset/build_stress_sample.py and import/evaluate through the running website with scripts/import_stress_sample.py. The saved standalone and website results demonstrate the combined effect on scoring and detected regions.
