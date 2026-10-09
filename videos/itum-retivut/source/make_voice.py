import json, subprocess, tts
from script import SCENES
GAP = 0.25; LEAD = 0.6
out = []; t = LEAD; files = []
for sid, s in SCENES:
    pairs = [tok.split('|') for tok in s.split()]
    heb = [p[0] for p in pairs]; phon = ' '.join(p[1] for p in pairs)
    tim, dur, err = tts.synth(phon, f'v_{sid}.wav', voice='hb1', base=104, rate=1.04)
    assert not err.strip(), err
    assert len(tim) == len(heb), (sid, len(tim), len(heb))
    words = [{"t": heb[i], "s": round(t + w["start"], 3), "e": round(t + w["end"], 3), "p": w["phrase"]} for i, w in enumerate(tim)]
    out.append({"id": sid, "start": round(t, 3), "end": round(t + dur, 3), "words": words})
    files.append((f'v_{sid}.wav', t)); t += dur + GAP
total = t + (4.5)  # hold end card
json.dump({"scenes": out, "total": round(total, 3)}, open('timeline.json', 'w'), ensure_ascii=False, indent=1)
# mix voice track at offsets
inputs = []; filt = []
for i, (f, off) in enumerate(files):
    inputs += ['-i', f]; filt.append(f'[{i}]aresample=44100,adelay={int(off*1000)}|{int(off*1000)}[a{i}]')
filt.append(''.join(f'[a{i}]' for i in range(len(files))) + f'amix=inputs={len(files)}:normalize=0,apad,atrim=0:{total}[o]')
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(filt), '-map', '[o]', '-ac', '1', 'voice_raw.wav'], check=True)
print('total', total)
for s in out: print(s['id'], s['start'], s['end'])
