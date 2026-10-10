// ─── Where a finished birth plan goes ────────────────────────────────────────
// E-mail: sent server-side by /api/birth-plan (PLAN_EMAIL_TO, same default);
// this list is only the manual fallback when automatic sending is unavailable. WhatsApp: the finish screen opens a chat with
// the doula, pre-filled with the whole plan.
export const PLAN_EMAILS = ['Daske2725@gmail.com', 'kidaryogev@gmail.com']
export const DOULA_NAME = 'הדס'
// International format, digits only (972…). Override with VITE_DOULA_PHONE.
export const DOULA_PHONE = (import.meta.env?.VITE_DOULA_PHONE || '972542299787').replace(/\D/g, '')
