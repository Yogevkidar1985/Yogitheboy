"""Timeline for the silent 'gap by the wall' video: word reveal at reading pace."""
import json, re
SCENES = [
 ('hook',   'רצף מקצועי לא מצמיד את האריח האחרון לקיר.', 1.0),
 ('reason', 'הוא משאיר רווח קטן, ויש לזה סיבה.', 0.8),
 ('title',  'הפרט בשלוש שורות:', 1.6),
 ('gap',    'רווח: בין שולי הריצוף לקיר, ובמשטחים רחבים גם מישקים בתוך הרצפה.', 1.2),
 ('move',   'תנועה: חומרים מתרחבים ומתכווצים עם חום ולחות. בלי מקום לזוז, אריחים עלולים להתרומם.', 1.6),
 ('hide',   'הסתרה: הפנל מסתיר את הרווח, ולכן אף אחד לא רואה אותו.', 1.4),
 ('future', 'זו דוגמה למלאכה שכל כולה מחשבה על העתיד. היום זה נראה כמו פספוס, בעוד כמה שנים זה מה שמחזיק את הרצפה שקטה.', 1.4),
 ('smart',  'אנחנו חושבים שהפרטים החכמים ביותר בבית הם אלה שנועדו להיעלם.', 1.6),
 ('cta',    'שמרו, שלחו למי שמרצף עכשיו, וכתבו "מרווח" בתגובות.', 0.0),
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
