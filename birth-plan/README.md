# שאלון תכנית לידה

שאלון בסגנון Typeform: שאלה אחת בכל מסך, עברית מימין לשמאל, אפשר לעצור ולהמשיך.
השאלות לקוחות ממסמך "תכנית הלידה" של הדס.

## מה קורה כשיולדת מסיימת

1. נבנה קובץ PDF מסודר של כל התכנית (בדפדפן שלה, בלי שרת נוסף).
2. **מייל** עם כל המלל, מעוצב ומסודר לפי נושאים, נשלח ל `PLAN_EMAIL_TO`
   (ברירת מחדל: Daske2725@gmail.com ו kidaryogev@gmail.com), וה PDF מצורף.
3. **וואטסאפ** לכל המספרים ב `WA_NOTIFY_PHONES`: הודעה קצרה עם הפרטים החשובים, ומיד אחריה קובץ ה PDF.
4. **עותק ליולדת** בוואטסאפ עם ה PDF, כדי שתביא אותו ללידה (אפשר לכבות עם `WA_COPY_TO_MOTHER=0`).
5. במסך הסיום היא יכולה גם להוריד את ה PDF.

אם משהו מהשליחה האוטומטית לא עובר, מסך הסיום מציג לה כפתורים לשליחה ידנית בוואטסאפ ובמייל.

## אתר בלי שרת (GitHub Pages)

גרסה שנפתחת לכל אחד, בלי חשבון, ובסוף מאפשרת לשלוח את ה PDF ישירות בוואטסאפ או במייל דרך מסך השיתוף של הטלפון.
השליחה עצמה ידנית (היולדת בוחרת את הדס ולוחצת שלח), כי אין שרת.

הקבצים נבנים לתיקייה `docs` בשורש הריפו: `npm run build:pages`.
הפעלה חד פעמית: Settings ← Pages ← Deploy from a branch ← הענף של השאלון ← `/docs` ← Save.
הכתובת: https://yogevkidar1985.github.io/Yogitheboy/

## העלאה לאוויר (Vercel), פעם אחת

1. נכנסים ל https://vercel.com/new ומייבאים את הריפו `Yogevkidar1985/Yogitheboy`.
2. ב **Root Directory** בוחרים `birth-plan`. ב **Branch** את הענף של השאלון (או main אחרי מיזוג).
3. ב **Environment Variables** מוסיפים את המשתנים מהטבלה למטה, ולוחצים Deploy.
4. הכתובת שמתקבלת (למשל `birth-plan.vercel.app`) היא הלינק לשליחה ליולדות.

| משתנה | מה לשים |
|---|---|
| `GMAIL_USER` | חשבון ה Gmail ששולח את המיילים |
| `GMAIL_APP_PASSWORD` | סיסמת אפליקציה: https://myaccount.google.com/apppasswords (צריך אימות דו שלבי פעיל) |
| `PLAN_EMAIL_TO` | `Daske2725@gmail.com,kidaryogev@gmail.com` |
| `WA_GREENAPI_INSTANCE` | מספר ה Instance מ https://console.green-api.com |
| `WA_GREENAPI_TOKEN` | ה API Token של אותו Instance |
| `WA_NOTIFY_PHONES` | מי מקבל את הסיכום בוואטסאפ. ברירת מחדל: הדס `972542299787`. אפשר להוסיף מספרים מופרדים בפסיק |
| `WA_COPY_TO_MOTHER` | `1` כדי לשלוח ליולדת עותק, `0` כדי לא |
| `VITE_DOULA_PHONE` | הטלפון של הדס לכפתור הגיבוי (כבר מוגדר: `972542299787`) |

אם יש כבר חשבון Green API (כמו באתר של אפיק הנחל), אפשר להשתמש באותו Instance.

## פיתוח

```bash
cd birth-plan
npm install
npm run dev      # פיתוח
npm test         # בדיקות: ולידציה, תוכן המייל והוואטסאפ, אין מקפים בטקסט
npm run build
```

## קבצים

- `src/schema.js` כל השאלות, הסעיפים, הוולידציה וטקסט התכנית
- `src/BirthPlanForm.jsx` הטופס עצמו
- `src/pdf.js` בניית ה PDF בדפדפן
- `src/messages.js` המייל והודעות הוואטסאפ
- `src/draftStore.js` שמירת טיוטה והמשך מאיפה שעצרו
- `api/birth-plan.js` השליחה: מייל, וואטסאפ לצוות ועותק ליולדת
