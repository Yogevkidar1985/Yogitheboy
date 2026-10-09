# סרטון: איטום לפני החורף (קבוצת קורקוס)

- `kurkoos-itum-retivut.mp4`: 1080×1920 (רילס/סטוריז/טיקטוק), 55 שניות, קריינות Google Chirp3-HD (Iapetus) מסונכרנת למילה, מוזיקה קצבית 104 BPM, כתוביות צרובות עם הדגשת מילים, מוזיקה ואפקטים, סיום עם QR לכתבה.
- `subtitles.he.srt`: כתוביות נפרדות להעלאה לפלטפורמות.
- `cover.jpg`: תמונת שער.
- `source/`: קוד ההפקה.
  - `script.py`: התסריט, מילה בעברית לצד תעתיק פונטי (עברית ישראלית תקנית, הטעמה מסומנת).
  - `tts2.py`: קריינות MBROLA (קול עברי hb1) עם אינטונציה ומשכי הגאים מכוונים.
  - `gtts.py`, `align_g.py`: קריינות Google (המפתח נקרא רק ממשתנה הסביבה GOOGLE_TTS_API_KEY) וסנכרון מילים.
  - `align.py`: סנכרון ההקלטה לתסריט (חיתוך לפי הפסקות ו-DTW לכל מילה).
  - `beat.py`: מוזיקת הרקע הקצבית, מעובדת לפי הסצנות.
  - `asr.py`, `evalv.py`: בדיקת הבנה אוטומטית של הקריינות עם Whisper.
  - `textures.py`: חדר, כתם רטיבות וצבע לסצנת הקיר.
  - `sfx.py`, `mix.sh`: מוזיקה, אפקטים ומיקס.
  - `index.html`, `render.mjs`: אנימציה ורינדור (Playwright + ffmpeg).

קישור לכתבה: https://www.kurkoos-group.co.il/constructions/itum-retivut-chozeret-oto-makom
