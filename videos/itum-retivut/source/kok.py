"""Hebrew narration with Kokoro (neural) from hand-written phonetic transcription -> IPA."""
import re, numpy as np, onnxruntime as ort
from kokoro_onnx.config import get_vocab
VOCAB = get_vocab()
SESS = None; VOICES = None
MAP = {'x': 'χ', 'r': 'ʁ', 'S': 'ʃ', 'g': 'ɡ', '^': ''}
VOW = 'aeiouAEIOU'

def word_ipa(w):
    toks = []; i = 0
    while i < len(w):
        if w[i:i+2] == 'Ts': toks.append('ʦ'); i += 2; continue
        toks.append(w[i]); i += 1
    out = []
    for k, c in enumerate(toks):
        if c in 'AEIOU':
            # put stress mark before the onset consonant (if any)
            if out and out[-1] not in 'aeiou' and out[-1] != '':
                out.insert(len(out) - 1, 'ˈ')
            else:
                out.append('ˈ')
            out.append(c.lower())
        else:
            out.append(MAP.get(c, c))
    return ''.join(out)

def load():
    global SESS, VOICES
    if SESS is None:
        so = ort.SessionOptions(); so.intra_op_num_threads = 8
        SESS = ort.InferenceSession('/tmp/kok/kokoro-v1.0.onnx', so)
        VOICES = np.load('/tmp/kok/voices-v1.0.bin')

def synth(phon_words, voice='em_alex', speed=1.0, style=None):
    """phon_words: list of phonetic words, punctuation attached at end. Returns audio(24k), word spans."""
    load()
    ipa = ''; spans = []
    for k, w in enumerate(phon_words):
        m = re.match(r'(.*?)([.,?]?)$', w); core, p = m.group(1), m.group(2)
        a = len(ipa); ipa += word_ipa(core); b = len(ipa)
        spans.append((a, b)); ipa += p
        if k < len(phon_words) - 1: ipa += ' '
    toks = [VOCAB[c] for c in ipa]
    assert len(toks) == len(ipa), [c for c in ipa if c not in VOCAB]
    st = style if style is not None else VOICES[voice][len(toks) - 1]
    audio, dur = SESS.run(None, {'input_ids': np.array([[0, *toks, 0]], dtype=np.int64), 'style': np.asarray(st, np.float32), 'speed': np.array([speed], np.float32)})
    audio = np.asarray(audio).ravel(); dur = np.asarray(dur).ravel()
    edges = np.concatenate([[0], np.cumsum(dur)]); edges = edges * (len(audio) / edges[-1])
    sr = 24000
    # token i (in ipa) is at index i+1 because of leading pad
    times = [(edges[a + 1] / sr, edges[b + 1] / sr) for a, b in spans]
    return audio, times, ipa
