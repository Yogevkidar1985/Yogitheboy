// ─── BIRTH PLAN FORM — public page ───────────────────────────────────────────
// Typeform-style, one question per screen. White canvas, dark type, purple
// accents (#8490D8 / #3F4EB0). Single typeface: Heebo.
//
// • Keyboard first: Enter = continue, letters pick options, ↑/↓ move between
//   questions, Ctrl/⌘+Enter inside long answers.
// • Auto-saves a draft to localStorage so she can stop and resume.
// • On submit the plan is e-mailed to Yogev (/api/birth-plan) and the finish
//   screen opens a WhatsApp chat with Hadas the doula, pre-filled with the plan.
import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { STEPS, SECTIONS, validateStep, buildPlan, planText, isEmpty } from './schema.js'
import { PLAN_EMAIL, DOULA_NAME, DOULA_PHONE } from './config.js'

const DRAFT_KEY = 'birth_plan_form_v1'
// Static single-file build (no /api, no print dialog): VITE_TARGET=artifact
const STATIC = import.meta.env.VITE_TARGET === 'artifact'
// Option keys shown as Hebrew letters; pressing the letter (Hebrew layout) or its
// position-equivalent Latin letter (a = א, b = ב…) picks the option
const LETTERS = 'אבגדהוזחטיכלמנסעפצקרשת'
const LATIN = 'abcdefghijklmnopqrstuv'

