"""Align a recorded narration to the script: scene cut at pauses, word times via DTW against MBROLA renders."""
import json, subprocess, numpy as np, librosa, soundfile as sf, tts2
from script import SCENES
LEAD = 0.5; HOLD = 4.2
SR = 16000
y, _ = librosa.load('el.wav', sr=SR)
# speech regions per scene (seconds in the recording), from silencedetect
REG = {'hook': (0.0, 3.17), 'rain': (3.70, 7.27), 'stain': (7.76, 12.61), 'paint': (13.08, 16.24), 'where': (16.86, 18.66),
       'one': (19.31, 21.72), 'two': (22.28, 24.70), 'three': (25.27, 26.72), 'now': (27.40, 32.88), 'article': (33.49, 37.55),
       'save': (38.02, 41.93), 'cta': (42.43, 48.67)}
tts2.CFG.clear(); tts2.CFG.update(dict(stop=96, fric=95, son=70, nas=84, vow=68, svow=104, fall=0.88, endp=60, schwa=34, ph={'k': 118, 'd': 112, 'm': 100, 'x': 110}))
def feats(a):
    m = librosa.feature.mfcc(y=a, sr=SR, n_mfcc=20, hop_length=160, n_fft=512)[1:]
    m = (m - m.mean(1, keepdims=True)) / (m.std(1, keepdims=True) + 1e-6)
    return m
def trim(a, sr, top_db=35):
    _, idx = librosa.effects.trim(a, top_db=top_db); return idx[0] / sr, idx[1] / sr
out = []
for sid, s in SCENES:
    pairs = [t.split('|') for t in s.split()]
    heb = [p[0] for p in pairs]; phon = [p[1] for p in pairs]
    a0, a1 = REG[sid]
    seg = y[int(max(0, a0 - 0.15) * SR): int((a1 + 0.15) * SR)]
    t0, t1 = trim(seg, SR); base = max(0, a0 - 0.15)
    seg = seg[int(t0 * SR): int(t1 * SR)]; segstart = base + t0
    tim, dur, miss = tts2.synth(' '.join(phon), '/tmp/ref.wav', voice='hb1', enhance_on=False)
    r, _ = librosa.load('/tmp/ref.wav', sr=SR)
    rt0, rt1 = trim(r, SR); r = r[int(rt0 * SR): int(rt1 * SR)]
    F1, F2 = feats(r), feats(seg)
    D, wp = librosa.sequence.dtw(X=F1, Y=F2, metric='cosine', step_sizes_sigma=np.array([[1, 1], [0, 1], [1, 0]]), weights_mul=np.array([1, 1, 1]))
    wp = wp[::-1]; fr = 160 / SR
    def mapt(tref):
        i = int(round((tref - rt0) / fr)); i = min(max(i, 0), F1.shape[1] - 1)
        js = wp[wp[:, 0] == i][:, 1]
        return segstart + (js.mean() if len(js) else 0) * fr
    words = []
    for i, w in enumerate(tim):
        words.append({'t': heb[i], 's': round(mapt(w['start']) + LEAD, 3), 'e': round(mapt(w['end']) + LEAD, 3), 'p': w['phrase']})
    words[0]['s'] = round(segstart + LEAD, 3); words[-1]['e'] = round(segstart + len(seg) / SR + LEAD, 3)
    for i in range(1, len(words)):  # monotonic
        words[i]['s'] = max(words[i]['s'], words[i - 1]['s'] + 0.05)
        words[i - 1]['e'] = max(words[i - 1]['e'], words[i - 1]['s'] + 0.08)
    out.append({'id': sid, 'start': words[0]['s'], 'end': words[-1]['e'], 'words': words})
    print(sid, round(segstart, 2), ' '.join(f"{w['t']}@{w['s']-LEAD:.2f}" for w in words))
total = round(len(y) / SR + LEAD + HOLD, 3)
json.dump({'scenes': out, 'total': total}, open('timeline.json', 'w'), ensure_ascii=False, indent=1)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'el.wav', '-af', f'adelay={int(LEAD*1000)},apad,atrim=0:{total}', '-ar', '44100', '-ac', '1', 'voice_raw.wav'], check=True)
print('total', total)
