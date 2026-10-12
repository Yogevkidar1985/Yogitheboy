"""Timeline for the silent 'gap by the wall' video: word reveal at reading pace."""
import json, re
SCENES = [
 ('hook',    'ביום המסירה כל בית נראה טוב.', 0.4),
 ('shine',   'צבע טרי, רצפה נקייה, ברזים מבריקים.', 0.5),
 ('test',    'המבחן האמיתי מגיע הרבה אחר כך.', 0.5),
 ('weather', 'בגשם שבא מהצד, ובקיץ שמחמם את הגג.', 0.7),
 ('three',   'שלושה פרטים שאנחנו בודקים כאילו יבדקו אותם שוב בעוד עשר שנים:', 0.7),
 ('d1',      'אף מים: חריץ קטן מתחת לאדן, שמונע מטיפות לזחול חזרה אל הקיר.', 0.9),
 ('d2',      'שיפועים: מרפסת, גג וחצר שמכוונים את המים אל הניקוז, ולא אל הבית.', 0.9),
 ('d3',      'חדירות: כל צינור שעובר דרך גג או קיר חיצוני מקבל פרט איטום משלו.', 0.9),
 ('photo',   'אף אחד מהם לא יופיע בתמונות של המסירה.', 0.5),
 ('winter',  'כולם יופיעו, או לא יופיעו, בחורף העשירי.', 0.9),
 ('belief',  'בית טוב הוא בית ששוכחים שבדקו אותו.', 0.9),
 ('cta',     'שמרו לבדיקה הבאה, שלחו למי שמקבל מפתח, וכתבו "פרטים" בתגובות.', 0.0),
]
WORD = 0.25; PHRASE_PAUSE = 0.2; ENTRY = 0.35; HOLD_END = 4.0
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