const store = {
  get() { try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null') } catch { return null } },
  set(v) { try { localStorage.setItem(DRAFT_KEY, JSON.stringify(v)) } catch {} },
  clear() { try { localStorage.removeItem(DRAFT_KEY) } catch {} },
}

const waLink = (phone, text) => `https://wa.me/${phone || ''}?text=${encodeURIComponent(text)}`
const mailLink = (to, subject, body) => `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`

export default function BirthPlanForm() {
  const draft = useMemo(() => store.get(), [])
  const [phase, setPhase] = useState('welcome')          // welcome | form | done
  const [answers, setAnswers] = useState(draft?.answers || {})
  const [idx, setIdx] = useState(0)
  const [dir, setDir] = useState(1)
  const [err, setErr] = useState('')
  const [returnToReview, setReturnToReview] = useState(false)
  const [sending, setSending] = useState(false)
  const [mailed, setMailed] = useState(false)

  const step = STEPS[idx]
  const section = SECTIONS.find(s => s.id === step.section)
  const questions = STEPS.filter(s => s.type !== 'intro' && s.type !== 'review')
  const qNo = questions.indexOf(step) + 1
  const progress = Math.round((idx / (STEPS.length - 1)) * 100)

  useEffect(() => { if (phase === 'form') store.set({ answers, idx, at: Date.now() }) }, [answers, idx, phase])

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
    if (!STATIC) try {
      const r = await fetch('/api/birth-plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) })
      const j = await r.json().catch(() => ({}))
      setMailed(!!(r.ok && j.ok))
    } catch { setMailed(false) }
    setSending(false)
    store.clear()
    setPhase('done')
  }

  // ── keyboard ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== 'form') return
    const onKey = e => {
      const tag = e.target.tagName
      if (e.key === 'Enter') {
        if (tag === 'TEXTAREA' && !(e.ctrlKey || e.metaKey)) return
        if (tag === 'BUTTON' && !e.target.classList.contains('bp-opt')) return
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
          <p className="bp-sub">כמה דקות של שקט, רק בשבילך. נעבור יחד על מה שחשוב לך בלידה: האווירה, הצוות והרגעים הראשונים עם התינוק, כדי שתגיעי ללידה רגועה ובטוחה.</p>
          {draft?.answers && Object.keys(draft.answers).length > 0 ? (
            <div className="bp-draft">
              <div className="bp-muted">מצאנו תכנית שהתחלת למלא</div>
              <button className="bp-btn" onClick={() => { setIdx(Math.min(Math.max(0, Number(draft.idx) || 0), STEPS.length - 1)); setPhase('form') }}>להמשיך מאיפה שעצרתי</button>
              <button className="bp-link" onClick={() => { store.clear(); setAnswers({}); setIdx(0); setPhase('form') }}>להתחיל מחדש</button>
            </div>
          ) : (
            <button className="bp-btn" onClick={() => setPhase('form')}>בואי נתחיל ←</button>
          )}
          <div className="bp-hint">לחצי <kbd>Enter ↵</kbd> כדי להתקדם</div>
        </div>
      </div>
    </Shell>
  )

  if (phase === 'done') {
    const text = planText(answers)
    const first = String(answers.name || '').trim().split(/\s+/)[0]
    return (
      <Shell>
        <div className="bp-center">
          <div className="bp-card bp-done">
            <div className="bp-check" aria-hidden>✓</div>
            <h1>תודה{first ? `, ${first}` : ''}!</h1>
            <p className="bp-sub">
              {mailed ? 'תכנית הלידה נשלחה ליוגב במייל. ' : ''}
              {mailed ? `עכשיו נשאר רק לשלוח אותה ל${DOULA_NAME} הדולה.` : `עכשיו נשאר לשלוח אותה ל${DOULA_NAME} הדולה וליוגב.`}
            </p>
            <div className="bp-actions">
              <a className="bp-btn bp-wa" href={waLink(DOULA_PHONE, text)} target="_blank" rel="noopener noreferrer">שליחה ל{DOULA_NAME} בוואטסאפ</a>
              {!DOULA_PHONE && <p className="bp-muted bp-small">בוואטסאפ בחרי את {DOULA_NAME} מרשימת אנשי הקשר</p>}
              {DOULA_PHONE && <a className="bp-btn bp-ghost" href={`tel:+${DOULA_PHONE}`}>התקשרות ל{DOULA_NAME}</a>}
              {!mailed && (
                <div className="bp-mailbox">
                  <div className="bp-muted">שליחה ליוגב במייל</div>
                  <div className="bp-addr" dir="ltr">{PLAN_EMAIL}</div>
                  <div className="bp-mailrow">
                    <CopyButton text={planText(answers, { bold: false })} />
                    <a className="bp-btn bp-ghost" href={mailLink(PLAN_EMAIL, `תכנית לידה: ${String(answers.name || '').trim()}`, planText(answers, { bold: false }))}>פתיחת המייל</a>
                  </div>
                  <p className="bp-muted bp-small">העתיקי את התכנית והדביקי אותה במייל לכתובת הזו</p>
                </div>
              )}
              {!STATIC && <button className="bp-btn bp-ghost" onClick={() => window.print()}>הדפסה / שמירה כ־PDF</button>}
            </div>
          </div>
          <PlanView answers={answers} printable />
        </div>
      </Shell>
    )
  }

  return (
    <Shell progress={progress}>
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
                onChange={v => set(step.id, v)} onPick={pick} onNext={next} err={err} returnToReview={returnToReview} />
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

function Shell({ children, progress }) {
  return (
    <div className="bp-root" dir="rtl">
      {progress != null && <div className="bp-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${progress}%` }} /></div>}
      <header className="bp-top"><span className="bp-brand">תכנית לידה</span><span className="bp-muted">עם {DOULA_NAME} · דולה</span></header>
      {children}
    </div>
  )
}

function Question({ step, qNo, total, value, onChange, onPick, onNext, err, returnToReview }) {
  const ref = useRef(null)
  const box = useRef(null)
  useEffect(() => { (ref.current || box.current)?.focus({ preventScroll: true }) }, [step.id])
  const multi = step.type === 'multi'
  return (
    <div className="bp-q" ref={box} tabIndex={-1}>
      <div className="bp-qno">{qNo} <span>מתוך {total}</span></div>
      <h2>{step.q}{step.required && <span className="bp-req" title="שדה חובה"> *</span>}</h2>
      {step.help && <p className="bp-help">{step.help}</p>}
      {multi && <p className="bp-help">אפשר לסמן כמה שרוצים — או לדלג</p>}

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

      {err && <div className="bp-error" role="alert">{err}</div>}
      {step.type !== 'choice' && (
        <div className="bp-row">
          <button className="bp-btn" onClick={onNext}>{returnToReview ? 'חזרה לסיכום' : (multi && isEmpty(value)) || (!step.required && isEmpty(value)) ? 'דילוג' : 'אישור ✓'}</button>
          <span className="bp-hint">{step.type === 'long' ? <>או <kbd>Ctrl + Enter ↵</kbd></> : <>או לחצי <kbd>Enter ↵</kbd></>}</span>
        </div>
      )}
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
        <button className="bp-btn bp-big" onClick={onSubmit} disabled={sending}>{sending ? 'שולחת…' : 'סיום ושליחת התכנית'}</button>
      </div>
      <p className="bp-muted bp-small">התכנית תישלח ליוגב במייל, ובמסך הבא תוכלי לשלוח אותה ל{DOULA_NAME} בוואטסאפ.</p>
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
      {printable && <h1 className="bp-print-title">תכנית לידה — {answers.name}</h1>}
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
