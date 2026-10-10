// ─── What gets sent when a plan is submitted ─────────────────────────────────
// Framework-free: used by /api/birth-plan and by the tests.
import { STEPS, buildPlan, planText, otherKey } from './schema.js'

export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const first = a => String(a.name || '').trim().split(/\s+/)[0] || ''
const two = n => String(n).padStart(2, '0')
export const stamp = (d = new Date(), tz = 'Asia/Jerusalem') => {
  const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: tz, day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
    .formatToParts(d).map(x => [x.type, x.value]))
  return { date: `${p.day}/${p.month}/${p.year}`, time: `${p.hour}:${two(p.minute)}` }
}

// Israeli mobile/landline → 9725XXXXXXXX (digits only), or ''
export function intlPhone(raw) {
  const d = String(raw || '').replace(/\D/g, '')
  if (d.startsWith('972')) return d
  if (d.startsWith('0')) return '972' + d.slice(1)
  return d.length >= 11 ? d : ''
}

const FACT_LABELS = ['טלפון', 'מספר לידה', 'תאריך לידה משוער', 'בית חולים', 'מלווים']

// ── e-mail ───────────────────────────────────────────────────────────────────
const F = 'font-family:Heebo,Arial,Helvetica,sans-serif'
export function emailSubject(a) { return `תכנית לידה חדשה: ${String(a.name || '').trim()}` }

export function emailHtml(a, { when = stamp(), hasPdf = false } = {}) {
  const plan = buildPlan(a)
  const about = plan.find(s => s.id === 'about')?.items || []
  const facts = about.filter(it => FACT_LABELS.includes(it.label))
  const notes = about.filter(it => !FACT_LABELS.includes(it.label) && it.label !== 'שם')
  const phone = String(a.phone || '').replace(/\D/g, '')

  const factRows = []
  for (let i = 0; i < facts.length; i += 2) {
    const cell = it => it ? `<td width="50%" valign="top" style="padding:8px 0 8px 12px">
        <div style="${F};font-size:12px;font-weight:600;color:#75727C">${esc(it.label)}</div>
        <div style="${F};font-size:16px;font-weight:500;color:#26242B;margin-top:2px">${it.label === 'טלפון' ? `<a href="tel:${esc(phone)}" style="color:#3F4EB0;text-decoration:none">${esc(it.value)}</a>` : esc(it.value)}</div></td>` : '<td width="50%"></td>'
    factRows.push(`<tr>${cell(facts[i])}${cell(facts[i + 1])}</tr>`)
  }

  const item = it => `
      <tr><td style="padding:6px 0">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F6F9;border-radius:10px"><tr><td style="padding:12px 16px">
          <div style="${F};font-size:13px;font-weight:700;color:#4A4852;margin-bottom:6px">${esc(it.label)}</div>
          ${Array.isArray(it.value)
            ? it.value.map(x => `<table role="presentation" cellpadding="0" cellspacing="0" style="margin:3px 0"><tr>
                <td valign="top" style="${F};font-size:15px;color:#1F9D55;font-weight:800;padding-left:8px;line-height:1.6">✓</td>
                <td style="${F};font-size:15px;line-height:1.6;color:#26242B">${esc(x)}</td></tr></table>`).join('')
            : `<div style="${F};font-size:15px;line-height:1.7;color:#26242B;white-space:pre-wrap">${esc(it.value)}</div>`}
        </td></tr></table>
      </td></tr>`
  const section = (title, items) => !items.length ? '' : `
      <tr><td style="padding:26px 0 6px;${F};font-size:19px;font-weight:800;color:#3F4EB0;border-bottom:2px solid #DFE3F6">${esc(title)}</td></tr>
      <tr><td style="height:6px"></td></tr>
      ${items.map(item).join('')}`

  const body = [
    section('מה חשוב לה שתדעו', notes),
    ...plan.filter(s => s.id !== 'about').map(s => section(s.title, s.items)),
  ].join('')

  return `<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#EFEFF1">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#EFEFF1"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" dir="rtl" style="max-width:640px;width:100%;background:#FFFFFF;border-radius:16px;overflow:hidden">
  <tr><td style="background:#3F4EB0;padding:26px 28px 24px">
    <div style="${F};font-size:13px;font-weight:700;color:#DFE3F6;letter-spacing:.3px">תכנית לידה חדשה התקבלה</div>
    <div style="${F};font-size:28px;font-weight:800;color:#FFFFFF;margin-top:6px">${esc(String(a.name || '').trim())}</div>
    <div style="${F};font-size:13px;color:#DFE3F6;margin-top:6px">מולא בתאריך ${esc(when.date)} בשעה ${esc(when.time)}</div>
  </td></tr>
  <tr><td style="padding:18px 28px 4px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">${factRows.join('')}</table>
  </td></tr>
  <tr><td style="padding:0 28px 8px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">${body}</table>
  </td></tr>
  <tr><td style="padding:22px 28px 26px;${F};font-size:13px;line-height:1.6;color:#75727C;border-top:1px solid #EFEFF1">
    ${hasPdf ? 'התכנית מצורפת גם כקובץ PDF, נוח להדפסה ולשליחה לבית החולים.<br>' : ''}נשלח אוטומטית משאלון תכנית הלידה של הדס.
  </td></tr>
</table></td></tr></table></body></html>`
}

