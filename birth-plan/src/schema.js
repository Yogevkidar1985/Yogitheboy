// ─── BIRTH PLAN QUESTIONNAIRE — question schema ──────────────────────────────
// Framework-free (no React) so the same schema powers the public form AND the
// serverless e-mail in /api/birth-plan.
//
// Every step is one screen (Typeform style). Order follows the paper form
// "תכנית הלידה":
//   1 פרטים · 2 חדר לידה · 3 מחלקת ילודים · 4 מחלקת יולדות · 5 סיכום
//
// Step types
//   intro  – section cover screen
//   text   – single-line text        long  – multi-line text
//   phone  – Israeli phone number    date  – date picker
//   choice – pick ONE (letter keys, auto-advance)
//   multi  – pick MANY (checkbox rows)
//   review – summary + submit

const o = (v, l) => ({ v, l })

export const SECTIONS = [
  { id: 'about',    n: 1, title: 'קצת עלייך',        desc: 'כמה פרטים בסיסיים לראש התכנית' },
  { id: 'delivery', n: 2, title: 'חדר לידה',          desc: 'הצוות, הניטור, הכאב, האווירה והרגעים הראשונים עם התינוק' },
  { id: 'newborn',  n: 3, title: 'מחלקת ילודים',      desc: 'הבדיקות, ההאכלה והטיפול בתינוק אחרי הלידה' },
  { id: 'postpart', n: 4, title: 'מחלקת יולדות',      desc: 'הביות והימים הראשונים יחד' },
  { id: 'review',   n: 5, title: 'סיכום ושליחה',      desc: 'בדיקה אחרונה לפני שהתכנית נשלחת' },
]

