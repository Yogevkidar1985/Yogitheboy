// ─── Birth plan → PDF (in the browser) ───────────────────────────────────────
// The browser lays the Hebrew out (RTL, Heebo) and html-to-image snapshots
// it once with the browser's own renderer; the shot is cut into blocks that jsPDF stacks onto A4 pages,
// never cutting a block in half unless it is taller than a page. Libraries load on demand.
import { buildPlan } from './schema.js'

const A4 = { w: 595.28, h: 841.89 }          // points
const M = 40                                   // page margin, points
const DOC_W = 720                              // CSS px width of the rendered document

const CSS = `
.pdfhost{position:fixed;top:0;left:-10000px}
.pdfdoc{width:${DOC_W}px;background:#fff;color:#26242B;font-family:Heebo,Arial,sans-serif;direction:rtl}
.pdfdoc *{box-sizing:border-box}
.pdfdoc .blk{padding:0 4px;background:#fff;display:flow-root}
.pdfdoc .head{padding:6px 4px 18px;border-bottom:3px solid #3F4EB0}
.pdfdoc .kick{font-size:15px;font-weight:700;color:#3F4EB0;letter-spacing:.3px}
.pdfdoc h1{font-size:34px;font-weight:800;margin:4px 0 14px;line-height:1.2}
.pdfdoc .facts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px 18px}
.pdfdoc .fact b{display:block;font-size:12px;font-weight:600;color:#75727C}
.pdfdoc .fact span{font-size:16px;font-weight:500}
.pdfdoc .sec{padding:22px 4px 6px;font-size:21px;font-weight:800;color:#3F4EB0}
.pdfdoc .item{padding:10px 14px 12px;border-radius:10px;background:#F6F6F9;margin:6px 0}
.pdfdoc .lbl{font-size:13px;font-weight:700;color:#4A4852;margin-bottom:4px}
.pdfdoc .val{font-size:16px;line-height:1.65;white-space:pre-wrap}
.pdfdoc ul{margin:0;padding:0;list-style:none}
.pdfdoc li{display:flex;gap:10px;font-size:16px;line-height:1.6;padding:3px 0}
.pdfdoc li i{font-style:normal;color:#1F9D55;font-weight:800;flex:none}
`

const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e }

const FACTS = ['טלפון', 'מספר לידה', 'תאריך לידה משוער', 'בית חולים', 'מלווים']

// Blocks in reading order; `keep` glues a heading to the block after it
function buildBlocks(a) {
  const blocks = []
  const plan = buildPlan(a)
  const about = plan.find(s => s.id === 'about')
  const head = el('div', 'blk head')
  head.append(el('div', 'kick', 'תכנית לידה'), el('h1', '', String(a.name || '').trim()))
  const facts = el('div', 'facts')
  for (const it of about?.items || []) if (FACTS.includes(it.label)) {
    const f = el('div', 'fact'); f.append(el('b', '', it.label), el('span', '', it.value)); facts.append(f)
  }
  head.append(facts)
  blocks.push({ node: head })

  for (const sec of plan) {
    const items = sec.id === 'about' ? sec.items.filter(it => !FACTS.includes(it.label) && it.label !== 'שם') : sec.items
    if (!items.length) continue
    blocks.push({ node: el('div', 'blk sec', sec.id === 'about' ? 'מה חשוב לי שתדעו' : sec.title), keep: true })
    for (const it of items) {
      const box = el('div', 'blk')
      const inner = el('div', 'item')
      inner.append(el('div', 'lbl', it.label))
      if (Array.isArray(it.value)) { const ul = el('ul'); it.value.forEach(x => { const li = el('li'); li.append(el('i', '', '✓'), el('span', '', x)); ul.append(li) }); inner.append(ul) }
      else inner.append(el('div', 'val', it.value))
      box.append(inner)
      blocks.push({ node: box })
    }
  }
  return blocks
}

export async function buildPlanPdf(answers) {
  const [{ toCanvas }, { jsPDF }] = await Promise.all([import('html-to-image'), import('jspdf')])
  const style = el('style', '', CSS)
  const root = el('div', 'pdfdoc')
  root.setAttribute('dir', 'rtl')
  const blocks = buildBlocks(answers)
  blocks.forEach(b => root.append(b.node))
  const host = el('div', 'pdfhost')               // off screen; the snapshot only sees `root`
  host.append(root)
  document.head.append(style); document.body.append(host)
  try {
    await document.fonts?.ready
    const pdf = new jsPDF({ unit: 'pt', format: 'a4', compress: true })
    const cw = A4.w - 2 * M, bottom = A4.h - M - 14       // room for the footer line
    // one capture of the whole document, then cut it into the blocks
    const scale = 2
    const big = await toCanvas(root, { pixelRatio: scale, backgroundColor: '#ffffff' })
    const top0 = root.getBoundingClientRect().top
    const pxPerPt = big.width / cw
    const shots = blocks.map(b => {
      const r = b.node.getBoundingClientRect()
      return { sy: Math.round((r.top - top0) * scale), sh: Math.round(r.height * scale), keep: b.keep }
    })
    const draw = (sy, sh, y) => {
      const part = document.createElement('canvas'); part.width = big.width; part.height = Math.max(1, sh)
      part.getContext('2d').drawImage(big, 0, sy, big.width, sh, 0, 0, big.width, sh)
      pdf.addImage(part.toDataURL('image/jpeg', 0.9), 'JPEG', M, y, cw, sh / pxPerPt)
    }
    let y = M
    for (let i = 0; i < shots.length; i++) {
      const { sy, sh, keep } = shots[i]
      const h = sh / pxPerPt
      const need = keep && shots[i + 1] ? h + Math.min(shots[i + 1].sh / pxPerPt, bottom - M) : h
      if (y > M && y + need > bottom) { pdf.addPage(); y = M }
      if (h <= bottom - y) { draw(sy, sh, y); y += h; continue }
      // taller than the room left: slice it across pages
      let done = 0
      while (done < sh) {
        const take = Math.min(Math.floor((bottom - y) * pxPerPt), sh - done)
        draw(sy + done, take, y)
        done += take; y += take / pxPerPt
        if (done < sh) { pdf.addPage(); y = M }
      }
    }
    // footer on every page, drawn by the browser so the Hebrew shapes right
    const pages = pdf.getNumberOfPages()
    const d = new Date(), date = `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear()}`
    for (let n = 1; n <= pages; n++) {
      pdf.setPage(n)
      const c = document.createElement('canvas'); c.width = Math.round(cw * 3); c.height = 42
      const g = c.getContext('2d')
      g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height)
      g.font = '500 26px Heebo, Arial, sans-serif'; g.fillStyle = '#75727C'; g.direction = 'rtl'; g.textBaseline = 'middle'
      g.textAlign = 'right'; g.fillText(`תכנית הלידה של ${String(answers.name || '').trim()} · מולא ב ${date}`, c.width, 21)
      g.textAlign = 'left'; g.fillText(`עמוד ${n} מתוך ${pages}`, 0, 21)
      pdf.addImage(c.toDataURL('image/png'), 'PNG', M, A4.h - M + 2, cw, 14)
    }
    return pdf.output('blob')
  } finally {
    host.remove(); style.remove()
  }
}

export const pdfFileName = a => `תכנית לידה ${String(a.name || '').trim()}.pdf`.replace(/[\\/:*?"<>|]/g, '')

export const blobToBase64 = blob => new Promise((res, rej) => {
  const r = new FileReader()
  r.onload = () => res(String(r.result).split(',')[1] || '')
  r.onerror = rej
  r.readAsDataURL(blob)
})
