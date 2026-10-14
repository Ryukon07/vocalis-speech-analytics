# Transcription accuracy samples

Four public LibriSpeech clips, selected as rows 0-3 of the clean validation split of [hf-internal-testing/librispeech_asr_dummy](https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy) before recognition was run. Audio is converted from the downloaded lossless FLAC to mono PCM16 WAV at the original 16 kHz rate; gold transcripts are unchanged. The manifest records selection, source, hashes, durations and original text.

LibriSpeech is credited to Vassil Panayotov, Daniel Povey, Guoguo Chen and Sanjeev Khudanpur, with audiobook recordings from LibriVox. Original source: https://www.openslr.org/12/. Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The format conversion is the only audio modification.

Run `scripts/download_asr_checks.py` to download again, then `scripts/verify_transcription_accuracy.py` while the local backend is running. The verifier sends no gold-text prompt, makes three actual API jobs per clip and saves both recognized words and edit counts. Punctuation/case, contractions and numbers are normalized by the project's existing WER function. The literal spelling `Mr.` versus `MISTER` still counts as one substitution; reports preserve this conservative comparison.

This small set has one reader and clean audio. It does not establish accuracy on all accents/noise conditions or prove exclusion from upstream model training. Transcript review remains part of the product workflow.
