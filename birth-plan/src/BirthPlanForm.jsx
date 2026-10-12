// ─── BIRTH PLAN FORM — public page ───────────────────────────────────────────
// Typeform-style, one question per screen. White canvas, dark type, purple
// accents (#8490D8 / #3F4EB0). Single typeface: Heebo.
//
// • Keyboard first: Enter = continue, letters pick options, ↑/↓ move between
//   questions, Ctrl/⌘+Enter inside long answers.
// • Auto-saves a draft (browser + Claude per-person store when available) so
//   she can stop and resume where she left off.
// • On submit a PDF of the plan is built in the browser and /api/birth-plan
//   e-mails it and sends it on WhatsApp; the finish
//   screen opens a WhatsApp chat with Hadas the doula, pre-filled with the plan.
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { STEPS, SECTIONS, validateStep, buildPlan, planText, isEmpty, otherKey } from './schema.js'
import { PLAN_EMAILS, DOULA_NAME, DOULA_PHONE } from './config.js'
import { buildPlanPdf, pdfFileName, blobToBase64 } from './pdf.js'
import { drafts } from './draftStore.js'

// Static single-file build (no /api, no print dialog): VITE_TARGET=artifact
const STATIC = import.meta.env.VITE_TARGET === 'artifact'
// Static website (GitHub Pages): PDF and the phone's share sheet work, but
// there is no server, so nothing is sent automatically.
const HAS_API = !STATIC && import.meta.env.VITE_TARGET !== 'pages'
// Option keys shown as Hebrew letters; pressing the letter (Hebrew layout) or its
// position-equivalent Latin letter (a = א, b = ב…) picks the option
const LETTERS = 'אבגדהוזחטיכלמנסעפצקרשת'
const LATIN = 'abcdefghijklmnopqrstuv'


const QUESTIONS = STEPS.filter(s => s.type !== 'intro' && s.type !== 'review')
function draftWhere(d) {
  const step = STEPS[Math.min(Math.max(0, Number(d.idx) || 0), STEPS.length - 1)]
  const n = QUESTIONS.indexOf(step) + 1
  return n > 0 ? ` (נעצרת בשאלה ${n} מתוך ${QUESTIONS.length})` : step.type === 'review' ? ' (הגעת עד הסיכום)' : ''
}

const waLink = (phone, text) => `https://wa.me/${phone || ''}?text=${encodeURIComponent(text)}`
const mailLink = (to, subject, body) => `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`

