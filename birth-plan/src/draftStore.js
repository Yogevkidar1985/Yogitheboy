// ─── Draft persistence ───────────────────────────────────────────────────────
// Two layers, newest wins on load:
// • localStorage — every viewer, same browser/device only.
// • the Claude Artifact viewer's per-person private store (db capability,
//   `data/users/<id>/draft`) — signed-in viewers who may write, any device.
//   Absent everywhere else (a plain website, signed-out or view-only guests),
//   in which case it silently stays off.
const KEY = 'birth_plan_form_v1'

const local = {
  get() { try { return JSON.parse(localStorage.getItem(KEY) || 'null') } catch { return null } },
  set(v) { try { localStorage.setItem(KEY, JSON.stringify(v)) } catch {} },
  clear() { try { localStorage.removeItem(KEY) } catch {} },
}

let remoteRef = null          // DocumentReference once available
let remoteReady = null        // Promise<DocumentReference|null>
let pending = null, timer = null, writing = false

function remote() {
  if (remoteReady) return remoteReady
  remoteReady = (async () => {
    try {
      const c = typeof window !== 'undefined' && window.claude
      if (!c?.use) return null
      const [db, user] = await Promise.all([c.use('db'), c.use('user')])
      if (!db || !user) return null
      const id = await user.id()
      if (!id) return null
      remoteRef = db.doc(`data/users/${id}/draft`)
      return remoteRef
    } catch { return null }
  })()
  return remoteReady
}

async function flush() {
  if (writing || !remoteRef || !pending) return
  writing = true
  const body = pending; pending = null
  try { await (body.clear ? remoteRef.delete() : remoteRef.set(body)) }
  catch (e) { if (e?.code === 'invalid_argument' || e?.code === 'revoked') remoteRef = null }   // can't write here: stay local-only
  writing = false
  if (pending) flush()
}

const isDraft = d => d && d.answers && typeof d.answers === 'object' && Object.keys(d.answers).length > 0

export const drafts = {
  local: () => (isDraft(local.get()) ? local.get() : null),

  // Newest of local and remote, or null. Never rejects.
  async load() {
    const l = this.local()
    const ref = await remote()
    if (!ref) return l
    try {
      const snap = await ref.get()
      const r = snap.exists ? snap.data() : null
      if (!isDraft(r)) return l
      return !l || (r.at || 0) > (l.at || 0) ? { answers: r.answers, idx: r.idx, at: r.at } : l
    } catch { return l }
  },

  // Local immediately; remote coalesced to one write per pause.
  save(d) {
    local.set(d)
    pending = { answers: d.answers, idx: d.idx, at: d.at }
    clearTimeout(timer)
    timer = setTimeout(() => remote().then(flush), 1200)
  },

  clear() {
    local.clear()
    clearTimeout(timer)
    pending = { clear: true }
    remote().then(flush)
  },

  // true once the cross-device layer is confirmed available
  async synced() { return !!(await remote()) },
}
