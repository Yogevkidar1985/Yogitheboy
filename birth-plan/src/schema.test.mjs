import { test } from 'node:test'
import assert from 'node:assert/strict'
import { STEPS, validateStep, buildPlan, planText } from './schema.js'
import { emailHtml, teamWhatsApp, motherWhatsApp, intlPhone } from './messages.js'
import handler from '../api/birth-plan.js'
import { readFileSync } from 'node:fs'

const A = { name: 'נועה כהן', phone: '050-123-4567', birthNo: '2', dueDate: '2026-12-01', companions: 'בעלי והדס',
  d_pain: ['natural', 'noOffer'], d_episio: 'inform', n_care: ['bfOnly'], p_rooming: 'full', wishes: 'שקט\nואור עמום' }

test('required fields are enforced', () => {
  const bad = STEPS.filter(s => validateStep(s, {})).map(s => s.id)
  assert.deepEqual(bad, ['name', 'phone', 'birthNo'])
  assert.equal(STEPS.filter(s => validateStep(s, A)).length, 0)
  assert.ok(validateStep(STEPS.find(s => s.id === 'phone'), { phone: '123' }))
})

test('plan groups answers by section with full option text', () => {
  const plan = buildPlan(A)
  assert.deepEqual(plan.map(s => s.id), ['about', 'delivery', 'newborn', 'postpart'])
  const pain = plan[1].items.find(i => i.label === 'שיכוך כאבים')
  assert.equal(pain.value.length, 2)
  assert.match(pain.value[0], /כדור פיזיו/)
  assert.equal(plan[0].items.find(i => i.label === 'תאריך לידה משוער').value, '01/12/2026')
  assert.equal(plan[3].items[0].value, 'ביות מלא, בלי הפרדה')
  assert.equal(plan[0].items.find(i => i.label === 'מספר לידה').value, 'שנייה')
})

test('text and e-mail render and escape', () => {
  const t = planText(A)
  assert.match(t, /^\*תכנית הלידה של נועה כהן\*/)
  assert.match(t, /✔ אני מבקשת להניק בלבד/)
  const html = emailHtml({ ...A, name: '<b>x</b>' })
  assert.ok(html.includes('&lt;b&gt;x&lt;/b&gt;') && !html.includes('<b>x</b>'))
})

test('"someone else" cuts the cord: name is carried into the plan', () => {
  const plan = buildPlan({ ...A, d_cord: 'other', d_cord_other: 'אמא שלי' })
  assert.equal(plan[1].items.find(i => i.label === 'חיתוך חבל הטבור').value, 'מישהו אחר: אמא שלי')
})

