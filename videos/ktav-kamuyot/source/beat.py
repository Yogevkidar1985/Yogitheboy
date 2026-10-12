"""Upbeat music bed, arranged to the video timeline."""
import json, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt
SR = 44100
tl = json.load(open('timeline.json')); T = tl['total']; N = int(T * SR)
S = {s['id']: s for s in tl['scenes']}
rng = np.random.default_rng(5)
BPM = 124; BEAT = 60 / BPM; BAR = 4 * BEAT
def q(t): return round(t / BEAT) * BEAT
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x)
def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], 'band', fs=SR, output='sos'), x)
def note(m): return 440 * 2 ** ((m - 69) / 12)
def place(buf, x, t, g=1.0):
    i = int(t * SR)
    if i >= len(buf) or i + len(x) <= 0: return
    if i < 0: x = x[-i:]; i = 0
    x = x[:len(buf) - i]; buf[i:i + len(x)] += g * x

# sections
A = q(S['hook']['start'] + 0.2)
B = q(S['rules']['start'] - 0.4)
BRK = q(S['hour']['start'] - 0.4)
FIN = q(S['cta']['start'] - 0.4)
B2 = FIN
OUT = q(S['cta']['end'] + 0.6)
END = T - 0.3

# --- instruments ---
def kick():
    L = int(0.35 * SR); t = np.arange(L) / SR
    f = 48 + 110 * np.exp(-t * 32); ph = 2 * np.pi * np.cumsum(f) / SR
    k = np.sin(ph) * np.exp(-t * 9) + 0.25 * np.exp(-t * 300) * rng.standard_normal(L)
    return np.tanh(1.6 * k) * 0.9
def clap():
    L = int(0.25 * SR); t = np.arange(L) / SR; n = rng.standard_normal(L)
    env = np.exp(-t * 22) + 0.6 * np.exp(-np.abs(t - 0.012) * 400) + 0.5 * np.exp(-np.abs(t - 0.024) * 400)
    return bp(n, 900, 6000) * env * 0.55 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.25
def hat(open_=False):
    L = int((0.22 if open_ else 0.05) * SR); t = np.arange(L) / SR
    return hp(rng.standard_normal(L), 7000) * np.exp(-t * (14 if open_ else 80)) * 0.22
def crash():
    L = int(2.2 * SR); t = np.arange(L) / SR
    return hp(rng.standard_normal(L), 4000) * np.exp(-t * 2.2) * 0.25
def saw(f, L, harm=14):
    t = np.arange(L) / SR
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, harm))
def pluck(m, L=0.32, g=0.12):
    n = int(L * SR); t = np.arange(n) / SR
    x = (saw(note(m), n, 8) * 0.5 + np.sin(2 * np.pi * note(m) * t)) * np.exp(-t * 11)
    return lp(x, 3500) * g
def bassnote(m, L):
    n = int(L * SR); t = np.arange(n) / SR
    x = lp(saw(note(m), n, 10), 380) * np.minimum(1, t / 0.008) * np.exp(-t * 3.5)
    return np.tanh(x * 1.3) * 0.32
def pad(ch, L):
    n = int(L * SR); t = np.arange(n) / SR
    x = sum(saw(note(m), n, 6) + saw(note(m) * 1.004 / note(m) * note(m), n, 6) * 0.0 for m in ch)
    x = lp(x, 1400) * np.minimum(1, t / 0.4) * np.minimum(1, (L - t) / 0.3)
    return x * 0.03

