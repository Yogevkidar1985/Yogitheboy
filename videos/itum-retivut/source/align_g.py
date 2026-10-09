"""Google TTS narration per scene + word alignment (DTW vs MBROLA render with known word times)."""
import json, subprocess, sys, numpy as np, librosa, soundfile as sf, tts2, gtts
from script import SCENES
VOICE = sys.argv[1] if len(sys.argv) > 1 else 'he-IL-Chirp3-HD-Iapetus'
RATE = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
LEAD = 0.5; HOLD = 4.2; SR = 24000
GAP = {'one': 0.35, 'two': 0.35, 'three': 0.35}
tts2.CFG.clear(); tts2.CFG.update(dict(stop=96, fric=95, son=70, nas=84, vow=68, svow=104, fall=0.88, endp=60, schwa=34, ph={'k': 118, 'd': 112, 'm': 100, 'x': 110}))
def feats(a, sr):
    m = librosa.feature.mfcc(y=a, sr=sr, n_mfcc=20, hop_length=sr // 100, n_fft=1024)[1:]
    return (m - m.mean(1, keepdims=True)) / (m.std(1, keepdims=True) + 1e-6)
def trim(a, sr):
    _, idx = librosa.effects.trim(a, top_db=38); return idx
track = []; t = LEAD; out = []
for sid, s in SCENES:
    pairs = [x.split('|') for x in s.split()]
    heb = [p[0] for p in pairs]; phon = [p[1] for p in pairs]
    text = ' '.join(heb).replace('1.', 'אחת:').replace('2.', 'שתיים:').replace('3.', 'שלוש:')
    gtts.synth(text, f'g_{sid}.wav', VOICE, {'now': 0.9}.get(sid, RATE))
    a, _ = librosa.load(f'g_{sid}.wav', sr=SR)
    i0, i1 = trim(a, SR); a = a[max(0, i0 - 240): i1 + 1200]; lead_in = (i0 - max(0, i0 - 240)) / SR
    tim, dur, miss = tts2.synth(' '.join(phon), '/tmp/ref.wav', voice='hb1', enhance_on=False)
    r, _ = librosa.load('/tmp/ref.wav', sr=SR); j0, j1 = trim(r, SR); rt0 = j0 / SR
    F1, F2 = feats(r[j0:j1], SR), feats(a, SR)
    D, wp = librosa.sequence.dtw(X=F1, Y=F2, metric='cosine'); wp = wp[::-1]; fr = 0.01
    def mapt(tr):
        i = min(max(int(round((tr - rt0) / fr)), 0), F1.shape[1] - 1)
        js = wp[wp[:, 0] == i][:, 1]; return (js.mean() if len(js) else 0) * fr
    words = [{'t': heb[i], 's': round(t + mapt(w['start']), 3), 'e': round(t + mapt(w['end']), 3), 'p': w['phrase']} for i, w in enumerate(tim)]
    # snap each phrase start to the real speech onset after a pause
    iv = librosa.effects.split(a, top_db=32, frame_length=1024, hop_length=240)
    chunks = [iv[0][0] / SR]
    for k in range(1, len(iv)):
        if (iv[k][0] - iv[k - 1][1]) / SR >= 0.15: chunks.append(iv[k][0] / SR)
    for i in range(1, len(words)):
        if words[i]['p'] != words[i - 1]['p']:
            rel = words[i]['s'] - t
            cand = [c for c in chunks if abs(c - rel) < 0.8 and c > words[i - 1]['s'] - t]
            if cand:
                c = min(cand, key=lambda c: abs(c - rel)); words[i]['s'] = round(t + c, 3)
                words[i - 1]['e'] = min(words[i - 1]['e'], words[i]['s'])
                # keep following words of this phrase after the snapped start
                for j in range(i + 1, len(words)):
                    if words[j]['p'] != words[i]['p']: break
                    words[j]['s'] = max(words[j]['s'], words[i]['s'] + 0.12 * (j - i))
    words[0]['s'] = round(t + lead_in, 3); words[-1]['e'] = round(t + len(a) / SR - 0.05, 3)
    for i in range(1, len(words)):
        words[i]['s'] = max(words[i]['s'], words[i - 1]['s'] + 0.05); words[i - 1]['e'] = max(words[i - 1]['e'], words[i - 1]['s'] + 0.08)
    out.append({'id': sid, 'start': words[0]['s'], 'end': words[-1]['e'], 'words': words})
    track.append((a, t)); print(sid, ' '.join(f"{w['t']}@{w['s']:.2f}" for w in words))
    t += len(a) / SR + GAP.get(sid, 0.45)
total = round(t + HOLD, 3)
y = np.zeros(int(total * SR))
for a, st in track:
    i = int(st * SR); y[i:i + len(a)] += a
sf.write('voice24.wav', y, SR)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'voice24.wav', '-ar', '44100', '-ac', '1', 'voice_raw.wav'], check=True)
json.dump({'scenes': out, 'total': total}, open('timeline.json', 'w'), ensure_ascii=False, indent=1)
print('total', total)
