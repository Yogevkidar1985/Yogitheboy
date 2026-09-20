"""בדיקת רספונסיביות: כל מסך בכל רוחב – ללא גלילה אופקית, ואלמנטים לחיצים בגודל מגע.

הרצה (מול שרת עם נתוני הדגמה):  python scripts/ui_check.py http://127.0.0.1:8000 sapir demo1234 [out_dir]
דורש: pip install playwright (הדפדפן: PLAYWRIGHT_BROWSERS_PATH או chromium מותקן).
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

from playwright.async_api import async_playwright

WIDTHS = [320, 375, 390, 430, 768, 1280]
PAGES = [
    "/", "/children", "/children/new", "/children/3", "/groups",
    "/calendar?view=month&year=2026&month=9", "/calendar?view=week&week=2026-09-13", "/calendar?view=list",
    "/attendance?on=2026-09-16", "/billing?year=2026&month=9", "/billing/messages/list?year=2026&month=9",
    "/payments", "/payments/new?child_id=3", "/payments/upload/screenshot", "/receipts", "/intro", "/intro/new",
    "/month-close?year=2026&month=9", "/settings", "/settings/reports?year=2026", "/settings/audit",
]


async def main(base: str, username: str, password: str, out: str | None) -> int:
    problems: list[str] = []
    async with async_playwright() as p:
        exe = "/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None
        b = await p.chromium.launch(executable_path=exe)
        ctx = await b.new_context(viewport={"width": 1280, "height": 900}, locale="he-IL")
        pg = await ctx.new_page()
        await pg.goto(base + "/login")
        await pg.fill("input[name=username]", username)
        await pg.fill("input[name=password]", password)
        await pg.click("button[type=submit], button.btn-primary")
        await pg.wait_for_load_state()
        # מכינים נתונים: חיובים, תשלום, קבלה – כדי שיהיה מה להציג
        await pg.goto(base + "/billing?year=2026&month=9")
        if await pg.locator('form[action="/billing/compute"] button').count():
            await pg.click('form[action="/billing/compute"] button')
            await pg.wait_for_load_state()
        html = await pg.content()
        mm = re.search(r'/billing/(\d+)">לביא', html)
        if mm:
            await pg.goto(base + f"/billing/{mm.group(1)}")
            sel = 'button[formaction$="/approve"]'
            if await pg.locator(sel).count():
                await pg.click(sel); await pg.wait_for_load_state()
            await pg.goto(base + "/payments/new?child_id=3")
            await pg.fill("input[name=paid_on]", "2026-09-20"); await pg.fill("input[name=amount]", "320"); await pg.fill("input[name=reference]", "B-123")
            await pg.click("form.card button.btn-primary"); await pg.wait_for_load_state()
            if await pg.locator('form[action$="/prepare-receipts"] button').count():
                await pg.click('form[action$="/prepare-receipts"] button'); await pg.wait_for_load_state()
        await pg.goto(base + "/receipts")
        rid = re.search(r'/receipts/(\d+)"', await pg.content())
        await pg.goto(base + "/payments")
        pid = re.search(r'/payments/(\d+)"', await pg.content())
        pages = PAGES + [f"/receipts/{rid.group(1)}" if rid else "/receipts", f"/payments/{pid.group(1)}" if pid else "/payments", f"/billing/{mm.group(1)}" if mm else "/billing"]
        for w in WIDTHS:
            await pg.set_viewport_size({"width": w, "height": 844})
            for path in pages:
                await pg.goto(base + path)
                await pg.wait_for_load_state()
                await pg.wait_for_timeout(700)  # סיום אנימציות הכניסה
                sw, cw = await pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                if sw > cw + 1:
                    problems.append(f"{w}px {path}: גלילה אופקית ({sw} > {cw})")
                if w <= 430:
                    small = await pg.evaluate("""() => { const out=[]; document.querySelectorAll('a.btn,button.btn,.bottomnav a,.bottomnav button,.seg-opt span,.chip,.tab').forEach(e=>{const r=e.getBoundingClientRect(); if(r.width>0 && r.height>0 && r.height<34) out.push(e.className+' '+r.height.toFixed(0));}); return out.slice(0,5); }""")
                    if small:
                        problems.append(f"{w}px {path}: אלמנטים נמוכים ממטרת מגע: {small}")
                if out and w in (375, 1280):
                    name = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "home"
                    await pg.screenshot(path=os.path.join(out, f"{w}-{name}.png"), full_page=True)
        await b.close()
    for pr in problems:
        print("✗", pr)
    print("OK" if not problems else f"{len(problems)} בעיות", f"({len(WIDTHS)} רוחבים × {len(pages)} מסכים)")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(2)
    os.makedirs(sys.argv[4], exist_ok=True) if len(sys.argv) > 4 else None
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)))
