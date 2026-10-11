"""Timeline for the silent 'gap by the wall' video: word reveal at reading pace."""
import json, re
SCENES = [
 ('hook',    'בסוף סיור מסירה יש לכם עשרות תמונות ורשימה.', 1.0),
 ('mess',    'אחרי שבוע כבר לא ברור איזו תמונה שייכת לאיזו שורה.', 1.2),
 ('tools',   'הפתרון עולה כמה שקלים: גליל סרט הדבקה צבעוני וטוש.', 1.3),
 ('s1',      'מדביקים פס קטן ליד כל ליקוי, בלי לגעת בצבע הטרי.', 1.3),
 ('s2',      'כותבים עליו מספר רץ.', 1.4),
 ('s3',      'מצלמים כך שהמספר בתוך התמונה.', 1.5),
 ('s4',      'רושמים בפרוטוקול את אותו מספר, עם החדר והתיאור.', 1.5),
 ('fix',     'הקבלן מגיע לתקן? הוא מוצא את הפס. תוקן? מורידים אותו ומסמנים וי ברשימה.', 1.5),
 ('insight', 'לדעתנו זה ההבדל בין רשימת ליקויים לבין רשימה שבאמת נסגרת.', 1.6),
 ('cta',     'שמרו את השיטה, שלחו למי שמקבל מפתח החודש, וכתבו "סרט" בתגובות ונשלח טבלה עם מספרים מוכנים.', 0.0),
]
WORD = 0.34; PHRASE_PAUSE = 0.45; ENTRY = 0.55; HOLD_END = 6.0
t = 0.3; out = []
for sid, text, hold in SCENES:
    words = text.split(); st = t + ENTRY; ws = []; p = 0
    for w in words:
        d = WORD + 0.025 * max(0, len(w) - 4)
        ws.append({'t': w, 's': round(st, 3), 'e': round(st + d, 3), 'p': p}); st += d
        if re.search(r'[.,:?]$', w): p += 1; st += PHRASE_PAUSE
    end = ws[-1]['e']
    out.append({'id': sid, 'start': ws[0]['s'], 'end': round(end, 3), 'words': ws})
    t = end + PHRASE_PAUSE + hold
total = round(out[-1]['end'] + HOLD_END, 3)
json.dump({'scenes': out, 'total': total}, open('timeline.json', 'w'), ensure_ascii=False, indent=1)
for s in out: print(s['id'], s['start'], s['end'])
print('total', total)