PROG = [(57, [57, 60, 64, 69]), (53, [53, 57, 60, 65]), (48, [55, 60, 64, 67]), (55, [55, 59, 62, 67])]  # Am F C G
drums = np.zeros(N); bass = np.zeros(N); synth = np.zeros(N); padb = np.zeros(N)
kick_times = []
nbars = int(T / BAR) + 1
for b in range(nbars):
    t0 = b * BAR; root, ch = PROG[b % 4]
    if t0 > END: break
    padb_seg = pad(ch, BAR + 0.3); place(padb, padb_seg, t0)
    for k in range(16):  # 16th steps
        ts = t0 + k * BEAT / 4
        if ts >= END: break
        sec = 'intro' if ts < A else 'A' if ts < B else 'B' if ts < BRK else 'brk' if ts < B2 else 'B' if ts < FIN else 'fin' if ts < OUT else 'out'
        beat = k % 4 == 0; bi = k // 4
        # kick
        if sec in ('B', 'fin') and beat or sec == 'A' and k in (0, 8, 10):
            place(drums, kick(), ts); kick_times.append(ts)
        # clap
        if sec in ('A', 'B', 'fin') and k in (4, 12):
            place(drums, clap(), ts)
        # hats
        if sec in ('A',) and k % 2 == 0:
            place(drums, hat(), ts, 0.8 if k % 4 else 0.5)
        if sec in ('B', 'fin'):
            place(drums, hat(), ts, [0.5, 0.9, 0.65, 1.0][k % 4] * 0.9)
            if k % 4 == 2: place(drums, hat(True), ts, 0.5)
        if sec == 'intro' and k % 4 == 2:
            place(drums, hat(), ts, 0.5)
        # bass: 8th-note root pattern with octave pops
        if sec in ('A', 'B', 'fin', 'brk') and k % 2 == 0:
            m = root - 12 + (12 if k in (6, 14) and sec != 'brk' else 0)
            if sec == 'brk' and k != 0: pass
            else: place(bass, bassnote(m, BEAT / 2 if sec != 'brk' else BAR), ts)
        # pluck arpeggio on offbeats
        if sec in ('intro', 'B', 'fin', 'brk', 'out') and k % 2 == 1 and not (sec == 'intro' and k % 4 != 3):
            m = ch[(k // 2) % len(ch)] + 12
            place(synth, pluck(m, g=0.10 if sec in ('B', 'fin') else 0.07), ts)
    # snare roll into B2 and FIN
for target in sorted({B2, FIN}):
    for i in range(16):
        ts = target - BAR + i * BAR / 16
        place(drums, clap(), ts, 0.15 + 0.6 * i / 16)
for c in sorted({A, B, B2, FIN}):
    place(drums, crash(), c, 0.9)
# riser into groove A and finale
for target, L in ((A, 2.0), (FIN, 2.5)):
    n = int(L * SR); t = np.arange(n) / SR
    r = hp(rng.standard_normal(n), 1500) * (t / L) ** 2 * 0.12
    place(drums, r, target - L)
# final chord ring
place(synth, sum(pluck(m, 2.5, 0.12) for m in (69, 72, 76)), OUT)
place(bass, bassnote(45, 2.5), OUT)

# sidechain pump on bass/pad/synth from kicks
pump = np.ones(N)
for kt in kick_times:
    i = int(kt * SR); L = int(0.22 * SR)
    seg = 1 - 0.55 * np.exp(-np.arange(L) / SR * 14)
    pump[i:i + L] = np.minimum(pump[i:i + L], seg[:max(0, min(L, N - i))])
mix = drums * 0.9 + (bass * 1.0 + padb + synth) * pump
# intro filter sweep (dark -> open)
fade = np.ones(N); fi = int(0.8 * SR); fade[:fi] = np.linspace(0, 1, fi)
fo = int(1.5 * SR); fade[-fo:] = np.linspace(1, 0, fo); mix *= fade
mix = np.tanh(mix * 1.2) / 1.2
wavfile.write('music.wav', SR, (np.clip(mix / np.abs(mix).max() * 0.85, -1, 1) * 32767).astype(np.int16))
print('sections', dict(A=round(A, 2), B=round(B, 2), BRK=round(BRK, 2), B2=round(B2, 2), FIN=round(FIN, 2), OUT=round(OUT, 2)))
