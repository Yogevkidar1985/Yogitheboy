/* התנהגויות ממשק: טוסטים, דיאלוג אישור, מצב טעינה, מגירת "עוד", שמירת מיקום גלילה, העתקה */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // --- טוסטים: הצלחה/מידע נעלמים לבד, שגיאה/אזהרה נשארות עד סגירה
  function dismiss(t) { t.classList.add('leaving'); setTimeout(function () { t.remove(); }, reduce ? 0 : 220); }
  document.querySelectorAll('.toast').forEach(function (t) {
    t.querySelector('.close').addEventListener('click', function () { dismiss(t); });
    if (t.dataset.kind === 'success' || t.dataset.kind === 'info') setTimeout(function () { dismiss(t); }, 5000);
  });
  window.toast = function (text, kind) {
    var stack = document.getElementById('toasts'); if (!stack) return;
    var t = document.createElement('div'); t.className = 'toast toast-' + (kind || 'info'); t.dataset.kind = kind || 'info';
    t.innerHTML = '<div class="toast-text"></div><button class="close" aria-label="סגירה">×</button>';
    t.querySelector('.toast-text').textContent = text; stack.appendChild(t);
    t.querySelector('.close').addEventListener('click', function () { dismiss(t); });
    if (kind !== 'error' && kind !== 'warning') setTimeout(function () { dismiss(t); }, 4000);
  };

  // --- מגירת "עוד"
  var moreBtn = document.getElementById('more-btn'), sheet = document.getElementById('more-sheet'), backdrop = document.getElementById('sheet-backdrop');
  function setSheet(open) { if (!sheet) return; sheet.classList.toggle('open', open); backdrop.classList.toggle('open', open); moreBtn.setAttribute('aria-expanded', open); }
  if (moreBtn) { moreBtn.addEventListener('click', function () { setSheet(!sheet.classList.contains('open')); }); backdrop.addEventListener('click', function () { setSheet(false); }); }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { setSheet(false); document.querySelectorAll('details.menu[open]').forEach(function (d) { d.removeAttribute('open'); }); } });

  // --- תפריטי פעולות: סגירה בלחיצה מחוץ / על הרקע
  document.addEventListener('click', function (e) {
    var open = document.querySelectorAll('details.menu[open]');
    if (!open.length) return;
    var inside = e.target.closest('details.menu');
    open.forEach(function (d) { if (d !== inside || e.target === d.querySelector('summary') && false) d.removeAttribute('open'); });
  });
  // במובייל: לחיצה על ה-backdrop (pseudo-element של summary) סוגרת
  document.addEventListener('click', function (e) {
    var s = e.target.closest('details.menu[open] > summary');
    if (s && window.innerWidth < 720) { var r = s.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) { e.preventDefault(); s.parentElement.removeAttribute('open'); } }
  }, true);

  // --- דיאלוג אישור לטפסים עם data-confirm
  var dlg = document.getElementById('confirm-dialog'), pending = null;
  function askConfirm(form, text, title) {
    if (!dlg || !dlg.showModal) return window.confirm(text);
    document.getElementById('confirm-text').textContent = text;
    document.getElementById('confirm-title').textContent = title || 'אישור פעולה';
    pending = form; dlg.showModal(); return false;
  }
  if (dlg) {
    document.getElementById('confirm-ok').addEventListener('click', function () { dlg.close(); if (pending) { var f = pending; pending = null; f.dataset.confirmed = '1'; if (f.requestSubmit) f.requestSubmit(); else f.submit(); } });
    document.getElementById('confirm-cancel').addEventListener('click', function () { pending = null; dlg.close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) { pending = null; dlg.close(); } });
  }

  // --- שליחת טפסים: אישור, מניעת שליחה כפולה, מצב טעינה, שמירת גלילה
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form.dataset.confirm && !form.dataset.confirmed) { e.preventDefault(); askConfirm(form, form.dataset.confirm, form.dataset.confirmTitle); return; }
    if (form.dataset.submitted) { e.preventDefault(); return; }
    form.dataset.submitted = '1';
    try { sessionStorage.setItem('scroll:' + location.pathname, String(window.scrollY)); } catch (err) {}
    var btn = e.submitter || form.querySelector('button[data-loading], button.btn-primary, button[type=submit]');
    if (btn && btn.classList.contains('btn')) setTimeout(function () { btn.classList.add('is-loading'); btn.setAttribute('aria-busy', 'true'); }, 0);
    progress(true);
  });
  // --- פס התקדמות בניווט
  var bar = document.getElementById('nav-progress');
  function progress(on) { if (bar) bar.classList.toggle('active', on); }
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href]');
    if (a && a.origin === location.origin && !a.target && !a.hasAttribute('download') && !a.href.includes('#')) progress(true);
  });
  window.addEventListener('pageshow', function () { progress(false); document.querySelectorAll('form[data-submitted]').forEach(function (f) { delete f.dataset.submitted; }); document.querySelectorAll('.is-loading').forEach(function (b) { b.classList.remove('is-loading'); }); });
  // --- שחזור גלילה אחרי שמירה שחוזרת לאותו עמוד
  try { var y = sessionStorage.getItem('scroll:' + location.pathname); if (y && document.referrer && new URL(document.referrer).pathname === location.pathname) { window.scrollTo(0, parseInt(y, 10)); } sessionStorage.removeItem('scroll:' + location.pathname); } catch (err) {}

  // --- העתקה ללוח
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]'); if (!btn) return;
    var src = btn.dataset.copy ? document.querySelector(btn.dataset.copy) : btn.closest('form, .card').querySelector('textarea');
    var text = src ? (src.value !== undefined ? src.value : src.textContent) : '';
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { window.toast('הטקסט הועתק', 'success'); });
  });
  // --- הגדלת תצוגה מקדימה
  document.addEventListener('click', function (e) { var z = e.target.closest('[data-zoom]'); if (z) { var w = document.querySelector(z.dataset.zoom); if (w) w.classList.toggle('zoomed'); } });
  // --- שדה תאריך: מציג את היום בעברית ליד הקלט
  document.querySelectorAll('input[type=date][data-hebrew]').forEach(function (inp) {
    var out = document.getElementById(inp.dataset.hebrew); if (!out) return;
    var days = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון'];
    function upd() { if (!inp.value) { out.textContent = ''; return; } var d = new Date(inp.value + 'T00:00:00'); out.textContent = 'יום ' + days[(d.getDay() + 6) % 7] + ', ' + d.toLocaleDateString('he-IL', { day: 'numeric', month: 'long', year: 'numeric' }); }
    inp.addEventListener('change', upd); upd();
  });
})();