export const STEPS = [
  // ═══════════════════ 1. ABOUT ═════════════════════════════════════════════
  { id: 'a_intro', section: 'about', type: 'intro' },
  { id: 'name', section: 'about', type: 'text', required: true,
    q: 'נעים מאוד! מה שמך המלא?', ph: 'שם פרטי ושם משפחה', autocomplete: 'name' },
  { id: 'phone', section: 'about', type: 'phone', required: true,
    q: 'מה מספר הטלפון שלך?', help: 'כדי שהדס תוכל לחזור אלייך', ph: '050-000-0000' },
  { id: 'birthNo', section: 'about', type: 'choice', required: true, grid: true,
    q: 'איזו לידה זו בשבילך?', opts: [o('1', 'ראשונה'), o('2', 'שנייה'), o('3', 'שלישית'), o('4', 'רביעית'), o('5', 'חמישית'), o('6+', 'שש ומעלה')] },
  { id: 'dueDate', section: 'about', type: 'date',
    q: 'מה תאריך הלידה המשוער?' },
  { id: 'hospital', section: 'about', type: 'text',
    q: 'באיזה בית חולים את מתכננת ללדת?', ph: 'למשל: מאיר, כפר סבא' },
  { id: 'companions', section: 'about', type: 'text',
    q: 'מי המלווים שתרצי איתך בלידה?', help: 'למשל בן/בת זוג, אמא, הדס הדולה', ph: 'שמות והקשר אלייך' },
  { id: 'special', section: 'about', type: 'long',
    q: 'פרטים מיוחדים שחשוב שצוות חדר הלידה יידע?', help: 'רקע רפואי, לידות קודמות, פחדים, רגישויות — כל מה שחשוב לך שיידעו',
    ph: 'כתבי בחופשיות…' },
  { id: 'wishes', section: 'about', type: 'long',
    q: 'אילו בקשות ורצונות יש לך לגבי הלידה?', help: 'איך היית רוצה שהלידה תיראה ותרגיש',
    ph: 'כתבי בחופשיות…' },

  // ═══════════════════ 2. DELIVERY ROOM ═════════════════════════════════════
  { id: 'd_intro', section: 'delivery', type: 'intro' },
  { id: 'd_staff', section: 'delivery', type: 'multi', title: 'צוות ותקשורת',
    q: 'צוות ותקשורת — מה חשוב לך?',
    opts: [
      o('names',      'חשוב לי שאנשי הצוות יזדהו בשמם ותפקידם.'),
      o('companions', 'אני מעדיפה שהמלווים שלי ישהו עמי בכל שלב, ככל שניתן.'),
      o('midwife',    'חשוב לי לדעת מי המטפל העיקרי שלי (מיילדת) ואשמח במידת האפשר להיבדק על ידה.'),
      o('explain',    'חשוב לי לקבל הסבר לפני כל בדיקה או התערבות רפואית ולהיות מעורבת בקבלת ההחלטות.'),
    ] },
  { id: 'd_monitor', section: 'delivery', type: 'multi', title: 'ניטור ועירוי',
    q: 'ניטור, תנועה ועירוי',
    opts: [
      o('monitor',  'אני מעדיפה ביצוע מוניטור רציף רק במידת הצורך.'),
      o('movement', 'אני מבקשת לאפשר לי שינויי תנוחה ותנועתיות, ככל האפשר, גם בזמן ניטור.'),
      o('iv',       'אני מעדיפה לקבל עירוי רק במידת הצורך. במידה ויש צורך בפתיחת וריד, אעדיף פתיחת וריד ופקיקתו, ללא עירוי פעיל.'),
    ] },
  { id: 'd_pain', section: 'delivery', type: 'multi', title: 'שיכוך כאבים',
    q: 'איך תרצי להתמודד עם הכאב?',
    opts: [
      o('natural',  'אני מעוניינת לנסות ללדת ללא שיכוך כאבים תרופתי או לדחות את מועד קבלתם ככל האפשר — אשמח אם תסייעו בידי באמצעים שונים (כדור פיזיו, שימוש במים, הסבר על שיטות מקלות).'),
      o('noOffer',  'אני מבקשת שלא להציע לי תרופות לשיכוך כאבים. במידה ואהיה מעוניינת, אבקש.'),
      o('wantMeds', 'אני מעוניינת בשיכוך כאבים תרופתי. אנא הסבירו לי על האפשרויות העומדות בפני.'),
    ] },
  { id: 'd_atmos', section: 'delivery', type: 'multi', title: 'אווירה',
    q: 'אווירה בחדר',
    opts: [
      o('lights', 'אני מבקשת לעמעם אורות בחדר, כדי לסייע בידי ביצירת אווירה מרגיעה.'),
      o('music',  'אני מבקשת להשמיע מוסיקה שהבאתי, כדי לסייע בידי ביצירת אווירה מרגיעה.'),
    ] },
  { id: 'd_push', section: 'delivery', type: 'multi', title: 'לחיצה ופרינאום',
    q: 'שלב הלחיצות והפרינאום',
    opts: [
      o('positions', 'אני מבקשת כי תציעו לי תנוחות שונות ללחיצה, כדי שאוכל לבחור בשיתוף עם המיילדת את זו המתאימה לי ומסייעת בידי ללחוץ באופן יעיל.'),
      o('massaged',  'אבקש ליידע כי ביצעתי עיסוי לפרינאום לקראת הלידה.'),
      o('perineum',  'אבקש מהמיילדת לעסות את הפרינאום עם שמן ולהניח רטיות חמות בסמוך לשלב ההכתרה.'),
    ] },
  { id: 'd_episio', section: 'delivery', type: 'choice', title: 'חתך חיץ',
    q: 'במידה ויתעורר צורך בחתך חיץ (אפיזיוטומי)…',
    opts: [
      o('inform',   'אבקש ליידע אותי מראש'),
      o('noInform', 'אבקש לא ליידע אותי'),
      o('none',     'אין לי העדפה'),
    ] },
  { id: 'd_baby', section: 'delivery', type: 'multi', title: 'אחרי הלידה',
    q: 'הרגעים הראשונים עם התינוק',
    opts: [
      o('skin',     'אני מבקשת להשאיר את התינוק על גופי זמן ארוך ככל הניתן.'),
      o('wiped',    'אני מעדיפה כי לפני הנחת התינוק על בטני, הוא ינוגב וינוקה או ייעטף.'),
      o('nurse',    'אני מעוניינת להניק הנקה ראשונה סמוך ללידה, אודה לסיוע.'),
      o('together', 'אני מבקשת לאפשר לנו (הורים ותינוק) זמן היכרות יחד ממושך ככל הניתן, ללא הפרדה.'),
    ] },
  { id: 'd_cord', section: 'delivery', type: 'choice', title: 'חיתוך חבל הטבור',
    q: 'מי יחתוך את חבל הטבור?',
    opts: [
      o('companion', 'המלווה שלי'),
      o('me',        'אני'),
      o('none',      'אין לי העדפה'),
    ] },
  { id: 'd_more', section: 'delivery', type: 'long', title: 'בקשות נוספות',
    q: 'בקשות נוספות לחדר הלידה?', ph: 'כתבי בחופשיות…' },

  // ═══════════════════ 3. NEWBORN ═══════════════════════════════════════════
  { id: 'n_intro', section: 'newborn', type: 'intro' },
  { id: 'n_care', section: 'newborn', type: 'multi', title: 'מחלקת ילודים',
    q: 'הטיפול בתינוק במחלקת ילודים',
    opts: [
      o('explain',   'חשוב לנו לקבל הסבר לפני כל בדיקה או התערבות רפואית לתינוק ולהיות מעורבים בקבלת ההחלטות.'),
      o('bfOnly',    'אני מבקשת להניק בלבד — אנא ציינו זאת על העריסה.'),
      o('noPacifier','אני מבקשת להימנע ממתן מוצץ לתינוק.'),
      o('selfFeed',  'איני מעוניינת בהנקה, אך אשמח להאכיל את תינוקי בעצמי — אנא קראו לי במידת הצורך.'),
      o('vaccines',  'ארצה לקבל הסבר מקיף על מתן התרופות והחיסונים לתינוק, שיינתנו אך ורק לאחר הסכמתי.'),
    ] },

  // ═══════════════════ 4. POSTPARTUM ════════════════════════════════════════
  { id: 'p_intro', section: 'postpart', type: 'intro' },
  { id: 'p_rooming', section: 'postpart', type: 'choice', title: 'ביות',
    q: 'איזה ביות (Rooming-in) מתאים לך?',
    opts: [
      o('partial', 'ביות חלקי'),
      o('full',    'אפס הפרדה — ביות מלא'),
      o('none',    'עוד לא החלטתי'),
    ] },
  { id: 'p_more', section: 'postpart', type: 'long', title: 'הערות נוספות',
    q: 'משהו נוסף שחשוב לך שהדס תדע?', ph: 'כתבי בחופשיות…' },

  // ═══════════════════ 5. REVIEW ════════════════════════════════════════════
  { id: 'review', section: 'review', type: 'review' },
]

