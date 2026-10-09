"""Hebrew TTS via MBROLA from hand-written modern-Israeli phonetic transcription.

Word notation: phonemes a e i o u ^(glottal) b v g d h z x(ח/כ) t j k l m n s p f Ts r S(ש);
stressed vowel UPPERCASE. A word with no uppercase vowel is an unaccented clitic.
Phrase punctuation . , ? ends a phrase.
"""
import subprocess, re, random

VOW = set('aeiou')
FRIC = {'s', 'S', 'x', 'f', 'Ts', 'z', 'v'}
STOP = {'p', 't', 'k', 'b', 'd', 'g'}
SON = {'l', 'm', 'n', 'r', 'j'}

VOICES = {
    'hb1': dict(db='/usr/share/mbrola/hb1/hb1', base=104, map={}),
    'hb2': dict(db='/usr/share/mbrola/hb2/hb2', base=196, map={'r': 'R', 'x': 'X', '^': '?'}),
}


def tokenize(word):
    out, i = [], 0
    while i < len(word):
        if word[i:i + 2] == 'Ts':
            out.append(['Ts', False]); i += 2; continue
        c = word[i]
        if c == '_':
            out.append(['_', False]); i += 1; continue
        if c == 'ə':
            out.append(['e', 'schwa']); i += 1; continue
        out.append([c.lower(), True] if c in 'AEIOU' else [c, False])
        i += 1
    return out


def fix_for_voice(toks, voice, nxt_first):
    """Make the phone sequence pronounceable with the voice's diphone set."""
    if voice != 'hb2':
        return toks
    out = []
    for k, (p, st) in enumerate(toks):
        nxt = toks[k + 1][0] if k + 1 < len(toks) else nxt_first
        prev = out[-1][0] if out else None
        if p == 'j' and prev in VOW and (nxt is None or nxt not in VOW):
            out[-1] = [prev + 'i', out[-1][1]]  # diphthong ai/ei/oi/ui
            continue
        if p == 'j' and (prev is None or prev not in VOW) and nxt is not None and nxt not in VOW:
            out.append(['i', False]); continue  # word-initial y + consonant -> short i
        if p == '^' and (nxt is None or nxt not in VOW):
            continue
        if p in VOW and prev is not None and prev[0] in VOW:
            out.append(['^', False])  # hiatus -> light glottal
        out.append([p, st])
    return out


def phrases_of(text):
    res = []
    for m in re.finditer(r'([^.,?]+)([.,?])', text):
        ws = m.group(1).split()
        if ws:
            res.append((ws, m.group(2)))
    return res


