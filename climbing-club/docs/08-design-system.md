# 8. מערכת העיצוב ומפרט מסירה למפתח

הקבצים: `app/static/style.css` (טוקנים ורכיבים), `app/static/app.js` (התנהגויות), `app/templates/_macros.html` (רכיבי Jinja), `app/templates/_icons.html` (אייקונים), `app/templates/base.html` (שלד).

## 1. עקרונות
1. **מובייל תחילה** – ה-CSS הבסיסי הוא לטלפון; `@media (min-width:…)` מרחיב. נקודות שבירה: 600 (טופס 2 עמודות), 640 (רשת כרטיסים), 720 (טבלה במקום כרטיסים, תפריט צף במקום מגירה), 900 (סרגל צד במקום ניווט תחתון), 1000 (2 עמודות).
2. **RTL ברמת המסמך** – `<html dir="rtl">`; כל המיקומים ב-`inset-inline-*`, `margin-inline-*`, `padding-inline-*`. מספרים/מיילים/אסמכתאות ב-`.ltr` (`unicode-bidi:isolate`).
3. **יעד מגע** – כל לחיץ ≥44×44 (`--tap`). שדות `font-size:16px` (מונע זום אוטומטי ב-iOS).
4. **צבע לעולם לא לבד** – סטטוס = צבע + אייקון + טקסט.
5. **תנועה מדודה** – 120/200/320ms, `cubic-bezier(.2,.7,.2,1)`; `prefers-reduced-motion: reduce` מאפס הכול.

## 2. טוקנים (`:root`)
| קבוצה | טוקנים | ערכים |
|---|---|---|
| רקעים | `--c-bg` `--c-surface` `--c-surface-2` | #f5f7fa · #fff · #f8fafc |
| קווים | `--c-line` `--c-line-strong` | #e5e9f0 · #cbd3de |
| טקסט | `--c-text` `--c-text-2` `--c-text-3` | #0f172a · #475569 · #94a3b8 |
| ראשי | `--c-primary` / hover / soft / text | #2457d6 · #1c47b3 · #e8effc · #1a44a8 |
| הצלחה | `--c-success` / soft | #15803d · #e6f6ec |
| אזהרה | `--c-warning` / soft | #b45309 · #fff4e0 |
| שגיאה | `--c-danger` `--c-danger-strong` / soft | #c2410c · #b91c1c · #feeceb |
| מידע | `--c-info` / soft | #0369a1 · #e4f3fb |
| ניטרלי | `--c-neutral` / soft | #64748b · #eef2f6 |
| הועבר | `--c-purple` / soft | #6d28d9 · #efe9fb |
| ניווט | `--c-nav` `--c-nav-text` | #0f172a · #cbd5e1 |
| גופן | `--font` | Heebo → Assistant → Segoe UI → system-ui |
| גדלים | `--fs-xs … --fs-2xl`, `--fs-num` | .8 / .9 / 1 / 1.125 / 1.35 / 1.7 / 1.9rem |
| מרווחים | `--sp-1 … --sp-8` | 4 / 8 / 12 / 16 / 20 / 24 / 32px |
| רדיוס | `--r-sm` `--r-md` `--r-lg` `--r-pill` | 8 / 12 / 16 / 999px |
| צל | `--sh-1` `--sh-2` `--sh-3` | 1px · 4/14px · 16/40px |
| תנועה | `--t-fast` `--t-med` `--t-slow` `--ease` | 120 / 200 / 320ms |
| מובייל | `--safe-b` `--safe-t` `--nav-h` `--appbar-h` | env(safe-area-inset-*) · 60px+safe · 56px |

