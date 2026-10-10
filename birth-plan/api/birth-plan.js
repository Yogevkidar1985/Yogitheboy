// ─── POST /api/birth-plan — e-mail a finished birth plan ─────────────────────
// Body: { answers }. Sends the formatted plan to PLAN_EMAIL_TO (default Yogev)
// through Gmail SMTP (GMAIL_USER + GMAIL_APP_PASSWORD).
import { buildPlan, planText, validateStep, STEPS } from '../src/schema.js'

const DEFAULT_TO = 'kidaryogev@gmail.com'

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

export function buildEmailHtml(a) {
  const sections = buildPlan(a).map(sec => `
    <tr><td style="padding:22px 28px 6px;font:700 17px Heebo,Arial,sans-serif;color:#3F4EB0">${esc(sec.title)}</td></tr>
    ${sec.items.map(it => `
    <tr><td style="padding:6px 28px;font:400 15px/1.6 Heebo,Arial,sans-serif;color:#26242B">
      <div style="font-weight:600;color:#4A4852">${esc(it.label)}</div>
      ${Array.isArray(it.value)
        ? `<ul style="margin:4px 0 0;padding:0 18px 0 0">${it.value.map(x => `<li style="margin:3px 0">${esc(x)}</li>`).join('')}</ul>`
        : `<div style="white-space:pre-wrap">${esc(it.value)}</div>`}
    </td></tr>`).join('')}`).join('')
  return `<!doctype html><html lang="he" dir="rtl"><body style="margin:0;background:#EFEFF1">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#EFEFF1;padding:24px 0"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" dir="rtl" style="max-width:600px;width:100%;background:#fff;border-radius:16px;overflow:hidden">
  <tr><td style="background:#3F4EB0;padding:24px 28px;font:700 22px Heebo,Arial,sans-serif;color:#fff">תכנית לידה — ${esc(a.name)}</td></tr>
  ${sections}
  <tr><td style="padding:24px 28px;font:400 13px Heebo,Arial,sans-serif;color:#75727C">נשלח מטופס תכנית הלידה</td></tr>
</table></td></tr></table></body></html>`
}

export default async function handler(req, res) {
  res.setHeader('X-Robots-Tag', 'noindex, nofollow')
  if (req.method !== 'POST') return res.status(405).json({ ok: false, error: 'POST only' })

  let body = req.body
  if (typeof body === 'string') { try { body = JSON.parse(body) } catch { body = {} } }
  const a = body?.answers
  if (!a || typeof a !== 'object') return res.status(400).json({ ok: false, error: 'missing answers' })
  const bad = STEPS.find(s => validateStep(s, a))
  if (bad) return res.status(400).json({ ok: false, error: `invalid ${bad.id}` })

  const user = process.env.GMAIL_USER, pass = process.env.GMAIL_APP_PASSWORD
  const to = process.env.PLAN_EMAIL_TO || DEFAULT_TO
  if (!user || !pass) return res.status(500).json({ ok: false, error: 'GMAIL_USER / GMAIL_APP_PASSWORD missing' })

  try {
    const { default: nodemailer } = await import('nodemailer')
    const transporter = nodemailer.createTransport({ host: 'smtp.gmail.com', port: 465, secure: true, auth: { user, pass: pass.replace(/\s+/g, '') } })
    await transporter.sendMail({
      from: `"תכנית לידה" <${user}>`, to,
      subject: `🤍 תכנית לידה חדשה: ${String(a.name).trim()}`,
      text: planText(a, { bold: false }),
      html: buildEmailHtml(a),
    })
    return res.status(200).json({ ok: true })
  } catch (e) {
    return res.status(502).json({ ok: false, error: e.message })
  }
}
