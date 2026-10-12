"""Timeline for the silent 'gap by the wall' video: word reveal at reading pace."""
import json, re
SCENES = [
 ('hook',  'הפער בין ההצעה לחשבון הסופי לא נולד באתר.', 0.6),
 ('where', 'הוא נולד בכתב הכמויות, בשורות שאף אחד לא קרא עד הסוף.', 0.7),
 ('rules', '3 כללי אצבע לכל כתב כמויות:', 0.8),
 ('r1',    'כל סעיף עם כמות ויחידת מידה ברורה.', 0.9),
 ('r2',    'בלי פאושל על דבר שאפשר למדוד.', 0.9),
 ('r3',    'כל מה שלא כלול, כתוב במפורש.', 0.9),
 ('pen',   'סעיף שלא עובר? שואלים עכשיו, ומתקנים בעט ולא בצ׳ק.', 0.9),
 ('hour',  'זו השעה הכי משתלמת בכל תהליך הבנייה.', 0.9),
 ('cta',   'שמרו לפגישה לפני החתימה, וכתבו "כמויות" בתגובות לכתבה על חריגות תקציב.', 0.0),
]
WORD = 0.27; PHRASE_PAUSE = 0.24; ENTRY = 0.35; HOLD_END = 4.0
t = 0.3; out = []
for sid, text, hold in SCENES:
    words = text.split(); st = t + ENTRY; ws = []; p = 0
    for w in words:
        d = WORD + 0.02 * max(0, len(w) - 4)
        ws.append({'t': w, 's': round(st, 3), 'e': round(st + d, 3), 'p': p}); st += d
        if re.search(r'[.,:?]$', w): p += 1; st += PHRASE_PAUSE
    end = ws[-1]['e']
    out.append({'id': sid, 'start': ws[0]['s'], 'end': round(end, 3), 'words': ws})
    t = end + PHRASE_PAUSE + hold + 0.25
total = round(out[-1]['end'] + HOLD_END, 3)
json.dump({'scenes': out, 'total': total}, open('timeline.json', 'w'), ensure_ascii=False, indent=1)
for s in out: print(s['id'], s['start'], s['end'])
print('total', total)
