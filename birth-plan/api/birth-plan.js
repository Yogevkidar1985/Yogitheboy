// ─── POST /api/birth-plan — deliver a finished birth plan ────────────────────
// Body: { answers, pdf?: base64, pdfName?: string, website?: '' (honeypot) }
//
// • E-mail (Gmail SMTP) to PLAN_EMAIL_TO, full plan in the body + PDF attached
// • WhatsApp (Green API) to WA_NOTIFY_PHONES (default Hadas): short summary + the PDF
// • WhatsApp copy to the mother herself (WA_COPY_TO_MOTHER, on by default)
// Every channel is best effort; the response says which ones went out.
import { validateStep, STEPS, planText } from '../src/schema.js'
import { emailHtml, emailText, emailSubject, teamWhatsApp, motherWhatsApp, intlPhone, stamp } from '../src/messages.js'

const DEFAULT_TO = 'Daske2725@gmail.com,kidaryogev@gmail.com'
const DEFAULT_NOTIFY = '972542299787'            // Hadas
const MAX_PDF = 3.5 * 1024 * 1024
const list = v => String(v || '').split(/[,;\s]+/).map(s => s.trim()).filter(Boolean)

// ── e-mail ───────────────────────────────────────────────────────────────────
async function sendEmail(a, pdf, pdfName, when) {
  const user = process.env.GMAIL_USER, pass = process.env.GMAIL_APP_PASSWORD
  const to = list(process.env.PLAN_EMAIL_TO || DEFAULT_TO)
  if (!user || !pass) return { ok: false, error: 'GMAIL_USER / GMAIL_APP_PASSWORD missing' }
  try {
    const { default: nodemailer } = await import('nodemailer')
    const t = nodemailer.createTransport({ host: 'smtp.gmail.com', port: 465, secure: true, auth: { user, pass: pass.replace(/\s+/g, '') } })
    await t.sendMail({
      from: `"תכנית לידה" <${user}>`, to,
      subject: emailSubject(a),
      text: emailText(a),
      html: emailHtml(a, { when, hasPdf: !!pdf }),
      attachments: pdf ? [{ filename: pdfName, content: pdf, contentType: 'application/pdf' }] : [],
    })
    return { ok: true, to: to.length }
  } catch (e) { return { ok: false, error: e.message } }
}

// ── WhatsApp (Green API) ─────────────────────────────────────────────────────
const GI = () => process.env.WA_GREENAPI_INSTANCE || ''
const GT = () => process.env.WA_GREENAPI_TOKEN || ''
const greenUrl = m => { const r = String(GI()).slice(0, 4); return `${r ? `https://${r}.api.greenapi.com` : 'https://api.green-api.com'}/waInstance${GI()}/${m}/${GT()}` }

async function waText(phone, message) {
  const r = await fetch(greenUrl('sendMessage'), { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chatId: `${phone}@c.us`, message }), signal: AbortSignal.timeout(15000) })
  if (!r.ok) throw new Error(`Green API sendMessage HTTP ${r.status}`)
}
async function waFile(phone, pdf, fileName, caption) {
  const fd = new FormData()
  fd.append('chatId', `${phone}@c.us`)
  fd.append('file', new Blob([pdf], { type: 'application/pdf' }), fileName)
  fd.append('fileName', fileName)
  if (caption) fd.append('caption', caption)
  const r = await fetch(greenUrl('sendFileByUpload'), { method: 'POST', body: fd, signal: AbortSignal.timeout(45000) })
  if (!r.ok) throw new Error(`Green API sendFileByUpload HTTP ${r.status}`)
}

async function sendWhatsApp(a, pdf, pdfName, when) {
  if (!GI() || !GT()) return { ok: false, error: 'WA_GREENAPI_INSTANCE / WA_GREENAPI_TOKEN missing' }
  const team = list(process.env.WA_NOTIFY_PHONES || DEFAULT_NOTIFY).map(intlPhone).filter(Boolean)
  const mother = /^(0|false|no)$/i.test(process.env.WA_COPY_TO_MOTHER || '') ? '' : intlPhone(a.phone)
  const out = { team: 0, mother: false, errors: [] }

  await Promise.all(team.map(async p => {
    try {
      await waText(p, teamWhatsApp(a, { when, hasPdf: !!pdf }))
      if (pdf) await waFile(p, pdf, pdfName, '')
      out.team++
    } catch (e) { out.errors.push(e.message) }
  }))
  if (mother && !team.includes(mother)) {
    try {
      if (pdf) await waFile(mother, pdf, pdfName, motherWhatsApp(a))
      else await waText(mother, `${motherWhatsApp(a).split('\n\n')[0]}\n\n${planText(a)}`)
      out.mother = true
    } catch (e) { out.errors.push(e.message) }
  }
  out.ok = out.team > 0 || out.mother
  return out
}

// ── handler ──────────────────────────────────────────────────────────────────
export default async function handler(req, res) {
  res.setHeader('X-Robots-Tag', 'noindex, nofollow')
  if (req.method !== 'POST') return res.status(405).json({ ok: false, error: 'POST only' })

  let body = req.body
  if (typeof body === 'string') { try { body = JSON.parse(body) } catch { body = {} } }
  if (body?.website) return res.status(200).json({ ok: true })            // bot filled the hidden field
  const a = body?.answers
  if (!a || typeof a !== 'object') return res.status(400).json({ ok: false, error: 'missing answers' })
  const bad = STEPS.find(s => validateStep(s, a))
  if (bad) return res.status(400).json({ ok: false, error: `invalid ${bad.id}` })

  let pdf = null
  if (typeof body.pdf === 'string' && body.pdf) {
    const buf = Buffer.from(body.pdf, 'base64')
    if (buf.length <= MAX_PDF && buf.subarray(0, 5).toString() === '%PDF-') pdf = buf
  }
  const pdfName = String(body.pdfName || 'תכנית לידה.pdf').replace(/[\\/:*?"<>|\r\n]/g, '').slice(0, 80) || 'תכנית לידה.pdf'
  const when = stamp()

  const [email, whatsapp] = await Promise.all([sendEmail(a, pdf, pdfName, when), sendWhatsApp(a, pdf, pdfName, when)])
  const ok = email.ok || whatsapp.ok
  if (!email.ok || !whatsapp.ok) console.error('birth-plan delivery', { email: email.error, whatsapp: whatsapp.error || whatsapp.errors })
  return res.status(ok ? 200 : 502).json({ ok, email: email.ok, whatsapp: { team: whatsapp.team || 0, mother: !!whatsapp.mother } })
}
