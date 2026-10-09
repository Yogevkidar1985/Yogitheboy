# סרטון: איטום לפני החורף (קבוצת קורקוס)

- `kurkoos-itum-retivut.mp4`: 1080×1920 (רילס/סטוריז/טיקטוק), 66 שניות, קריינות בעברית, כתוביות צרובות עם הדגשת מילים, מוזיקה ואפקטים, סיום עם QR לכתבה.
- `subtitles.he.srt`: כתוביות נפרדות להעלאה לפלטפורמות.
- `cover.jpg`: תמונת שער.
- `source/`: קוד ההפקה.
  - `script.py`: התסריט, מילה בעברית לצד תעתיק פונטי (עברית ישראלית תקנית, הטעמה מסומנת).
  - `tts2.py`: קריינות MBROLA (קול עברי hb1) עם אינטונציה ומשכי הגאים מכוונים.
  - `asr.py`, `evalv.py`: בדיקת הבנה אוטומטית של הקריינות עם Whisper.
  - `textures.py`: חדר, כתם רטיבות וצבע לסצנת הקיר.
  - `sfx.py`, `mix.sh`: מוזיקה, אפקטים ומיקס.
  - `index.html`, `render.mjs`: אנימציה ורינדור (Playwright + ffmpeg).

קישור לכתבה: https://www.kurkoos-group.co.il/constructions/itum-retivut-chozeret-oto-makom
