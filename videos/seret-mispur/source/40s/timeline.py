"""Timeline for the silent 'gap by the wall' video: word reveal at reading pace."""
import json, re
SCENES = [
 ('hook',    'סוף סיור מסירה: עשרות תמונות ורשימה.', 0.5),
 ('mess',    'אחרי שבוע? לא ברור מה שייך למה.', 0.6),
 ('tools',   'הפתרון: סרט הדבקה צבעוני וטוש.', 0.7),
 ('s1',      'מדביקים פס ליד כל ליקוי, לא על הצבע הטרי.', 0.7),
 ('s2',      'כותבים מספר רץ.', 0.9),
 ('s3',      'מצלמים עם המספר בתמונה.', 0.9),
 ('s4',      'רושמים בפרוטוקול: מספר, חדר, תיאור.', 0.9),
 ('fix',     'הקבלן מוצא את הפס. תוקן? מורידים ומסמנים וי.', 0.9),
 ('insight', 'ככה רשימת ליקויים באמת נסגרת.', 0.9),
 ('cta',     'שמרו, שלחו למי שמקבל מפתח, וכתבו "סרט" לטבלה מוכנה.', 0.0),
]
WORD = 0.27; PHRASE_PAUSE = 0.24; ENTRY = 0.35; HOLD_END = 4.6
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
