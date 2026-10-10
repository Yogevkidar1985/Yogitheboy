import { test } from 'node:test'
import assert from 'node:assert/strict'
import { STEPS, validateStep, buildPlan, planText } from './schema.js'
import { buildEmailHtml } from '../api/birth-plan.js'

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
  assert.equal(plan[3].items[0].value, 'אפס הפרדה — ביות מלא')
})

test('text and e-mail render and escape', () => {
  const t = planText(A)
  assert.match(t, /^\*תכנית לידה — נועה כהן\*/)
  assert.match(t, /✔ אני מבקשת להניק בלבד/)
  const html = buildEmailHtml({ ...A, name: '<b>x</b>' })
  assert.ok(html.includes('&lt;b&gt;x&lt;/b&gt;') && !html.includes('<b>x</b>'))
})