ניגודיות: כל טקסט על רקע ≥ 4.5:1 (טקסט משני #475569 על לבן = 7.5:1; תגים – טקסט כהה על רקע בהיר).

## 3. מיפוי סטטוסים → צבע/אייקון (עקבי בכל המסכים)
| ערך | תג | אייקון |
|---|---|---|
| מתוכנן `planned` | אפור | calendar |
| התקיים `held`, נכח `present`, פעיל `active`, אושר `approved` | ירוק/כחול | check |
| ממתין להשלמת נוכחות `pending_attendance`, בהפסקה `paused` | כתום | clock |
| בוטל – חג `cancelled_holiday` | כחול-מידע | flag |
| בוטל (מנהלת/אחר), החסיר `absent`, נכשלה `failed` | אדום | x / x-circle |
| הועבר `moved` | סגול | move |
| לא דווח `unreported`, טיוטה `draft` | אפור | info / edit |
| הופקה `issued` | כחול | receipt |
| נשלחה `sent` | ירוק | send |
| סגור `closed` | סגול | lock |

המיפוי מיושם פעם אחת ב-`web.badge_class` (צבע) וב-`_macros.badge` (אייקון).

## 4. רכיבים
| רכיב | מחלקה / מאקרו | הערות התנהגות |
|---|---|---|
| כפתור | `.btn` + `-primary` `-soft` `-ghost` `-danger` `-success` `-sm` `-lg` `-icon` `-block` | `:active` scale .97; `data-loading` → ספינר ונעילה בשליחה; `[disabled]` 50% |
| כפתור צף | `.fab` | מובייל בלבד, מעל הניווט התחתון, צד שמאל (RTL) |
| תג | `m.badge(value, text)` | צבע+אייקון+טקסט |
| צ'יפ סינון | `.chips > .chip.active` | שורה גלילה אופקית ללא פס |
| טאבים | `.tabs > .tab.active` | תצוגות (חודש/שבוע/הקרובים), קבוצות באותו יום |
| כרטיס | `.card`, `.card-link` | לחיץ: hover מרים 1px וצל |
| מדד | `.stat` + `-warn` `-danger` `-ok` | תווית + ערך + שורת הקשר; לחיץ כשיש יעד |
| טבלה | `.table.table-cards` + `td[data-label]` + `.td-title` + `.cell-actions` | <720px: כל שורה כרטיס, תוויות משמאל לערך |
| רשימה | `.list`, `.tasks` | שורות ≥44px |
| מקטע מתקפל | `details.section > summary + .section-body` | חץ מסתובב, ספירה ב-`.count` |
| תפריט פעולות | `details.menu > summary + .menu-body` | ≥720 צף; <720 מגירה תחתונה + רקע; Esc/לחיצה בחוץ סוגרת |
| מגירת "עוד" | `#more-sheet` `.sheet.open` | `visibility` + transform; Esc/רקע סוגר |
| טוסט | `.toast-stack > .toast-{kind}` | תחתית, מעל ניווט; הצלחה/מידע 5s; שגיאה/אזהרה עד סגירה; `aria-live` |
| התראה בתוכן | `m.alert(kind, text)` | `role=alert` לשגיאה |
| מצב ריק | `m.empty(title, text, cta_url, cta_label, icon)` | תמיד עם הסבר ופעולה אפשרית |
| דיאלוג אישור | `<dialog#confirm-dialog>` + `form[data-confirm][data-confirm-title]` | חוסם שליחה עד אישור; fallback ל-`confirm()` |
| בורר נוכחות | `.seg > .seg-opt.seg-green/red/gray` | רדיו נסתר; ≤480px נמתח לרוחב מלא; פוקוס מקלדת |
| שלבים | `.steps > .step.done/.current` | קבלה, העלאת צילום |
| רשימת בדיקה | `.checklist li.ok/.bad/.warn` | סגירת חודש |
| מסמך קבלה | `.receipt-doc` + `[data-zoom]` | הגדלה ×1.35 במובייל |
| פעולות דביקות | `.sticky-actions` | מעל הניווט התחתון; safe-area |
| טופס | `.form`, `.form-grid`, `.form-section`, `.req`, `.hint`, `.field-warn`, `.checks .check` | תוויות מעל השדה; חובה = כוכבית אדומה; אזהרה = מסגרת כתומה |

## 5. אייקונים
SVG sprite אחד (`_icons.html`, ~45 סמלים, stroke 2px, 24 viewBox) – `m.icon('name', 'icon-lg')`. ללא תלות בקבצים חיצוניים.

## 6. טיפוגרפיה
Heebo נטען מ-Google Fonts עם `display=swap`; ללא רשת נופל ל-Assistant/Segoe UI. היררכיה: h1 1.35rem/700 · h2 1.125rem/700 · גוף 1rem · תווית .9rem/600 · עזר .8rem · מספרים 1.9rem/800 `tabular-nums`. שורה 1.55.

## 7. התנהגויות JS (`app.js`, ~4KB, ללא ספריות)
* טוסטים (הצגה/סגירה/יצירה ב-`window.toast(text, kind)`).
* מגירת "עוד", תפריטי פעולות, Esc.
* דיאלוג אישור לטפסים עם `data-confirm`.
* שליחת טופס: מניעת כפילות, ספינר, פס התקדמות עליון, שמירת/שחזור מיקום גלילה בחזרה לאותו עמוד.
* `[data-copy]` העתקה ללוח, `[data-zoom]` הגדלה, `input[type=date][data-hebrew]` תצוגת יום בעברית.

## 8. מצבי מסך חובה – היכן מיושמים
| מצב | מימוש |
|---|---|
| טעינה | ספינר על הכפתור השולח, פס התקדמות בניווט, `aria-busy` |
| ללא נתונים | `m.empty` בכל רשימה, עם פעולה (ילד חדש, יצירת לוח, לתשלומים…) |
| שגיאה | טוסט אדום קבוע + `alert-error` בתוכן (קבלה שנכשלה שומרת נתונים ומציגה "נסי שוב") |
| הצלחה | טוסט ירוק, שלב "done" ב-stepper |
| חסרים פרטים | `row-warn`, `field-warn`, רשימת שדות חסרים בקבלה, כפתור אישור מושבת |
| לא זמין | `fieldset[disabled]` לחודש סגור / חוסר הרשאה + הסבר |
| כפילות אפשרית | `alert-error` עם קישורים לתשלומים הדומים + תיבת "בדקתי" |
| נדרש אישור | דיאלוג אישור; בהפקת קבלה תיבת סימון חובה + אזהרה |

## 9. בדיקת קבלה אוטומטית
`scripts/ui_check.py <base> <user> <pass> [out_dir]` – עובר על 24 מסכים ב-6 רוחבים (320/375/390/430/768/1280), נכשל אם יש גלילה אופקית או אלמנט לחיץ נמוך מ-34px, ושומר צילומי מסך ב-375 ו-1280.