export const isEmpty = v => v == null || (typeof v === 'string' && !v.trim()) || (Array.isArray(v) && !v.length)

export const PHONE_RE = /^0(5\d|[2-489]|7\d)-?\d{3}-?\d{4}$/
export function validateStep(step, a) {
  const v = a[step.id]
  if (step.required && isEmpty(v)) return 'שדה חובה'
  if (step.type === 'phone' && !isEmpty(v) && !PHONE_RE.test(String(v).replace(/[\s()]/g, ''))) return 'מספר הטלפון לא נראה תקין'
  return ''
}

// ── human-readable plan ──────────────────────────────────────────────────────
const fmtDate = d => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || '')
  return m ? `${m[3]}/${m[2]}/${m[1]}` : d || ''
}
const optLabel = (step, v) => step.opts?.find(x => x.v === v)?.l || v

function answerText(step, v) {
  if (isEmpty(v)) return ''
  if (step.type === 'date') return fmtDate(v)
  if (step.type === 'choice') return optLabel(step, v)
  if (step.type === 'multi') return v.map(x => optLabel(step, x))
  return String(v).trim()
}

// Sections → [{ title, items: [{ label, value }] }]; value is a string or a list
export function buildPlan(a) {
  const ab = id => answerText(STEPS.find(s => s.id === id), a[id])
  const out = []
  out.push({ id: 'about', title: 'פרטים', items: [
    { label: 'שם', value: ab('name') },
    { label: 'טלפון', value: ab('phone') },
    { label: 'מספר לידה', value: ab('birthNo') },
    { label: 'תאריך לידה משוער', value: ab('dueDate') },
    { label: 'בית חולים', value: ab('hospital') },
    { label: 'מלווים', value: ab('companions') },
    { label: 'פרטים מיוחדים לצוות', value: ab('special') },
    { label: 'בקשות ורצונות', value: ab('wishes') },
  ].filter(x => !isEmpty(x.value)) })

  for (const sec of SECTIONS.filter(s => !['about', 'review'].includes(s.id))) {
    const items = STEPS.filter(s => s.section === sec.id && s.title && !isEmpty(a[s.id]))
      .map(s => ({ label: s.title, value: answerText(s, a[s.id]) }))
    if (!items.length) continue
    out.push({ id: sec.id, title: sec.title, items })
  }
  return out
}

// Plain text (WhatsApp / e-mail text part). WhatsApp renders *bold*.
export function planText(a, { bold = true } = {}) {
  const b = s => (bold ? `*${s}*` : s)
  const lines = [b(`תכנית לידה — ${String(a.name || '').trim()}`), '']
  for (const sec of buildPlan(a)) {
    lines.push(b(`— ${sec.title} —`))
    for (const it of sec.items) {
      if (Array.isArray(it.value)) {
        lines.push(`${it.label}:`)
        it.value.forEach(x => lines.push(`✔ ${x}`))
      } else if (it.value.includes('\n')) {
        lines.push(`${it.label}:`, it.value)
      } else lines.push(`${it.label}: ${it.value}`)
    }
    lines.push('')
  }
  return lines.join('\n').trim()
}
