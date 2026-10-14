"""Save final browser evidence and refresh project verification documentation."""
from pathlib import Path
import json
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]

def main():
    raw = json.loads((ROOT/'tmp/browser-checks/results.json').read_text(encoding='utf-8'))
    assert raw['stats']['unexpected'] == 0 and raw['stats']['expected'] == 7 and raw['stats']['skipped'] == 0, raw['stats']
    cases = []
    def walk(suite):
        for spec in suite.get('specs', []):
            for test in spec['tests']:
                assert test['status'] == 'expected' and test['results'][-1]['status'] == 'passed'
                cases.append(dict(name=spec['title'], status='passed', duration_ms=test['results'][-1]['duration']))
        for child in suite.get('suites', []): walk(child)
    for suite in raw['suites']: walk(suite)
    microphone = json.loads((ROOT/'tmp/browser-checks/microphone-capture.json').read_text())
    summary = dict(app_version='3.1.3', checked_at=datetime.now(timezone.utc).isoformat(), browser='Isolated Playwright Chromium, headless, localhost', computer_use_skill_used=False, tests=cases, microphone=microphone,
        boundaries=['Automated microphone uses a public file-backed media device; physical Realtek capture and clear speaker feedback were previously confirmed by the user in Brave.', 'Browser exports completed via Chromium download events and verified file bytes; native Brave Save-dialog interaction is outside this automated suite.', 'Print button invocation, print CSS and headless PDF rendering are checked; native Brave print preview was previously inspected.'],
        no_remaining_local_implementation_checks=True)
    (ROOT/'docs/benchmarks/automated-browser-verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    accuracy=json.loads((ROOT/'docs/benchmarks/transcription-accuracy.json').read_text())
    assert accuracy['passed'] and all(s['repeats_identical'] for s in accuracy['samples'])
    baseline=json.loads((ROOT/'docs/benchmarks/draft-model-baseline.json').read_text())
    old_path=ROOT/'docs/benchmarks/browser-verification.json'
    old=json.loads(old_path.read_text())
    old['historical_app_version']=old['app_version']; old['app_version']='3.1.3'
    old['automated_follow_up']='automated-browser-verification.json'
    old['remaining_live_checks']=[]
    old['transcript_review_policy']='All ASR drafts require recording review; exact accuracy of the private full microphone recording is not claimed.'
    old['regressions']=dict(backend_tests_passed=64,frontend_tests_passed=24,browser_tests_passed=7,production_build_passed=True,dependency_check_passed=True,npm_audit_vulnerabilities=0)
    old['recognition']['production_model']='Pinned medium default for drafts; base.en for independent clarity; optional base.en draft selection with medium quality fallback'
    old['findings_fixed'].append('Switching participant recordings clears stale transcript text')
    old['findings_fixed'].extend(['Versioned native pitch cache replaces the crashing legacy pYIN cache', 'Mobile hero content fits its grid', 'Scrolling tables contain absolutely positioned screen-reader labels', 'Website favicon prevents browser 404 errors'])
    old_path.write_text(json.dumps(old,indent=2)+'\n',encoding='utf-8')
    paragraph=f"Four fixed, newly downloaded LibriSpeech validation clips were each transcribed three times through the actual API (12 jobs per model). Draft WER fell from {baseline['aggregate_wer']*100:.2f}% with base.en to {accuracy['aggregate_wer']*100:.2f}% with medium. Repeats were identical for every clip. The conservative comparison counts Mr. versus MISTER as substitutions; one proper-name spelling remains wrong. No gold transcript was supplied to recognition. This is a clean, one-reader sample check, not universal accuracy or an assurance of absence from upstream training."
    verification=f'''# Verification

The completed local target is Vocalis 3.1.3 on Windows, Python 3.12, Node.js 24.15 and CPU-only PyTorch 2.8, using a 16 GB Intel i5-10200H laptop. GitHub and YouTube publication are deferred by the user.

## Final regression and browser checks

64 backend tests and 24 frontend tests passed; TypeScript/Vite production build, pip dependency check and npm audit passed (zero reported vulnerabilities). Vitest was upgraded to 5.0.4 to remove critical/moderate transitive advisories. An AnyIO deprecation warning remains informational.

All seven isolated Chromium browser checks passed against the real localhost services, without computer use:

1. Settings density/default persistence, capability-limited choices, rubric weight validation, creation, edit/versioning and deletion.
2. Annotation taxonomy, exact interval bounds, editing and deletion.
3. Real completed medium-model draft restoration into the editable wizard; switching recordings clears stale words.
4. Actual upload, API transcription, transcript confirmation, five-step submission, real CTC/acoustic inference and available clarity result.
5. File-backed simulated microphone through the actual AudioWorklet, signal/duration validation, audible-media timeline preview, PCM WAV upload and retrieval.
6. Report playback/pause, speed, word/flaw seeking, every acoustic chart, recognition/evidence disclosure, speech voice handling, completed JSON/CSV/PDF downloads and print invocation/CSS/PDF rendering.
7. Landing/workspace pages at mobile width, document overflow checks, invalid-upload feedback, unavailable-route recovery and navigation.

Native stability: the legacy compiled Numba cache reproduced a Windows access violation inside pYIN interpolation. A fresh compiler cache passed two independent worker/process runs with matching pitch arrays, and the versioned production cache passed two more. The real browser analysis and seven API comparisons also passed. The runtime now separates native caches by Python/Numba/librosa/NumPy versions; acoustic methods and frozen benchmark identities are unchanged. Startup enables faulthandler diagnostics.

Detailed public evidence: [automated browser checks](benchmarks/automated-browser-verification.json). Test traces, downloaded files and screenshots stay under tmp/browser-checks and are excluded from the shareable package. The browser suite checks that no page exceptions or error-level console messages occur. QA-created rubrics, annotations, analyses, references and microphone/upload recordings are removed afterwards; the four public accuracy recordings are retained.

## Transcription accuracy

{paragraph}

Gold text, SHA-256 hashes, source/license, recognized text, edit counts and timings are saved in [accuracy results](benchmarks/transcription-accuracy.json), [baseline](benchmarks/draft-model-baseline.json) and dataset/asr_checks/manifest.json. The default draft recognizer is medium, CPU int8; TRANSCRIPTION_MODEL=base.en selects faster drafts with medium as the optional empty/unreliable-output retry. ASR_MODEL=base.en independently controls clarity, preserving the frozen scoring configuration.

The user previously confirmed clear physical microphone playback and clear spoken feedback in Brave. The original 50.98-second microphone recording now has a completed 29-word medium draft, but there is no verified exact gold transcript for that full private recording. Draft confirmation remains a normal product step; this recording is not used to claim accuracy. Private audio/text remain excluded from the package. Automated microphone capture uses public speech and does not claim a new physical-device test. Headless speech checks exercise OS voices if available or the actionable missing-voice state; the human listening confirmation establishes physical speaker output.

## Genuine speech benchmark and clarity

The frozen four-category v3.0 delivery benchmark completed 70/70 real inferences. Predictions match by type and interval IoU >= 0.25. Testing holds out Eisenhower; training and validation use different Reagan sources.

| Split | Files | Precision | Recall | F1 | Boundary MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 28 | 0.875 | 0.875 | 0.875 | 0.430 s |
| Validation | 21 | 0.824 | 0.778 | 0.800 | 0.320 s |
| Testing | 21 | 0.727 | 0.889 | 0.800 | 0.288 s |
| All | 70 | 0.810 | 0.850 | 0.829 | 0.355 s |

Ground truth records controlled acoustic edits, not human-rated rhetorical quality. Full predictions, hashes and split boundaries remain under benchmarks/.

Clarity is an independent recognition proxy: 100 * (1 - min(1, max(0, participant WER - reference WER))). It requires at least eight normalized words and reference WER <= 25%; unavailable clarity is excluded from the weighted average. Three identical-source controls scored 100; nine noise checks verified additional recognition errors. At -5 dB, the three excerpts scored 43.2, 3.6 and 21.1. Some milder noise improves ASR, so this is not a monotonic noise metric or a human pronunciation diagnosis. Exact results are in benchmarks/clarity-verification.json.

Seven five-category website comparisons passed, along with a separate noisy report (clarity 83.6, overall 95.33, four localized feedback regions). API verification covers result persistence, participant-aligned curves, word timestamps, audio ranges and all exports. Historical results retain their provider/rubric snapshots; the current independent draft model does not rewrite them.

## Documents and local scope

The six-page technical document and two-page real report are regenerated and rendered for visual verification before packaging. The project archive excludes .env credentials, user recordings/databases, model weights, browser profiles and test traces. The local walkthrough video and transcript remain available; publication is deferred.

Windows/local SQLite is the verified execution target. Docker files are supplied, but Docker is not installed on this laptop; PostgreSQL and public multi-user hosting are outside this local completion. Native Brave print/playback/chart/word/flaw/voice checks from earlier turns remain historical evidence in browser-verification.json. The previously unfinished editor/settings/draft/export software checks are now covered by the completed Chromium suite; native Brave Save-dialog automation is not claimed.

## Reproduce

Run scripts/verify-local.ps1 for regression/build/dependency checks. With the website running, run scripts/verify_real_workflow.py and scripts/verify_transcription_accuracy.py. On a fresh machine, scripts/install-browser-checks.ps1 installs an isolated Chromium into model-artifacts/playwright; then run npm run test:e2e in frontend. The four public test WAVs are bundled, and scripts/download_asr_checks.py downloads them again if needed. Browser checks need at least one real report from verify_real_workflow.py and the accuracy jobs in the current local database.
'''
    (ROOT/'docs/VERIFICATION.md').write_text(verification,encoding='utf-8')
    p=ROOT/'README.md'; text=p.read_text(encoding='utf-8')
    text += '\n## Final transcription and browser verification (3.1.3)\n\n'+paragraph+'\n\nAll seven Chromium end-to-end checks passed, including the real wizard/inference, microphone worklet, settings/rubrics, annotation editing, completed report downloads, responsive pages and voice handling. Final checks: 64 backend tests, 24 frontend tests, production build, pip check and zero npm audit vulnerabilities. See docs/VERIFICATION.md for precise physical-device and automated-test boundaries. Run scripts/install-browser-checks.ps1 once, then npm run test:e2e from frontend to reproduce.\n'
    p.write_text(text,encoding='utf-8')
    p=ROOT/'docs/ML_INTEGRATION.md'; text=p.read_text(encoding='utf-8')
    text += '\n## Independent draft default (3.1.3)\n\n'+paragraph+'\n\nTRANSCRIPTION_MODEL=medium selects the higher-accuracy draft default; ASR_MODEL=base.en preserves clarity recognition and its cache signature. TRANSCRIPTION_FALLBACK_MODEL=medium only performs a retry when a different primary draft model is selected. A completed job records its actual model. Switching participant recordings clears transcript text so old words cannot be submitted against new audio.\n'
    p.write_text(text,encoding='utf-8')
    native=dict(observed_failure='Windows native access violation in librosa pYIN _parabolic_interpolation / Numba gufunc from the legacy compiled cache', fix='Fresh v2 compiler-cache namespace keyed by Python/Numba/librosa/NumPy versions', verification='Two clean-cache process runs and two production-cache process runs; finite voiced pitch arrays match at rtol=1e-6 with NaNs preserved; real browser inference and seven API comparisons pass', pitch_method_changed=False)
    (ROOT/'docs/benchmarks/native-pitch-verification.json').write_text(json.dumps(native,indent=2)+'\n',encoding='utf-8')
    print('Saved seven passed browser checks and final verification documentation.')

if __name__=='__main__':main()
