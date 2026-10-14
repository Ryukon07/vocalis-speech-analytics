# Dataset source and reuse notes

Reviewed 14 October 2026. This document distinguishes the original historical recordings, our controlled transformations/labels, and supplementary ASR samples. It does not apply one invented Creative Commons license to all audio.

## Historical contrastive corpus

| Source | Primary archive evidence | Reuse basis and provenance |
| --- | --- | --- |
| Reagan, Challenger address, 28 January 1986 | [Official audio gallery](https://www.reaganlibrary.gov/galleries/audio-recordings-01281986-launch-sts-mission-51-l), WHCA tape PP6028B, National Archives identifier 7087577 | White House Communications Agency audio collection, which the [Reagan Library describes as public domain](https://www.reaganlibrary.gov/archives/audiovisual/white-house-communications-agency). The two supplied Reagan MP3s have Miller Center-style filenames; the corpus excerpts match the dated public speech and published text. The original supplied-file download receipt was not retained and no byte identity with the WHCA MP3 is claimed. |
| Reagan, farewell address, 11 January 1989 | [Official audio inventory entry](https://www.reaganlibrary.gov/archives/audio/remarks-president-reagan-during-farewell-address-nation-oval-office), WHCA tape PP9011B, National Archives identifier 7087581 | Same official WHCA audio collection public-domain basis. Source text is linked in the manifest; the local supplied-file provenance qualification above applies. |
| Eisenhower, farewell address, 17 January 1961 | [Official speech and audio](https://www.eisenhowerlibrary.gov/research/online-documents/farewell-address); audio file downloaded from that Library's website. The [subject guide](https://www.eisenhowerlibrary.gov/sites/default/files/research/subject-guides/pdf/farewell-address-january-17-1961.pdf) identifies U.S. Army Signal Corps recording EL-D16-138 RA. | Federal government recording. The [Library's Online Documents page](https://www.eisenhowerlibrary.gov/research/online-documents) states that its listed digitized items are public domain. The retained download-status file records the official MP3 URL and normalized-audio hash. |

The historical speech/audio reuse basis is U.S. public-domain government material, supported by the collection/item evidence above. This is a documented archive-based assessment, not a newly issued license or a claim that every item at the National Archives is unrestricted. The Reagan Library explicitly distinguishes its public-domain WHCA **audio** from videotapes, many of which have copyright restrictions. No third-party news footage, music, archive logos or broadcast introductions are deliberately included in the paired excerpts.

Audio excerpts were cropped, converted to mono 16 kHz PCM, and transformed with time stretching, gain changes, pause insertion and pitch flattening. Every transformation and SHA-256 is recorded in `contrastive/manifest.json`. The supplementary combined-severe sample derives from the same Challenger reference. Attribution: Ronald Reagan/Dwight D. Eisenhower; White House Communications Agency/U.S. Army Signal Corps; National Archives and the respective Presidential Libraries. Miller Center, University of Virginia, supplied the linked presidential speech transcripts/source pages.

The public-domain statements describe U.S. copyright status. Archive attribution does not certify every possible use or jurisdiction. The [National Archives' permissions guidance](https://www.archives.gov/research/still-pictures/permissions) explains the distinction between federal works and restricted third-party holdings. We do not imply endorsement by the speakers, their estates, archives or libraries.

## Project-authored labels and documentation

Ryucoders releases the construction scripts, transformation parameters, manifests, annotations and project documentation under the repository MIT license, to the extent the team holds rights in those contributions. That license does not privatize or relicense the underlying government recordings. Word alignments are model-generated; edit labels describe known controlled modifications.

## Supplementary recognition samples

`asr_checks/` contains four LibriSpeech excerpts licensed **CC BY 4.0**. Credit Vassil Panayotov, Daniel Povey, Guoguo Chen and Sanjeev Khudanpur, with readings from LibriVox. Source: [LibriSpeech/OpenSLR](https://www.openslr.org/12/) and the Hugging Face dataset referenced in its manifest. Only lossless FLAC-to-PCM-WAV conversion was applied. See [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

`clarity/` contains noise transformations of attributed contrastive excerpts; they retain the original speech's reuse basis. Locally uploaded user microphone recordings, SQLite databases, model weights and credentials are excluded from GitHub and the submission package. Unused reference candidates in the source catalog are not claimed to be licensed, downloaded or part of the released audio corpus.
