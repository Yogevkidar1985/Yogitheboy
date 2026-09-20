"""בונה אב-טיפוס אינטראקטיבי (קובץ HTML אחד) מהמסכים האמיתיים עם נתוני ההדגמה.

הרצה: python scripts/build_prototype.py out.html
הקובץ מכיל את כל המסכים כפי שהמערכת מרנדרת אותם, ניווט מלא ביניהם, וללא שמירה.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["CLUB_DATA_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402

import scripts.seed_demo as seed  # noqa: E402
from app.main import app  # noqa: E402

seed.main()
c = TestClient(app, follow_redirects=True)
c.post("/login", data={"username": "sapir", "password": "demo1234"})

# ---- מצב הדגמה עשיר: חיובים, אישורים, תשלומים, קבלות, הודעות
c.post("/billing/compute", data={"year": 2026, "month": 9})
html = c.get("/billing?year=2026&month=9").text
charge_ids = sorted(set(re.findall(r'/billing/(\d+)"', html)))
for cid in charge_ids:
    c.post(f"/billing/{cid}/approve")
c.post("/payments", data={"child_id": "3", "paid_on": "2026-09-18", "amount": "320", "method": "bank_transfer", "payer_name": "מיכל מזרחי", "reference": "77812", "auto_alloc": "1"})
c.post("/payments", data={"child_id": "1", "paid_on": "2026-09-19", "amount": "100", "method": "bit", "payer_name": "דנה לוי", "reference": "BIT-5521", "auto_alloc": "1"})
c.post("/payments", data={"child_id": "", "paid_on": "2026-09-20", "amount": "420", "method": "bank_transfer", "payer_name": "א. שלום", "reference": "90031"})
c.post("/payments/1/prepare-receipts")
c.post("/receipts/1/approve")
c.post("/receipts/1/issue", data={"confirm": "1"})
c.post("/receipts/1/send")
msgs = re.findall(r'/billing/messages/(\d+)/approve', c.get("/billing/messages/list?year=2026&month=9").text)
if msgs:
    body = re.search(r'<textarea name="body"[^>]*>(.*?)</textarea>', c.get("/billing/messages/list?year=2026&month=9").text, re.S).group(1)
    c.post(f"/billing/messages/{msgs[0]}/approve", data={"body": body})
    c.post(f"/billing/messages/{msgs[0]}/sent")
c.post("/intro", data={"child_name": "רוני אביב", "parent_name": "טל אביב", "parent_phone": "0507778888", "parent_email": "tal@example.com", "session_date": "2026-09-15", "amount": "150", "paid": "1", "paid_on": "2026-09-15", "method": "cash"})

# ---- המסכים לצילום
paths = ["/", "/children", "/children/new", "/children/new?copy_from=3", "/groups", "/intro", "/intro/new", "/intro/1",
         "/calendar?view=month&year=2026&month=9", "/calendar?view=month&year=2026&month=10", "/calendar?view=month&year=2026&month=8",
         "/calendar?view=week", "/calendar?view=week&week=2026-09-13", "/calendar?view=week&week=2026-09-20", "/calendar?view=week&week=2026-09-27", "/calendar?view=week&week=2026-09-06", "/calendar?view=list",
         "/attendance", "/billing?year=2026&month=9", "/billing?year=2026&month=9&status=open", "/billing?year=2026&month=9&status=paid", "/billing?year=2026&month=9&status=draft", "/billing?year=2026&month=9&status=warnings", "/billing?year=2026&month=10", "/billing?year=2026&month=8",
         "/billing/messages/list?year=2026&month=9", "/payments", "/payments?filter=unassigned", "/payments/new", "/payments/upload/screenshot",
         "/receipts", "/receipts?status=draft", "/receipts?status=sent", "/receipts?status=issued", "/receipts?status=approved", "/month-close?year=2026&month=9", "/month-close?year=2026&month=10", "/month-close?year=2026&month=8",
         "/settings", "/settings/users", "/settings/audit", "/settings/backup", "/settings/reports?year=2026",
         "/children?status=active", "/children?status=paused", "/children?status=left", "/children?group_id=1", "/children?group_id=2"]
for i in range(1, 8):
    paths += [f"/children/{i}", f"/payments/new?child_id={i}"]
for cid in charge_ids:
    paths.append(f"/billing/{cid}")
for i in range(1, 5):
    paths += [f"/payments/{i}", f"/receipts/{i}"]
for sid in range(1, 15):
    paths.append(f"/attendance?session_id={sid}")
import datetime as _dt  # noqa: E402

d = _dt.date(2026, 9, 1)
while d <= _dt.date(2026, 10, 31):
    paths.append(f"/attendance?on={d.isoformat()}")
    d += _dt.timedelta(days=1)

pages: dict[str, str] = {}
for p in paths:
    r = c.get(p)
    if r.status_code != 200:
        continue
    m = re.search(r'(<div class="shell">.*</div>)\s*<dialog', r.text, re.S)
    if not m:
        continue
    shell = m.group(1)
    shell = re.sub(r'<div class="toast-stack" id="toasts" aria-live="polite">\s*</div>', "", shell)
    shell = re.sub(r'\s(onchange|onclick|onsubmit)="[^"]*"', "", shell)
    pages[p] = shell
print(f"{len(pages)} מסכים נלכדו")

css = (ROOT / "app/static/style.css").read_text()
icons = (ROOT / "app/templates/_icons.html").read_text()
import json  # noqa: E402

pages_json = json.dumps(pages, ensure_ascii=False).replace("</", "<\\/")

out = f"""<title>ניהול חוג טיפוס</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700;800&display=swap">
<style>
{css}
body{{direction:rtl;background:var(--c-bg);color:var(--c-text);font-family:var(--font);font-size:var(--fs-md)}}
.proto-banner{{position:fixed;top:0;inset-inline:0;z-index:95;background:#0f172a;color:#e2e8f0;font-size:.78rem;padding:4px 12px;text-align:center;line-height:1.4}}
.proto-banner b{{color:#fff}}
@media (min-width:900px){{.sidebar{{padding-top:calc(var(--sp-5) + 24px)}}}}
@media (max-width:899px){{.appbar{{top:24px}}.shell{{padding-top:24px}}}}
</style>
<div class="proto-banner"><b>אב-טיפוס להדגמה</b> · המסכים האמיתיים של המערכת עם נתוני דוגמה · הניווט עובד, פעולות אינן נשמרות</div>
<div id="root" dir="rtl" lang="he">
{icons}
<div id="page"></div>
<div class="toast-stack" id="toasts" aria-live="polite"></div>
<dialog class="confirm" id="confirm-dialog"><h2><svg class="icon" aria-hidden="true"><use href="#i-warning"/></svg><span id="confirm-title">אישור פעולה</span></h2><p id="confirm-text" class="muted"></p><div class="actions"><button type="button" class="btn btn-primary" id="confirm-ok">אישור</button><button type="button" class="btn btn-ghost" id="confirm-cancel">ביטול</button></div></dialog>
</div>
<script>
(function(){{
var PAGES={pages_json};
var root=document.getElementById('page');
function norm(p){{ if(!p) return '/'; if(p[0]!=='/') p='/'+p; return p; }}
function resolve(p){{
  p=norm(p);
  if(PAGES[p]) return p;
  var base=p.split('?')[0];
  if(PAGES[base]) return base;
  var keys=Object.keys(PAGES);
  var same=keys.filter(function(k){{return k.split('?')[0]===base;}});
  if(same.length) return same[0];
  var parent=base.replace(/\\/[^\\/]+$/,'');
  if(parent && PAGES[parent]) return parent;
  return null;
}}
function toast(text,kind){{
  var stack=document.getElementById('toasts');
  var t=document.createElement('div'); t.className='toast toast-'+(kind||'info');
  var ic={{success:'check-circle',error:'x-circle',warning:'warning',info:'info'}}[kind||'info'];
  t.innerHTML='<svg class="icon" aria-hidden="true"><use href="#i-'+ic+'"/></svg><div class="toast-text"></div><button class="close" aria-label="סגירה"><svg class="icon"><use href="#i-x"/></svg></button>';
  t.querySelector('.toast-text').textContent=text; stack.appendChild(t);
  function go(){{t.classList.add('leaving');setTimeout(function(){{t.remove();}},220);}}
  t.querySelector('.close').addEventListener('click',go);
  if(kind!=='error'&&kind!=='warning') setTimeout(go,4000);
}}
function render(){{
  var p=resolve(decodeURIComponent(location.hash.slice(1)||'/'));
  if(!p){{ toast('המסך הזה לא נכלל באב-הטיפוס','warning'); return; }}
  root.innerHTML=PAGES[p];
  window.scrollTo(0,0);
  // דיווח נוכחות: מונה
  var form=root.querySelector('#att-form');
  if(form){{
    var total=form.querySelectorAll('.seg').length;
    var count=function(){{var n=0;form.querySelectorAll('.seg').forEach(function(s){{var c=s.querySelector('input:checked');if(c&&c.value!=='unreported')n++;}});var el=document.getElementById('counter');if(el)el.textContent=n+' מתוך '+total+' סומנו';}};
    form.addEventListener('change',function(){{count();var h=document.getElementById('save-hint');if(h)h.textContent='יש שינויים שלא נשמרו';}});
    var all=document.getElementById('mark-all'); if(all) all.addEventListener('click',function(){{form.querySelectorAll('input[value=present]').forEach(function(i){{i.checked=true;}});count();}});
    count();
  }}
  root.querySelectorAll('input[type=date][data-hebrew]').forEach(function(inp){{
    var out=document.getElementById(inp.dataset.hebrew); if(!out) return;
    var days=['שני','שלישי','רביעי','חמישי','שישי','שבת','ראשון'];
    inp.addEventListener('change',function(){{ location.hash='#/attendance?on='+inp.value; }});
  }});
}}
window.addEventListener('hashchange',render);
document.addEventListener('click',function(e){{
  var a=e.target.closest('a[href]');
  if(a){{ var h=a.getAttribute('href'); if(h && h[0]==='/'){{ e.preventDefault(); if(h.startsWith('/logout')) return; if(h.startsWith('/static')||h.startsWith('/payments/attachment')) return; if(resolve(h)) location.hash='#'+h; else toast('המסך הזה לא נכלל באב-הטיפוס','warning'); }} if(h && h.startsWith('https://wa.me')) {{ e.preventDefault(); toast('במערכת המלאה נפתח וואטסאפ עם ההודעה מוכנה','info'); }} return; }}
  if(e.target.closest('#more-btn')){{ var s=document.getElementById('more-sheet'), b=document.getElementById('sheet-backdrop'); var open=!s.classList.contains('open'); s.classList.toggle('open',open); b.classList.toggle('open',open); return; }}
  if(e.target.closest('#sheet-backdrop')){{ document.getElementById('more-sheet').classList.remove('open'); document.getElementById('sheet-backdrop').classList.remove('open'); return; }}
  var z=e.target.closest('[data-zoom]'); if(z){{ var w=document.querySelector(z.dataset.zoom); if(w) w.classList.toggle('zoomed'); return; }}
  var cp=e.target.closest('[data-copy]'); if(cp){{ var src=cp.closest('form,.card').querySelector('textarea'); if(src&&navigator.clipboard){{navigator.clipboard.writeText(src.value).then(function(){{toast('הטקסט הועתק','success');}});}} return; }}
  var inside=e.target.closest('details.menu');
  document.querySelectorAll('details.menu[open]').forEach(function(d){{ if(d!==inside) d.removeAttribute('open'); }});
}});
document.addEventListener('click',function(e){{
  var s=e.target.closest('details.menu[open] > summary');
  if(s&&window.innerWidth<720){{var r=s.getBoundingClientRect(); if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom){{e.preventDefault();s.parentElement.removeAttribute('open');}}}}
}},true);
var dlg=document.getElementById('confirm-dialog');
document.getElementById('confirm-ok').addEventListener('click',function(){{dlg.close();toast('הפעולה אושרה (באב-הטיפוס הנתונים אינם נשמרים)','success');}});
document.getElementById('confirm-cancel').addEventListener('click',function(){{dlg.close();}});
document.addEventListener('submit',function(e){{
  e.preventDefault(); var f=e.target;
  if(f.method && f.method.toLowerCase()==='get'){{ var q=new URLSearchParams(new FormData(f)).toString(); var p=f.getAttribute('action')||location.hash.slice(1).split('?')[0]; var target=p+(q?'?'+q:''); if(resolve(target)) location.hash='#'+target; else toast('הסינון הזה פועל במערכת המלאה','info'); return; }}
  if(f.dataset.confirm){{ document.getElementById('confirm-text').textContent=f.dataset.confirm; document.getElementById('confirm-title').textContent=f.dataset.confirmTitle||'אישור פעולה'; dlg.showModal(); return; }}
  toast('נשמר בהצלחה (הדגמה – במערכת המלאה הנתונים נשמרים)','success');
}});
document.addEventListener('change',function(e){{ var sel=e.target; if(sel.tagName==='SELECT' && sel.form && (sel.form.method||'get').toLowerCase()==='get' && sel.form.classList.contains('filters')) {{ var q=new URLSearchParams(new FormData(sel.form)).toString(); var p=sel.form.getAttribute('action')||location.hash.slice(1).split('?')[0]; var target=p+(q?'?'+q:''); if(resolve(target)) location.hash='#'+target; else toast('הסינון הזה פועל במערכת המלאה','info'); }} }});
document.addEventListener('keydown',function(e){{ if(e.key==='Escape'){{ var s=document.getElementById('more-sheet'); if(s){{s.classList.remove('open');document.getElementById('sheet-backdrop').classList.remove('open');}} }} }});
render();
}})();
</script>
"""
Path(sys.argv[1]).write_text(out)
print(f"נכתב {sys.argv[1]} ({len(out)//1024} KB)")