export default function BirthPlanForm() {
  const [draft, setDraft] = useState(() => drafts.local())
  const [phase, setPhase] = useState('welcome')          // welcome | form | done
  const [answers, setAnswers] = useState({})
  const [savedAt, setSavedAt] = useState(0)
  const [cloud, setCloud] = useState(false)
  const [idx, setIdx] = useState(0)
  const [dir, setDir] = useState(1)
  const [err, setErr] = useState('')
  const [returnToReview, setReturnToReview] = useState(false)
  const [sending, setSending] = useState(false)
  const [delivery, setDelivery] = useState(null)       // { email, whatsapp: { team, mother } } from the API
  const [pdf, setPdf] = useState(null)                 // Blob

  const step = STEPS[idx]
  const section = SECTIONS.find(s => s.id === step.section)
  const questions = STEPS.filter(s => s.type !== 'intro' && s.type !== 'review')
  const qNo = questions.indexOf(step) + 1
  const progress = Math.round((idx / (STEPS.length - 1)) * 100)

  // newer draft from another device, if the viewer has one
  useEffect(() => {
    let live = true
    drafts.load().then(d => { if (live && d) setDraft(cur => (!cur || (d.at || 0) > (cur.at || 0) ? d : cur)) })
    drafts.synced().then(ok => live && setCloud(ok))
    return () => { live = false }
  }, [])

  useEffect(() => {
    if (phase !== 'form' || !Object.keys(answers).length) return
    const at = Date.now()
    drafts.save({ answers, idx, at }); setSavedAt(at)
  }, [answers, idx, phase])

  const resume = () => {
    setAnswers(draft.answers)
    setIdx(Math.min(Math.max(0, Number(draft.idx) || 0), STEPS.length - 1))
    setPhase('form')
  }
  const restart = () => { drafts.clear(); setDraft(null); setAnswers({}); setIdx(0); setPhase('form') }

  const set = useCallback((id, v) => { setAnswers(a => ({ ...a, [id]: v })); setErr('') }, [])

  const go = useCallback(to => {
    if (to < 0 || to >= STEPS.length) return
    setDir(to > idx ? 1 : -1); setErr(''); setIdx(to)
    window.scrollTo({ top: 0 })
  }, [idx])

  const next = useCallback(() => {
    const e = validateStep(step, answers)
    if (e) return setErr(e)
    if (returnToReview) { setReturnToReview(false); return go(STEPS.length - 1) }
    go(idx + 1)
  }, [step, answers, idx, go, returnToReview])

  const editStep = id => { setReturnToReview(true); go(STEPS.findIndex(s => s.id === id)) }

  const submit = async () => {
    const missing = STEPS.find(s => validateStep(s, answers))
    if (missing) { setReturnToReview(true); go(STEPS.indexOf(missing)); return }
    setSending(true)
    let blob = null
    if (!STATIC) try { blob = await buildPlanPdf(answers) } catch {}   // the shared Claude link can't hand out files
    setPdf(blob)
    if (HAS_API) try {
      const r = await fetch('/api/birth-plan', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers, pdf: blob ? await blobToBase64(blob) : '', pdfName: pdfFileName(answers), website: '' }) })
      const j = await r.json().catch(() => ({}))
      setDelivery(j && j.ok ? j : null)
    } catch { setDelivery(null) }
    setSending(false)
    drafts.clear()
    setPhase('done')
    window.scrollTo({ top: 0 })
  }

  // ── keyboard ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== 'form') return
    const onKey = e => {
      const tag = e.target.tagName
      if (e.key === 'Enter') {
        if (tag === 'TEXTAREA' && !(e.ctrlKey || e.metaKey)) return
        if (tag === 'BUTTON' && !e.target.matches('.bp-opt, .bp-chip')) return
        if (step.type === 'review') return
        e.preventDefault(); next(); return
      }
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.key === 'ArrowUp') { e.preventDefault(); go(idx - 1) }
      if (e.key === 'ArrowDown') { e.preventDefault(); next() }
      if ((step.type === 'choice' || step.type === 'multi') && e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
        const k = e.key.toLowerCase(), i = LETTERS.includes(k) ? LETTERS.indexOf(k) : LATIN.indexOf(k)
        const opt = i >= 0 && step.opts[i]
        if (opt) pick(opt.v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const pick = v => {
    if (step.type === 'choice') {
      set(step.id, v)
      if (step.other && v === step.other.v) return   // wait for the name, then "אישור"
      setTimeout(() => {
        setDir(1)
        if (returnToReview) { setReturnToReview(false); setIdx(STEPS.length - 1) } else setIdx(i => i + 1)
      }, 260)
    } else {
      const cur = answers[step.id] || []
      set(step.id, cur.includes(v) ? cur.filter(x => x !== v) : [...cur, v])
    }
  }

  // ── screens ────────────────────────────────────────────────────────────────
  if (phase === 'welcome') return (
    <Shell>
      <div className="bp-center">
        <div className="bp-card bp-welcome">
          <div className="bp-heart" aria-hidden>♡</div>
          <h1>תכנית הלידה שלך</h1>
          <p className="bp-sub">השאלון עובר איתך על מה שחשוב לך בלידה ובימים שאחריה. זה לוקח בערך עשר דקות, ואפשר לעצור ולהמשיך מתי שנוח לך.</p>
          {draft ? (
            <div className="bp-draft">
              <div className="bp-muted">מצאנו תכנית שהתחלת למלא{draftWhere(draft)}</div>
              <button className="bp-btn" onClick={resume}>להמשיך מאיפה שעצרתי ←</button>
              <button className="bp-link" onClick={restart}>להתחיל מחדש</button>
            </div>
          ) : (
            <button className="bp-btn" onClick={() => setPhase('form')}>בואי נתחיל ←</button>
          )}
          <div className="bp-hint bp-desk">לחצי <kbd>Enter ↵</kbd> כדי להתקדם</div>
        </div>
      </div>
    </Shell>
  )

  if (phase === 'done') {
    const text = planText(answers)
    const first = String(answers.name || '').trim().split(/\s+/)[0]
    const sent = !!delivery && (delivery.email || delivery.whatsapp?.team > 0)
    const shareable = !sent && !!pdf && canSharePdf(pdf, pdfFileName(answers))
    return (
      <Shell>
        <div className="bp-center">
          <div className="bp-card bp-done">
            <div className="bp-check" aria-hidden>✓</div>
            <h1>תודה{first ? `, ${first}` : ''}!</h1>
            {sent ? (
              <p className="bp-sub">
                התכנית נשלחה ל{DOULA_NAME}{delivery.email ? ' ולמייל' : ''}.
                {delivery.whatsapp?.mother ? ' שלחנו לך עותק בוואטסאפ, כדאי לשמור אותו ולהביא ללידה.' : ''}
              </p>
            ) : (
              <p className="bp-sub">{!HAS_API ? (pdf ? `התכנית מוכנה כקובץ PDF. נשאר רק לשלוח אותה ל${DOULA_NAME}.` : `נשאר רק לשלוח את התכנית ל${DOULA_NAME}.`) : 'השליחה האוטומטית לא עברה הפעם. אפשר לשלוח את התכנית בעצמך, זה לוקח רגע.'}</p>
            )}
            <div className="bp-actions">
              {!sent && shareable && <SharePdfButton blob={pdf} name={pdfFileName(answers)} className="bp-btn bp-wa" />}
              {!sent && shareable && <SharePdfButton kind="mail" blob={pdf} name={pdfFileName(answers)} plainText={planText(answers, { bold: false })} className="bp-btn bp-mail" />}
              {!sent && <a className={shareable ? 'bp-btn bp-ghost' : 'bp-btn bp-wa'} href={waLink(DOULA_PHONE, text)} target="_blank" rel="noopener noreferrer">{shareable ? `שליחה ל${DOULA_NAME} כהודעת טקסט` : `שליחה ל${DOULA_NAME} בוואטסאפ`}</a>}
              {!sent && !DOULA_PHONE && <p className="bp-muted bp-small">בוואטסאפ בחרי את {DOULA_NAME} מרשימת אנשי הקשר</p>}
              {pdf && <PdfButton blob={pdf} name={pdfFileName(answers)} />}
              {!sent && (
                <div className="bp-mailbox">
                  <div className="bp-muted">שליחה במייל</div>
                  {PLAN_EMAILS.map(m => <div key={m} className="bp-addr" dir="ltr">{m}</div>)}
                  <div className="bp-mailrow">
                    <CopyButton text={planText(answers, { bold: false })} />
                    <a className="bp-btn bp-ghost" href={mailLink(PLAN_EMAILS.join(','), `תכנית לידה: ${String(answers.name || '').trim()}`, planText(answers, { bold: false }))}>פתיחת המייל</a>
                  </div>
                  <p className="bp-muted bp-small">העתיקי את התכנית והדביקי אותה במייל לכתובות האלו</p>
                </div>
              )}
              {DOULA_PHONE && <a className="bp-btn bp-ghost" href={`tel:+${DOULA_PHONE}`}>התקשרות ל{DOULA_NAME}</a>}
            </div>
          </div>
          <PlanView answers={answers} printable />
        </div>
      </Shell>
    )
  }

  return (
    <Shell progress={progress} saved={!!savedAt} cloud={cloud}>
      <div className="bp-stage">
        <AnimatePresence mode="wait" custom={dir} initial={false}>
          <motion.div key={step.id} custom={dir} className="bp-step"
            initial={{ opacity: 0, y: dir * 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: dir * -40 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}>
            {step.type === 'intro' ? (
              <div className="bp-intro">
                <div className="bp-kicker">חלק {section.n} מתוך {SECTIONS.length}</div>
                <h2>{section.title}</h2>
                <p className="bp-sub">{section.desc}</p>
                <button className="bp-btn" onClick={next}>המשך</button>
              </div>
            ) : step.type === 'review' ? (
              <Review answers={answers} onEdit={editStep} onSubmit={submit} sending={sending} />
            ) : (
              <Question step={step} qNo={qNo} total={questions.length} value={answers[step.id]}
                onChange={v => set(step.id, v)} onPick={pick}
                otherValue={answers[otherKey(step.id)] || ''} onOther={v => set(otherKey(step.id), v)} onNext={next} err={err} returnToReview={returnToReview} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      {step.type !== 'review' && <nav className="bp-nav" aria-label="ניווט">
        <button onClick={() => go(idx - 1)} disabled={idx === 0} aria-label="לשאלה הקודמת">▲</button>
        <button onClick={next} aria-label="לשאלה הבאה">▼</button>
      </nav>}
    </Shell>
  )
}

function PdfButton({ blob, name }) {
  const [url] = useState(() => URL.createObjectURL(blob))
  useEffect(() => () => URL.revokeObjectURL(url), [url])
  return <a className="bp-btn bp-ghost" href={url} download={name}>הורדת התכנית כקובץ PDF</a>
}

// Backup when automatic delivery failed: the phone's own share sheet with the
// PDF attached, so she picks WhatsApp and Hadas. Only where the browser can
// share files (most phones); elsewhere the text button below does the job.
const pdfFile = (blob, name) => { try { return new File([blob], name, { type: 'application/pdf' }) } catch { return null } }
const canSharePdf = (blob, name) => {
  const f = blob && pdfFile(blob, name)
  try { return !!(f && navigator.canShare?.({ files: [f] })) } catch { return false }
}
function SharePdfButton({ blob, name, className, kind = 'wa', plainText = '' }) {
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const share = () => {
    setErr(''); setMsg('')
    const file = pdfFile(blob, name)
    const title = name.replace(/\.pdf$/, '')
    let data = { files: [file], title }
    if (kind === 'mail') {
      // the share sheet can't fill in recipients, so the addresses go to the clipboard
      navigator.clipboard?.writeText(PLAN_EMAILS.join(', ')).then(() => setMsg('כתובות המייל הועתקו. הדביקי אותן בשדה "אל".'), () => {})
      data = { files: [file], title, text: `${title} מצורפת כקובץ PDF.\n\n${plainText}` }
    }
    navigator.share(data).catch(e => { if (e?.name !== 'AbortError') setErr('השיתוף לא נפתח. אפשר להוריד את הקובץ ולצרף אותו ידנית.') })
  }
  return (
    <>
      <button type="button" className={className} onClick={share}>
        {kind === 'mail' ? 'שליחה במייל עם קובץ PDF' : `שליחה ל${DOULA_NAME} בוואטסאפ עם קובץ PDF`}
      </button>
      <p className="bp-muted bp-small">{kind === 'mail' ? 'במסך השיתוף בחרי את אפליקציית המייל' : `במסך השיתוף בחרי וואטסאפ ואז את ${DOULA_NAME}`}</p>
      {msg && <p className="bp-saved bp-small" role="status">{msg}</p>}
      {err && <p className="bp-error">{err}</p>}
    </>
  )
}

function CopyButton({ text }) {
  const [done, setDone] = useState(false)
  const [manual, setManual] = useState(false)
  const area = useRef(null)
  useEffect(() => { if (manual) area.current?.select() }, [manual])
  const copy = () => {
    const p = navigator.clipboard?.writeText ? navigator.clipboard.writeText(text) : Promise.reject()
    p.then(() => { setDone(true); setTimeout(() => setDone(false), 2000) }).catch(() => setManual(true))
  }
  return (
    <>
      <button className="bp-btn bp-ghost" onClick={copy}>{done ? 'הועתק ✓' : 'העתקת התכנית'}</button>
      {manual && (
        <div className="bp-manual">
          <p className="bp-muted bp-small">ההעתקה האוטומטית לא זמינה כאן. הטקסט מסומן: לחצי עליו לחיצה ארוכה ובחרי "העתק".</p>
          <textarea id="bp-plan-copy" ref={area} className="bp-input bp-long" readOnly rows={8} value={text} onFocus={e => e.target.select()} />
        </div>
      )}
    </>
  )
}

function Shell({ children, progress, saved, cloud }) {
  return (
    <div className="bp-root" dir="rtl">
      {progress != null && <div className="bp-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${progress}%` }} /></div>}
      <header className="bp-top"><span className="bp-brand">תכנית לידה</span>
        {saved ? <span className="bp-saved" role="status">✓ {cloud ? 'נשמר, אפשר להמשיך גם ממכשיר אחר' : 'נשמר, אפשר לחזור ולהמשיך'}</span>
               : <span className="bp-muted">עם {DOULA_NAME} · דולה</span>}</header>
      {children}
    </div>
  )
}

function Question({ step, qNo, total, value, onChange, onPick, onNext, err, returnToReview, otherValue, onOther }) {
  const ref = useRef(null)
  const box = useRef(null)
  useEffect(() => { (ref.current || box.current)?.focus({ preventScroll: true }) }, [step.id])
  const multi = step.type === 'multi'
  return (
    <div className="bp-q" ref={box} tabIndex={-1}>
      <div className="bp-qno">{qNo} <span>מתוך {total}</span></div>
      <h2>{step.q}{step.required && <span className="bp-req" title="שדה חובה"> *</span>}</h2>
      {step.help && <p className="bp-help">{step.help}</p>}
      {multi && <p className="bp-help">אפשר לסמן כמה תשובות, או לדלג</p>}

      {(step.type === 'text' || step.type === 'phone') && (
        <input ref={ref} className="bp-input" type={step.type === 'phone' ? 'tel' : 'text'} dir={step.type === 'phone' ? 'ltr' : 'rtl'}
          value={value || ''} placeholder={step.ph} autoComplete={step.autocomplete || (step.type === 'phone' ? 'tel' : 'off')}
          inputMode={step.type === 'phone' ? 'tel' : undefined} onChange={e => onChange(e.target.value)} />
      )}
      {step.type === 'date' && (
        <input ref={ref} className="bp-input bp-date" type="date" value={value || ''} onChange={e => onChange(e.target.value)} />
      )}
      {step.type === 'long' && (
        <textarea ref={ref} className="bp-input bp-long" rows={4} value={value || ''} placeholder={step.ph} onChange={e => onChange(e.target.value)} />
      )}
      {(step.type === 'choice' || multi) && (
        <div className={`bp-opts${step.grid ? ' bp-grid' : ''}`} role={multi ? 'group' : 'radiogroup'}>
          {step.opts.map((opt, i) => {
            const on = multi ? (value || []).includes(opt.v) : value === opt.v
            return (
              <button key={opt.v} type="button" className={`bp-opt${on ? ' on' : ''}${multi ? ' multi' : ''}`}
                role={multi ? 'checkbox' : 'radio'} aria-checked={on} onClick={() => onPick(opt.v)}>
                <span className="bp-key">{multi && on ? '✓' : LETTERS[i]}</span>
                <span className="bp-opt-l">{opt.l}</span>
              </button>
            )
          })}
        </div>
      )}

      {step.other && value === step.other.v && (
        <input autoFocus className="bp-input" type="text" value={otherValue} placeholder={step.other.ph} onChange={e => onOther(e.target.value)} />
      )}
      {step.examples && <Examples items={step.examples} single={step.single} other={step.otherChip} inputRef={ref} value={value || ''} long={step.type === 'long'} onChange={onChange} />}

      {err && <div className="bp-error" role="alert">{err}</div>}
      {(step.type !== 'choice' || (step.other && value === step.other.v)) && (
        <div className="bp-row">
          <button className="bp-btn" onClick={onNext}>{returnToReview ? 'חזרה לסיכום' : (multi && isEmpty(value)) || (!step.required && isEmpty(value)) ? 'דילוג' : 'אישור ✓'}</button>
          <span className="bp-hint bp-desk">{step.type === 'long' ? <>או <kbd>Ctrl + Enter ↵</kbd></> : <>או לחצי <kbd>Enter ↵</kbd></>}</span>
        </div>
      )}
    </div>
  )
}

// Tap-to-add inspiration: long answers get one idea per line, short ones a comma list
function Examples({ items, single, other, inputRef, value, long, onChange }) {
  const [hint, setHint] = useState('')
  const [focusTick, setFocusTick] = useState(0)
  // after the separator is in the field, put the cursor at its end
  useEffect(() => {
    if (!focusTick) return
    const el = inputRef?.current
    if (el) { el.focus(); el.setSelectionRange?.(el.value.length, el.value.length) }
  }, [focusTick])
  const sep = long ? '\n' : ', '
  const has = x => single ? value.trim() === x : value.split(long ? '\n' : ',').some(p => p.trim() === x)
  const add = x => {
    if (single) return onChange(has(x) ? '' : x)
    if (has(x)) return onChange(value.split(long ? '\n' : ',').map(p => p.trim()).filter(p => p && p !== x).join(sep))
    onChange(value.trim() ? `${value.replace(/[\s,]+$/, '')}${sep}${x}` : x)
  }
  return (
    <div className="bp-examples">
      <div className="bp-muted bp-small">{single ? "אפשר לבחור מהרשימה:" : "רעיונות לדוגמה, לחצי כדי להוסיף:"}</div>
      <div className="bp-chips">
        {items.map(x => (
          <button key={x} type="button" className={`bp-chip${has(x) ? ' on' : ''}`} aria-pressed={has(x)} onClick={() => add(x)}>
            {has(x) ? '✓ ' : '+ '}{x}
          </button>
        ))}
        {other && (
          <button type="button" className="bp-chip" onClick={() => {
            if (single) { if (items.includes(value.trim())) onChange('') }
            else if (value.trim() && !/[,\n]\s*$/.test(value)) onChange(`${value.replace(/\s+$/, '')}${sep}`)
            setHint(other.hint)
            setFocusTick(t => t + 1)
          }}>+ {other.l}</button>
        )}
      </div>
      {hint && <div className="bp-muted bp-small" role="status">{hint}</div>}
    </div>
  )
}

function Review({ answers, onEdit, onSubmit, sending }) {
  return (
    <div className="bp-review">
      <div className="bp-kicker">סיכום</div>
      <h2>תכנית הלידה שלך</h2>
      <p className="bp-sub">עברי על התכנית. אפשר לערוך כל חלק בלחיצה על "עריכה".</p>
      <PlanView answers={answers} onEdit={onEdit} />
      <div className="bp-row">
        <button className="bp-btn bp-big" onClick={onSubmit} disabled={sending}>{sending ? 'שולחת את התכנית…' : 'סיום ושליחת התכנית'}</button>
      </div>
      <p className="bp-muted bp-small">{!HAS_API ? `במסך הבא תוכלי לשלוח את התכנית ל${DOULA_NAME} בוואטסאפ ובמייל.` : `התכנית תישלח ל${DOULA_NAME} בוואטסאפ ובמייל, ותקבלי עותק לוואטסאפ שלך.`}</p>
    </div>
  )
}

// Edit target for each summary row — the step whose title / label matches
const EDIT_ID = { 'שם': 'name', 'טלפון': 'phone', 'מספר לידה': 'birthNo', 'תאריך לידה משוער': 'dueDate', 'בית חולים': 'hospital', 'מלווים': 'companions', 'פרטים מיוחדים לצוות': 'special', 'בקשות ורצונות': 'wishes' }
const stepIdFor = (secId, label) => EDIT_ID[label] || STEPS.find(s => s.section === secId && s.title === label)?.id

function PlanView({ answers, onEdit, printable }) {
  const plan = buildPlan(answers)
  const secs = SECTIONS.filter(s => s.id !== 'review').map(s => plan.find(p => p.id === s.id) || { id: s.id, title: s.title, items: [] })
  return (
    <div className={`bp-plan${printable ? ' bp-printable' : ''}`}>
      {printable && <h1 className="bp-print-title">תכנית הלידה של {answers.name}</h1>}
      {secs.map(sec => sec.items.length ? (
        <section key={sec.id} className="bp-sec">
          <h3>{sec.title}</h3>
          {sec.items.map(it => (
            <div key={it.label} className="bp-item">
              <div className="bp-item-h">
                <span className="bp-item-l">{it.label}</span>
                {onEdit && <button className="bp-link" onClick={() => onEdit(stepIdFor(sec.id, it.label))}>עריכה</button>}
              </div>
              {Array.isArray(it.value)
                ? <ul>{it.value.map(x => <li key={x}>{x}</li>)}</ul>
                : <div className="bp-item-v">{it.value}</div>}
            </div>
          ))}
        </section>
      ) : onEdit && (
        <section key={sec.id} className="bp-sec bp-sec-empty">
          <h3>{sec.title}</h3>
          <div className="bp-item-h"><span className="bp-muted">לא סומנו העדפות</span>
            <button className="bp-link" onClick={() => onEdit(STEPS.find(s => s.section === sec.id && s.type !== 'intro').id)}>הוספה</button></div>
        </section>
      ))}
    </div>
  )
}
