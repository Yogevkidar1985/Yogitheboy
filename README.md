# MarketWatch — סוכן שמחפש בשבילך במרקטפלייס 24/7

סוכן שרץ ברקע, סורק כל כמה דקות את **יד2** ואת **Facebook Marketplace**, ובודק אם עלה פריט שמתאים למה שאתה מחפש ובטווח המחיר שהגדרת. ברגע שיש התאמה — אתה מקבל הודעה בטלגרם (עם תמונה, מחיר, מיקום ולינק). כל מודעה מקפיצה התראה פעם אחת בלבד, ואם המחיר שלה ירד אחר כך — תקבל התראה על ירידת מחיר.

## איך זה עובד

```
כל X דקות:  yad2 / facebook  ──>  סינון (מחיר, מילים חובה, מילים אסורות)  ──>  "ראינו כבר?" (SQLite)  ──>  טלגרם
```

* `config.yaml` — רשימת החיפושים שלך (מה, עד כמה כסף, אילו מילים חייבות/אסורות להופיע).
* `data/seen.db` — זיכרון של הסוכן: אילו מודעות כבר נראו ובאיזה מחיר, כדי לא לחפור לך.
* התראות — טלגרם (מומלץ) ו/או הדפסה למסך.

## התקנה מהירה (5 דקות)

### 1. בוט טלגרם
1. בטלגרם, פתח שיחה עם **@BotFather**, שלח `/newbot`, ותקבל **טוקן**.
2. שלח הודעה כלשהי לבוט החדש שלך.
3. פתח בדפדפן `https://api.telegram.org/bot<הטוקן>/getUpdates` והעתק את `chat.id`.
4. העתק `.env.example` ל-`.env` והדבק את שני הערכים.

### 2. הגדרת החיפושים
```bash
cp config.example.yaml config.yaml
```
ערוך את `config.yaml`. דוגמה:
```yaml
searches:
  - name: "אייפון 13"
    query: "iphone 13"
    max_price: 1500
    min_price: 300
    must_include: ["13"]
    exclude: ["מסך שבור", "לחלקים", "כיסוי"]
    sources: ["yad2", "facebook"]
```

| שדה | משמעות |
|---|---|
| `query` | מה לחפש באתר (כמו שהיית מקליד בשורת החיפוש) |
| `max_price` / `min_price` | טווח מחיר בש"ח. `min_price` מסנן מודעות "1 ש"ח" |
| `must_include` | כל המילים חייבות להופיע בכותרת/תיאור |
| `any_of` | לפחות אחת מהמילים חייבת להופיע |
| `exclude` | אם אחת מהמילים מופיעה — לדלג |
| `sources` | `yad2`, `facebook` או שניהם |
| `allow_no_price` | האם להתריע גם על מודעות בלי מחיר (ברירת מחדל: לא) |

ההשוואה לא רגישה לאותיות גדולות/קטנות ולאותיות סופיות בעברית (ם/מ וכו').

### 3. הרצה
```bash
pip install -r requirements.txt
python -m marketwatch test-notify   # אמור להגיע "ההתראות עובדות" לטלגרם
python -m marketwatch once          # סבב בדיקה אחד
python -m marketwatch run           # ריצה רציפה 24/7
```

### 4. (אופציונלי) פייסבוק מרקטפלייס
פייסבוק דורש חשבון מחובר. פעם אחת, על מחשב עם מסך:
```bash
playwright install chromium
python -m marketwatch fb-login      # נפתח דפדפן, מתחברים, לוחצים Enter
```
נוצר `fb_state.json` עם הסשן. ב-`config.yaml` שנה את `facebook.city_slug` לעיר שלך (החלק ב-URL של `facebook.com/marketplace/<city>`, למשל `telaviv`, `haifa`, `jerusalem`).

## איך משאירים את זה דלוק 24/7

| אפשרות | מתאים ל | פייסבוק? |
|---|---|---|
| **Docker על מחשב ביתי / Raspberry Pi / VPS** (`docker compose up -d`) | הפתרון המומלץ. `restart: unless-stopped` דואג שיעלה חזרה אחרי ריסטארט | כן |
| **GitHub Actions** (חינם, `.github/workflows/watch.yml`) | אין לך מחשב שדלוק. רץ כל ~10 דקות. הגדר `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` ו-`CONFIG_YAML` ב-Secrets | לא (אין סשן דפדפן, ו-IP של דאטהסנטר נחסם) |
| `python -m marketwatch run` ב-`screen`/`tmux` | הכי פשוט, בלי Docker | כן |

```bash
# Docker
cp .env.example .env && cp config.example.yaml config.yaml   # ואז לערוך
docker compose up -d --build
docker compose logs -f
```

## דברים שכדאי לדעת

* **חסימות.** יד2 ופייסבוק לא אוהבים רובוטים. אל תרד מתחת ל-`interval_seconds: 120`, ואם אתה מקבל 403 שוב ושוב — הגדל את המרווח. פייסבוק: השתמש בחשבון משני; אוטומציה מנוגדת לתנאי השימוש שלהם.
* **האתרים משתנים.** כל הידע על מבנה האתר של יד2 יושב ב-`marketwatch/sources/yad2.py`, ושל פייסבוק ב-`marketwatch/sources/facebook.py`. אם יום אחד הסוכן מחזיר 0 תוצאות, זה המקום לתקן. הרץ עם `-v` כדי לראות למה.
* **הקוד נבדק עם נתוני דמה** (`pytest`), לא מול האתרים החיים, כי הסביבה שבה נכתב חוסמת גישה אליהם. הריצה הראשונה אצלך היא הבדיקה האמיתית — הרץ `python -m marketwatch once -v` ותראה כמה מודעות חזרו מכל חיפוש.

## פיתוח
```bash
pip install -r requirements.txt
pytest
```
להוסיף מקור חדש (למשל eBay או Winwin): לרשת את `Source` ב-`marketwatch/sources/base.py`, להחזיר רשימת `Listing`, ולרשום אותו ב-`build_sources`.