test('no dashes in anything a mother or the team reads', () => {
  const DASH = /[‒–—―־]|\s-\s/
  const strings = []
  const walk = v => { if (typeof v === 'string') strings.push(v); else if (Array.isArray(v)) v.forEach(walk); else if (v && typeof v === 'object') Object.values(v).forEach(walk) }
  walk(STEPS)
  const full = { ...A, special: 'x', wishes: 'y', d_staff: ['names'], d_monitor: ['iv'], d_atmos: ['music'], d_push: ['positions'], d_baby: ['skin'], d_cord: 'other', d_cord_other: 'אמא', n_care: ['bfOnly', 'selfFeed'], p_more: 'z' }
  strings.push(planText(full), teamWhatsApp(full, { hasPdf: true }), motherWhatsApp(full), emailHtml(full, { hasPdf: true }).replace(/<style[\s\S]*?<\/style>|<[^>]+>/g, ' '))
  // Hebrew lines in the UI source (comments excluded); they also hold code like `idx - 1`, so only real dash characters count there
  const source = []
  for (const f of ['src/BirthPlanForm.jsx', 'src/pdf.js'])
    for (const line of readFileSync(new URL(`../${f}`, import.meta.url), 'utf8').split('\n'))
      if (/[֐-׿]/.test(line) && !/^\s*\/\//.test(line)) source.push(line.replace(/\/\/.*$/, ''))
  const bad = [...strings.filter(x => /[\u0590-\u05FF]/.test(x) && DASH.test(x)), ...source.filter(x => /[\u2012-\u2015\u05BE]/.test(x))]
  assert.deepEqual(bad, [])
})

test('e-mail carries every chosen sentence in full', () => {
  const full = { ...A, d_staff: ['names', 'explain'], d_pain: ['natural'], special: 'בלידה הקודמת עברתי ניתוח קיסרי' }
  const html = emailHtml(full, { hasPdf: true })
  for (const id of ['d_staff', 'd_pain']) for (const v of full[id]) {
    const l = STEPS.find(s => s.id === id).opts.find(o => o.v === v).l
    assert.ok(html.includes(l.replace(/'/g, '&#39;').replace(/"/g, '&quot;')), l)
  }
  assert.ok(html.includes('בלידה הקודמת עברתי ניתוח קיסרי'))
  assert.ok(html.includes('מצורפת גם כקובץ PDF'))
})

test('team WhatsApp summary', () => {
  const t = teamWhatsApp({ ...A, d_cord: 'other', d_cord_other: 'אמא שלי', special: 'x' }, { hasPdf: true, when: { date: '10/10/2026', time: '14:05' } })
  assert.match(t, /\*נועה כהן\*/)
  assert.match(t, /לידה: שנייה/)
  assert.match(t, /תאריך משוער: 01\/12\/2026/)
  assert.match(t, /כאב: רוצה לנסות בלי שיכוך תרופתי · לא להציע לה תרופות/)
  assert.match(t, /חבל הטבור: אמא שלי/)
  assert.match(t, /ביות: ביות מלא, בלי הפרדה/)
  assert.match(t, /מצורפת כקובץ PDF/)
  assert.equal(intlPhone('050-123-4567'), '972501234567')
})

test('API sends WhatsApp summary + PDF to the team and a copy to the mother', async () => {
  const calls = []
  const realFetch = globalThis.fetch
  globalThis.fetch = async (url, init) => { calls.push({ url: String(url), init }); return new Response('{}', { status: 200 }) }
  Object.assign(process.env, { WA_GREENAPI_INSTANCE: '7105123456', WA_GREENAPI_TOKEN: 'tok', WA_NOTIFY_PHONES: '0521111111, 0522222222' })
  delete process.env.GMAIL_USER
  const pdf = Buffer.from('%PDF-1.4 test').toString('base64')
  let status, json
  const res = { setHeader() {}, status(c) { status = c; return this }, json(j) { json = j; return this } }
  try { await handler({ method: 'POST', body: { answers: A, pdf, pdfName: 'תכנית לידה נועה כהן.pdf' } }, res) }
  finally { globalThis.fetch = realFetch }
  assert.equal(status, 200)
  assert.deepEqual(json, { ok: true, email: false, whatsapp: { team: 2, mother: true } })
  assert.ok(calls.every(c => c.url.startsWith('https://7105.api.greenapi.com/waInstance7105123456/')))
  const texts = calls.filter(c => c.url.includes('/sendMessage/')).map(c => JSON.parse(c.init.body))
  assert.deepEqual(texts.map(t => t.chatId).sort(), ['972521111111@c.us', '972522222222@c.us'])
  const files = calls.filter(c => c.url.includes('/sendFileByUpload/'))
  assert.equal(files.length, 3)   // two team members + the mother
  assert.ok(files.some(f => f.init.body.get('chatId') === '972501234567@c.us' && /תודה שמילאת/.test(f.init.body.get('caption'))))
})

test('API rejects a bot and an incomplete form', async () => {
  let status
  const res = { setHeader() {}, status(c) { status = c; return this }, json() { return this } }
  await handler({ method: 'POST', body: { answers: {} } }, res); assert.equal(status, 400)
  await handler({ method: 'POST', body: { answers: A, website: 'spam' } }, res); assert.equal(status, 200)
})
