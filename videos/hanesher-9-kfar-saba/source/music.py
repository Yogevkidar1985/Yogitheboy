import json, subprocess, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt
# shot/page boundaries, mirrored from index.html
D = [2.6,2.0,1.3,2.6,2.0,1.5,2.0,1.5,1.8,1.8,1.5,1.6, 3.4,3.0,3.4,2.6,5.6]
cuts = list(np.cumsum(D)); T = cuts[-1]; starts = [0] + cuts[:-1]
vid_end = starts[12]
tl = {'total': round(T, 3), 'scenes': [
  {'id': 'intro', 'start': 0.0, 'end': 2.6, 'words': [{'s': 0, 'e': 1}]},
  {'id': 'rooms', 'start': 2.6, 'end': vid_end, 'words': [{'s': 2.6, 'e': 3}]},
  {'id': 'cond', 'start': starts[15], 'end': starts[16], 'words': [{'s': starts[15], 'e': starts[15]+1}]},
  {'id': 'cta', 'start': starts[16], 'end': T - 1.5, 'words': [{'s': starts[16], 'e': starts[16] + 1}] * 5}]}
json.dump(tl, open('out/timeline.json', 'w'))
s = open('../svb40/beat.py').read().replace("BPM = 124", "BPM = 122")
a = s.index("A = q(S['hook']['start'] + 0.2)"); b = s.index("END = T - 0.3")
s = s[:a] + """A = q(0.05)
B = q(S['rooms']['start'])
BRK = q(S['cond']['start'])
FIN = q(S['cta']['start'])
B2 = FIN
OUT = q(T - 2.2)
""" + s[b:]
s = s.replace("json.load(open('timeline.json'))", "json.load(open('out/timeline.json'))").replace("wavfile.write('music.wav'", "wavfile.write('out/music.wav'")
exec(compile(s, 'beat', 'exec'), {})
# whooshes on every cut
SR = 44100; N = int(T * SR); sfx = np.zeros(N); rng = np.random.default_rng(3)
def bp(x, a, b): return sosfilt(butter(2, [a, b], 'band', fs=SR, output='sos'), x)
for c in cuts[:-1]:
    L = int(0.32 * SR); tt = np.arange(L) / L; n = bp(rng.standard_normal(L), 600, 7000)
    w = n * np.sin(np.pi * tt) ** 2 * (0.3 + 0.7 * tt); w = 0.16 * w / np.abs(w).max()
    i = int((c - 0.22) * SR); sfx[i:i + L] += w[:max(0, N - i)]
wavfile.write('out/sfx.wav', SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'out/music.wav', '-i', 'out/sfx.wav', '-filter_complex',
  f'[0][1]amix=inputs=2:normalize=0,alimiter=limit=0.89,loudnorm=I=-14:TP=-1.5:LRA=11,apad,atrim=0:{T}', '-ar', '44100', '-ac', '2', 'out/mix.wav'], check=True)
print('total', T)
