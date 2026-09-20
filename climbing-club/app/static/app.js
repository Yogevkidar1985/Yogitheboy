// התנהגויות קטנות: העתקה ללוח, מניעת שליחה כפולה של טפסים, סגירת תפריטים
document.addEventListener('click', function (e) {
  var btn = e.target.closest('[data-copy]');
  if (btn) {
    var ta = btn.closest('form').querySelector('textarea');
    if (ta && navigator.clipboard) {
      navigator.clipboard.writeText(ta.value).then(function () { btn.textContent = 'הועתק ✔'; setTimeout(function () { btn.textContent = 'העתקת ההודעה'; }, 1500); });
    }
  }
  if (!e.target.closest('details.menu')) {
    document.querySelectorAll('details.menu[open]').forEach(function (d) { d.removeAttribute('open'); });
  }
});
document.addEventListener('submit', function (e) {
  var form = e.target;
  if (form.dataset.submitted) { e.preventDefault(); return; }
  form.dataset.submitted = '1';
  form.querySelectorAll('button[data-once], button.btn-primary').forEach(function (b) { setTimeout(function () { b.disabled = true; }, 0); });
});