CFG=dict(stop=62,fric=78,son=54,nas=54,vow=72,svow=108,fall=0.80,endp=200)
def build(text, voice='hb2', rate=1.0, base=None, seed=3):
    rnd = random.Random(seed)
    V = VOICES[voice]; base = base or V['base']; mp = V['map']
    lines = ['_ 150']; t = 150; timings = []
    phrases = phrases_of(text)
    for pi, (words, end) in enumerate(phrases):
        n = len(words)
        # index of last accented word
        acc_idx = [i for i, w in enumerate(words) if re.search('[AEIOU]', w)]
        last_acc = acc_idx[-1] if acc_idx else n - 1
        for wi, w in enumerate(words):
            toks = tokenize(w)
            nxt_first = tokenize(words[wi + 1])[0][0] if wi + 1 < n else None
            toks = fix_for_voice(toks, voice, nxt_first)
            wstart = t
            prog = wi / max(1, n - 1)
            decl = 1.10 - 0.20 * prog  # declination across phrase
            is_last = wi == last_acc
            accented = bool(re.search('[AEIOU]', w))
            for k, (p, st) in enumerate(toks):
                word_final = k == len(toks) - 1
                if p[0] in VOW:
                    d = CFG['vow']
                    if st: d = CFG['svow']
                    if st and is_last: d = 150 if end != ',' else 130
                    if word_final and not st: d += 12
                    if not accented: d = 62
                    if st == 'schwa': d = CFG.get('schwa', 34)
                    d = int(d / rate)
                    f = base * decl * (1 + rnd.uniform(-0.02, 0.02))
                    sym = p if p in ('ai', 'ei', 'oi', 'ui') or len(p) == 1 else p
                    if st and is_last and end == '.':
                        lines.append(f'{sym} {d} 0 {base*1.06:.0f} 40 {base*0.98:.0f} 100 {base*CFG['fall']:.0f}')
                    elif st and is_last and end == '?':
                        lines.append(f'{sym} {d} 0 {base*0.95:.0f} 60 {base*1.15:.0f} 100 {base*1.42:.0f}')
                    elif st and is_last and end == ',':
                        lines.append(f'{sym} {d} 0 {base*0.98:.0f} 100 {base*1.16:.0f}')
                    elif st and accented:
                        pk = f * 1.20
                        lines.append(f'{sym} {d} 0 {f*1.04:.0f} 45 {pk:.0f} 100 {f*1.02:.0f}')
                    else:
                        lines.append(f'{sym} {d} 50 {f:.0f}')
                else:
                    if p == '_': d = CFG.get('gap', 28)
                    elif p in FRIC: d = CFG['fric']
                    elif p in STOP: d = CFG['stop']
                    elif p in ('m','n'): d = CFG['nas']
                    elif p == '^': d = 30
                    elif p == 'h': d = 46
                    else: d = CFG['son']
                    if k == 0: d += 8
                    d = CFG.get('ph', {}).get(p, d)
                    d = int(d / rate)
                    lines.append(f'{mp.get(p, p)} {d}')
                t += d
            timings.append({'w': w, 'start': wstart / 1000, 'end': t / 1000, 'phrase': pi})
        pause = {'.': 380, ',': 190, '?': 420}[end]
        if pi == len(phrases) - 1:
            pause = CFG['endp']
        lines.append(f'_ {pause}'); t += pause
    return '\n'.join(lines) + '\n', timings, t / 1000


def synth(text, out, voice='hb2', rate=1.0, base=None):
    pho, tim, dur = build(text, voice, rate, base)
    open(out + '.pho', 'w').write(pho)
    r = subprocess.run(['mbrola', '-e', VOICES[voice]['db'], out + '.pho', out], capture_output=True, text=True)
    miss = sorted(set(re.findall(r'Warning: (\S+-\S+) unknown', r.stderr)))
    return tim, dur, miss


ENH = dict(nas=0.5, stop=1.8, fric=1.3)
def enhance(wav, pho):
    """Consonant enhancement using the known phone segmentation."""
    import soundfile as sf, numpy as np
    a, sr = sf.read(wav)
    g = np.ones(len(a)); t = 0
    segs = []
    for line in open(pho):
        f = line.split()
        if not f: continue
        d = int(f[1]) / 1000; segs.append((f[0], t, t + d)); t += d
    for k, (p, s, e) in enumerate(segs):
        i0, i1 = int(s * sr), int(e * sr)
        if p in ('m', 'n'):
            g[i0:i1] = ENH['nas']
        elif p in ('k', 't', 'p', 'b', 'd', 'g'):
            # boost release: last 30% of the stop and first 25 ms of following segment
            r0 = int((s + (e - s) * 0.7) * sr); r1 = min(len(a), i1 + int(0.025 * sr))
            g[r0:r1] = np.maximum(g[r0:r1], ENH['stop'])
        elif p in ('s', 'S', 'X', 'x', 'f', 'Ts', 'z', 'v'):
            g[i0:i1] = np.maximum(g[i0:i1], ENH['fric'])
    k = int(0.006 * sr); ker = np.hanning(2 * k + 1); ker /= ker.sum()
    g = np.convolve(g, ker, mode='same')
    out = a * g; out /= max(1e-9, np.abs(out).max()) / 0.9
    sf.write(wav, out, sr)


_synth_orig = synth
def synth(text, out, voice='hb2', rate=1.0, base=None, enhance_on=True):
    r = _synth_orig(text, out, voice, rate, base)
    if enhance_on: enhance(out, out + '.pho')
    return r
