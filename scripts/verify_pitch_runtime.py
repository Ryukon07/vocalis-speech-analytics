"""Exercise native pYIN in a worker across process restarts using a selected cache."""
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if len(sys.argv) < 2 or sys.argv[1] == '--runtime-cache':
    sys.path.insert(0, str(ROOT))
    from speech_runtime import configure
    configure()
else:
    os.environ['NUMBA_CACHE_DIR']=str(ROOT/sys.argv[1])
import librosa
import numpy as np
from concurrent.futures import ThreadPoolExecutor

def check():
    audio,rate=librosa.load(ROOT/'dataset/asr_checks/1272-128104-0000.wav',sr=16000)
    f0, voiced, probability=librosa.pyin(audio,sr=rate,fmin=65,fmax=600,hop_length=160)
    assert np.isfinite(f0[voiced]).all() and voiced.any()
    output=ROOT/'tmp/pitch-runtime'
    output.mkdir(parents=True,exist_ok=True)
    previous=output/'first.npy'
    if previous.exists():
        np.testing.assert_allclose(np.load(previous),f0,equal_nan=True,rtol=1e-6)
    else: np.save(previous,f0)
    print('pYIN passed:',len(f0),'frames;',int(voiced.sum()),'voiced; cache',os.environ['NUMBA_CACHE_DIR'],flush=True)

with ThreadPoolExecutor(max_workers=1) as pool: pool.submit(check).result()
