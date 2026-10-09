import json, subprocess, sys, numpy as np, soundfile as sf
from script import SCENES
ENGINE = sys.argv[1]; VOICE = sys.argv[2]; SPEED = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
GAP = 0.32; LEAD = 0.6; HOLD = 4.5
out = []; t = LEAD; files = []
for sid, s in SCENES:
    pairs = [tok.split('|') for tok in s.split()]
    heb = [p[0] for p in pairs]; phon = [p[1] for p in pairs]
    f = f'v2_{sid}.wav'
    if ENGINE == 'kokoro':
        import kok
        kok.MAP.update({'x': 'x', 'r': 'ɾ'})
        a, times, ipa = kok.synth(phon, VOICE, SPEED)
        # trim leading/trailing near-silence but keep word times consistent
        thr = 0.01 * np.abs(a).max(); nz = np.where(np.abs(a) > thr)[0]
        s0 = max(0, nz[0] - 1200); s1 = min(len(a), nz[-1] + 2400)
        a = a[s0:s1]; off = s0 / 24000; times = [(x - off, y - off) for x, y in times]
        sf.write(f, a, 24000); dur = len(a) / 24000
        words = [{"t": heb[i], "s": round(t + x, 3), "e": round(t + y, 3), "p": 0} for i, (x, y) in enumerate(times)]
        # phrase index from punctuation
        p = 0
        for i, w in enumerate(words):
            w['p'] = p
            if phon[i][-1] in '.,?': p += 1
    else:
        import tts2
        tts2.CFG.clear(); tts2.CFG.update(dict(stop=96, fric=95, son=70, nas=84, vow=68, svow=104, fall=0.88, endp=250, schwa=34, ph={'k': 118, 'd': 112, 'm': 100, 'x': 110}))
        tim, dur, miss = tts2.synth(' '.join(phon), f, voice=VOICE, enhance_on=False)
        assert not miss, miss
        words = [{"t": heb[i], "s": round(t + w["start"], 3), "e": round(t + w["end"], 3), "p": w["phrase"]} for i, w in enumerate(tim)]
    out.append({"id": sid, "start": round(t, 3), "end": round(t + dur, 3), "words": words})
    files.append((f, t)); t += dur + GAP
total = t + HOLD
json.dump({"scenes": out, "total": round(total, 3)}, open('timeline.json', 'w'), ensure_ascii=False, indent=1)
inputs = []; filt = []
for i, (f, off) in enumerate(files):
    inputs += ['-i', f]; filt.append(f'[{i}]aresample=44100,adelay={int(off*1000)}|{int(off*1000)}[a{i}]')
filt.append(''.join(f'[a{i}]' for i in range(len(files))) + f'amix=inputs={len(files)}:normalize=0,apad,atrim=0:{total}[o]')
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(filt), '-map', '[o]', '-ac', '1', 'voice_raw.wav'], check=True)
print('total', round(total, 2))
