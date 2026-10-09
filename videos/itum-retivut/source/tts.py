"""Hebrew TTS via MBROLA (hb1/hb2) from hand-written phonetic transcription.
Notation per word: lowercase phonemes, stressed vowel UPPERCASE. ^ glottal, x het, S shin, Ts tsadi.
Returns wav + per-word timings."""
import subprocess, re, json, sys, os

VOW = set('aeiou')
CONS2 = ['Ts', 'dZ']

def tokenize(word):
    out = []; i = 0
    while i < len(word):
        if word[i:i+2] in CONS2:
            out.append((word[i:i+2], False)); i += 2; continue
        c = word[i]
        if c in 'AEIOU':
            out.append((c.lower(), True))
        else:
            out.append((c, False))
        i += 1
    return out

FRIC = set('sSfvzxhTs')

def build_pho(phrases, base=112, rate=1.0, missing=set()):
    """phrases: list of (words[], end) end in '.', ',', '?', '…'"""
    lines = ["_ 120"]; t = 120; timings = []
    for pi, (words, end) in enumerate(phrases):
        nwords = len(words)
        for wi, w in enumerate(words):
            toks = tokenize(w)
            # insert schwa where diphone missing
            fixed = []
            for k, tk in enumerate(toks):
                if fixed and (fixed[-1][0], tk[0]) in missing:
                    fixed.append(('e', 'schwa'))
                fixed.append(tk)
            toks = fixed
            wstart = t
            prog = (wi + 0.5) / nwords  # position in phrase
            last_word = wi == nwords - 1
            for k, (p, st) in enumerate(toks):
                if p in VOW:
                    if st == 'schwa':
                        d = 38; pitch = None
                    else:
                        d = 120 if st else 78
                        if st and last_word: d = 165
                    f0 = base * (1.08 - 0.16 * prog)
                    if st is True:
                        f0 *= 1.17
                    if last_word and end in '.' and st is True:
                        f0 = base * 0.95
                    if last_word and end == '?' and st is True:
                        f0 = base * 1.35
                    if last_word and end == ',' and st is True:
                        f0 = base * 1.12
                    d = int(d / rate)
                    if st == 'schwa':
                        lines.append(f"e {d} 50 {f0:.0f}")
                    elif last_word and end == '.' and st is True:
                        lines.append(f"{p} {d} 0 {base*1.1:.0f} 100 {base*0.82:.0f}")
                    elif last_word and end == '?' and st is True:
                        lines.append(f"{p} {d} 0 {base*1.0:.0f} 100 {base*1.45:.0f}")
                    else:
                        lines.append(f"{p} {d} 50 {f0:.0f}")
                else:
                    d = 82 if p in FRIC else (55 if p == '^' else 66)
                    d = int(d / rate)
                    lines.append(f"{p} {d}")
                t += d
            timings.append({"w": w, "start": wstart / 1000, "end": t / 1000, "phrase": pi})
            if not last_word:
                lines.append("_ 18"); t += 18
        pause = {'.': 430, ',': 210, '?': 470, '…': 650}[end]
        lines.append(f"_ {pause}"); t += pause
    return "\n".join(lines) + "\n", timings, t / 1000

def parse(text):
    phrases = []
    for m in re.finditer(r'([^.,?…]+)([.,?…])', text):
        words = m.group(1).split()
        if words: phrases.append((words, m.group(2)))
    return phrases

def synth(text, out, voice='hb1', base=112, rate=1.0):
    phrases = parse(text)
    db = f"/usr/share/mbrola/{voice}/{voice}"
    missing = set()
    for _ in range(3):
        pho, tim, dur = build_pho(phrases, base, rate, missing)
        open(out + '.pho', 'w').write(pho)
        r = subprocess.run(['mbrola', '-e', db, out + '.pho', out], capture_output=True, text=True)
        new = set(re.findall(r'Warning: (\S+)-(\S+) unknown', r.stderr))
        new = {(a, b) for a, b in new if a != '_' and b != '_'}
        if not new - missing: break
        missing |= new
    return tim, dur, r.stderr

if __name__ == '__main__':
    tim, dur, err = synth(sys.argv[1], sys.argv[2], voice=sys.argv[3] if len(sys.argv) > 3 else 'hb1',
                          base=float(sys.argv[4]) if len(sys.argv) > 4 else 112)
    print(dur, err[-500:])