export const emailText = a => planText(a, { bold: false })

// ── WhatsApp ─────────────────────────────────────────────────────────────────
const SHORT = {
  d_pain: { natural: 'רוצה לנסות בלי שיכוך תרופתי', noOffer: 'לא להציע לה תרופות, היא תבקש אם תרצה', wantMeds: 'מעוניינת בשיכוך כאבים תרופתי' },
  n_care: { bfOnly: 'הנקה בלבד', selfFeed: 'לא מניקה, מאכילה בעצמה', noPacifier: 'בלי מוצץ' },
  d_episio: { inform: 'ליידע אותה מראש', noInform: 'לא ליידע אותה' },
}
const label = (id, v) => STEPS.find(s => s.id === id)?.opts?.find(o => o.v === v)?.l || ''

export function teamWhatsApp(a, { when = stamp(), hasPdf = false } = {}) {
  const L = [`*תכנית לידה חדשה התקבלה* 🤍`, '', `*${String(a.name || '').trim()}*`]
  const add = (k, v) => { v = String(v || '').trim(); if (v) L.push(`${k}: ${v}`) }
  add('טלפון', a.phone)
  add('לידה', label('birthNo', a.birthNo))
  if (a.dueDate) { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(a.dueDate); add('תאריך משוער', m ? `${m[3]}/${m[2]}/${m[1]}` : a.dueDate) }
  add('בית חולים', a.hospital)
  add('מלווים', a.companions)

  const hi = []
  const pain = (a.d_pain || []).map(v => SHORT.d_pain[v]).filter(Boolean)
  if (pain.length) hi.push(`כאב: ${pain.join(' · ')}`)
  const feed = (a.n_care || []).map(v => SHORT.n_care[v]).filter(Boolean)
  if (feed.length) hi.push(`האכלה: ${feed.join(' · ')}`)
  if (a.d_cord && a.d_cord !== 'none') hi.push(`חבל הטבור: ${a.d_cord === 'other' ? (String(a[otherKey('d_cord')] || '').trim() || 'מישהו אחר') : label('d_cord', a.d_cord)}`)
  if (SHORT.d_episio[a.d_episio]) hi.push(`חתך חיץ: ${SHORT.d_episio[a.d_episio]}`)
  if (a.p_rooming && a.p_rooming !== 'none') hi.push(`ביות: ${label('p_rooming', a.p_rooming)}`)
  if (String(a.special || '').trim()) hi.push('יש פרטים מיוחדים לצוות, כדאי לקרוא')
  if (hi.length) L.push('', '*בקצרה*', ...hi.map(x => `• ${x}`))

  L.push('', hasPdf ? 'התכנית המלאה מצורפת כקובץ PDF ונשלחה גם למייל.' : 'התכנית המלאה נשלחה למייל.', `התקבל בתאריך ${when.date} בשעה ${when.time}`)
  return L.join('\n')
}

export function motherWhatsApp(a, { doula = 'הדס' } = {}) {
  const n = first(a)
  return [
    `היי${n ? ` ${n}` : ''}, תודה שמילאת את תכנית הלידה 🤍`,
    `${doula} קיבלה אותה ותחזור אלייך.`,
    '',
    'מצורף עותק בשבילך. כדאי לשמור אותו בטלפון ולהביא איתך ללידה.',
  ].join('\n')
}
