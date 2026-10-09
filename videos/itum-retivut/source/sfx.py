import json, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt
SR = 44100
tl = json.load(open('timeline.json')); T = tl['total']; N = int(T * SR)
S = {s['id']: s for s in tl['scenes']}
rng = np.random.default_rng(7)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x)
def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], 'band', fs=SR, output='sos'), x)
def place(buf, x, t):
    i = int(t * SR); x = x[:max(0, len(buf) - i)]; buf[i:i + len(x)] += x

# --- music bed: warm pad, Am - F - C - G, 4s per chord, plus soft pluck arpeggio
def note(m): return 440 * 2 ** ((m - 69) / 12)
chords = [[57, 60, 64], [53, 57, 60], [48, 55, 60, 64], [55, 59, 62]]
music = np.zeros(N); t = np.arange(N) / SR
seg = 4.0
for k in range(int(T / seg) + 1):
    ch = chords[k % 4]; a = int(k * seg * SR); b = min(N, int((k + 1) * seg * SR) + SR)
    if a >= N: break
    tt = np.arange(b - a) / SR
    env = np.minimum(1, tt / 0.8) * np.exp(-np.maximum(0, tt - seg + 0.2) * 3)
    pad = sum(np.sin(2 * np.pi * note(m) * tt + 0.3 * np.sin(2 * np.pi * 0.3 * tt)) +
              0.5 * np.sin(2 * np.pi * note(m) * 1.003 * tt) for m in ch)
    pad += 0.8 * np.sin(2 * np.pi * note(ch[0] - 12) * tt)
    music[a:b] += 0.05 * env * pad
    # arpeggio 8ths
    for j in range(8):
        m = ch[j % len(ch)] + 12; st = a + int(j * 0.5 * SR)
        if st >= N: break
        L = int(0.6 * SR); tt2 = np.arange(L) / SR
        pl = np.sin(2 * np.pi * note(m) * tt2) * np.exp(-tt2 * 6) * 0.035
        e = min(N, st + L); music[st:e] += pl[:e - st]
music = lp(music, 3000)
# kick-ish soft pulse from the 'where' scene onward for drive
for bt in np.arange(S['where']['start'] - 0.2, S['cta']['end'], 0.5):
    L = int(0.25 * SR); tt = np.arange(L) / SR
    k = np.sin(2 * np.pi * (55 + 60 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14) * 0.18
    place(music, k, bt)
# fades
fade = np.ones(N); fi = int(1.5 * SR); fade[:fi] = np.linspace(0, 1, fi)
fo = int(2.5 * SR); fade[-fo:] = np.linspace(1, 0, fo)
music *= fade

# --- sfx
sfx = np.zeros(N)
def whoosh(d=0.55, amp=0.22):
    L = int(d * SR); n = rng.standard_normal(L); tt = np.arange(L) / L
    out = np.zeros(L); 
    for i, f in enumerate(np.linspace(400, 3500, 12)):
        s0, s1 = i * L // 12, (i + 1) * L // 12
    env = np.sin(np.pi * tt) ** 2
    y = bp(n, 300, 4000) * env
    y = y * (0.4 + 0.6 * tt)
    return amp * y / np.abs(y).max()
for s in tl['scenes'][1:]:
    place(sfx, whoosh(), s['start'] - 0.35)
# rain: from rain scene start until paint end, swell
r0, r1 = S['rain']['start'] - 0.4, S['paint']['end']
L = int((r1 - r0) * SR); n = rng.standard_normal(L)
rain = bp(n, 800, 9000) * 0.5 + lp(n, 400) * 0.6
drops = np.zeros(L); idx = rng.integers(0, L, int((r1 - r0) * 60)); drops[idx] = rng.uniform(0.3, 1, len(idx))
rain += hp(drops, 2000) * 1.2
tt = np.arange(L) / SR; env = np.minimum(1, tt / 1.2) * np.minimum(1, (L / SR - tt) / 1.5)
env *= np.where(tt > (S['stain']['start'] - r0), 0.45, 1.0)
place(sfx, 0.09 * lp(rain, 5000) * env / np.abs(rain).max() * 0.55, r0)
# thunder at 'now'
L = int(3.0 * SR); n = rng.standard_normal(L); tt = np.arange(L) / SR
th = lp(n, 180, 4) * (np.exp(-tt * 1.4)) * (1 + 0.5 * np.sin(2 * np.pi * 3 * tt))
crack = hp(n, 1500) * np.exp(-tt * 18)
thunder = th / np.abs(th).max() * 0.55 + crack / np.abs(crack).max() * 0.18
place(sfx, thunder, S['now']['start'] - 0.15)
# second distant rumble for "after the storm"
place(sfx, 0.5 * thunder, S['now']['words'][-3]['s'])
# ticks on list numbers
def tick(f=1200, amp=0.25):
    L = int(0.18 * SR); tt = np.arange(L) / SR
    return amp * (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.5 * tt)) * np.exp(-tt * 28)
for sid, f in (('one', 880), ('two', 988), ('three', 1109)):
    place(sfx, tick(f), S[sid]['start'])
# drip sound on stain appearance, return
def drip(amp=0.3):
    L = int(0.25 * SR); tt = np.arange(L) / SR
    fr = 600 + 1400 * (tt / 0.25)
    return amp * np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-tt * 22)
w = S['stain']['words']
place(sfx, drip(), w[0]['s']); place(sfx, drip(0.25), w[5]['s']); place(sfx, drip(0.32), w[-2]['s'])
# roller: one soft swish per painted band (matches the 5 bands in the animation)
p0 = S['paint']['start'] - 0.15; p1 = S['paint']['words'][5]['s'] - 0.05; bd = (p1 - p0) / 5
def roll(d, amp=0.10):
    L = int(d * SR); n = rng.standard_normal(L); tt = np.arange(L) / L
    y = bp(n, 250, 2500) * (np.sin(np.pi * tt) ** 1.5) * (1 + 0.35 * np.sin(2 * np.pi * 14 * tt * d))
    return amp * y / np.abs(y).max()
for k in range(5):
    place(sfx, roll(bd * 0.95), p0 + k * bd)
# paint bubbles: small pops
def pop(amp=0.22):
    L = int(0.07 * SR); tt = np.arange(L) / SR
    return amp * np.sin(2 * np.pi * (900 - 4000 * tt) * tt) * np.exp(-tt * 70)
for i in range(4):
    place(sfx, pop(), S['paint']['words'][6]['s'] + i * 0.12 + 0.12)
# stamp thud
L = int(0.35 * SR); tt = np.arange(L) / SR
place(sfx, 0.5 * np.sin(2 * np.pi * (70 + 80 * np.exp(-tt * 25)) * tt) * np.exp(-tt * 12), S['paint']['words'][7]['s'] + 0.3)
# CTA chime
def chime(amp=0.2):
    L = int(2.0 * SR); tt = np.arange(L) / SR
    return amp * sum(np.sin(2 * np.pi * note(m) * tt) * np.exp(-tt * 2.5) for m in (76, 81, 88)) / 3
place(sfx, chime(), S['cta']['start'] - 0.2)
place(sfx, chime(0.15), S['cta']['words'][4]['s'])

wavfile.write('music.wav', SR, (np.clip(music, -1, 1) * 32767).astype(np.int16))
wavfile.write('sfx.wav', SR, (np.clip(sfx, -1, 1) * 32767).astype(np.int16))
print('ok', T)
