// ─── Where a finished birth plan goes ────────────────────────────────────────
// E-mail: sent server-side by /api/birth-plan (recipient from PLAN_EMAIL_TO,
// falls back to this address). WhatsApp: the finish screen opens a chat with
// the doula, pre-filled with the whole plan.
export const PLAN_EMAIL = 'kidaryogev@gmail.com'
export const DOULA_NAME = 'הדס'
// International format, digits only (972…). Override with VITE_DOULA_PHONE.
export const DOULA_PHONE = (import.meta.env?.VITE_DOULA_PHONE || '').replace(/\D/g, '')
