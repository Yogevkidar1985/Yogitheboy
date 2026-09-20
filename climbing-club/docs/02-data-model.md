# 2. מבנה מאגר הנתונים

מסד הנתונים: SQLite (קובץ יחיד `data/club.db`, גיבוי בלחיצה). ה-ORM: SQLAlchemy 2. הטבלאות מוגדרות ב-`app/models.py`.

```
users ─┐                                  settings, audit_log, month_closures
       │
children ──< child_contacts >── contacts
   │  ├──< memberships >── groups ──< sessions ──< attendance >──┐
   │  ├──< billing_rules                  │ (moved_to → sessions)  │
   │  ├──< monthly_charges ──< payment_allocations >── payments ──┤
   │  │        │  └── payment_messages                    │      │
   │  ├──< adjustments                                    │      │
   │  └──< receipts ──────────────────────────────────────┘──────┘
   └──< intro_sessions ── sessions / payments
```

## טבלאות

### ילדים ואנשי קשר
| טבלה | שדות עיקריים | הערות |
|---|---|---|
| `children` | full_name, national_id, status (active/paused/left), joined_on, left_on, receipt_mode (monthly / per_session), hmo, receipt_notes, receipt_required_fields, notes | הפרדה מלאה מפרטי ההורה |
| `contacts` | full_name, phone, email, national_id | הורה או משלם; משותף לאחים |
| `child_contacts` | child_id, contact_id, relation, is_message_contact, is_billing_contact | מי מקבל הודעות ומי מופיע בקבלה |
| `billing_rules` | child_id, effective_from, effective_to, method, price_per_session, fixed_monthly_amount, description | היסטוריית תעריפים – שינוי תעריף לא משנה חודשים סגורים |
| `memberships` | child_id, group_id, from_date, to_date | ילד יכול להיות בכמה קבוצות |

### לוח ומפגשים
| טבלה | שדות | הערות |
|---|---|---|
| `groups` | name, weekday, start_time, is_active | ראשון = 6, רביעי = 2 (Python weekday) |
| `sessions` | date, group_id, kind (regular/intro), status, is_extra, original_date, moved_to_id, reason, notes, created_by, changed_by, changed_at | ייחודיות (date, group_id, kind). מפגש שהועבר נשאר עם קישור למפגש החדש |
| `attendance` | session_id, child_id, status (present/absent/unreported), charge_override (default/charge/no_charge), price_override, note, reported_at, reported_by | חריג חיוב ברמת מפגש בודד |

### חיובים והודעות
| טבלה | שדות | הערות |
|---|---|---|
| `monthly_charges` | child_id, year, month, status (draft/approved/closed), method, sessions_held/attended/absent/unreported/cancelled, price_per_session, base_amount, adjustments_total, custom_amount, amount, warnings (JSON), detail (JSON – פירוט מפגשים וכלל החיוב) | תמונת מצב; ייחודי ל(ילד, שנה, חודש) |
| `adjustments` | child_id, year, month, amount (+/-), reason, session_id | זיכויים והתאמות מאושרות |
| `payment_messages` | charge_id, recipient_name, recipient_phone, body, status (draft/approved/sent), sent_at, sent_by | אחת לכל חיוב – מונע שליחה כפולה |

### תשלומים וקבלות
| טבלה | שדות | הערות |
|---|---|---|
| `payments` | child_id (ריק = טרם שויך), paid_on, amount, method, payer_name, reference, bank_details, notes, attachment_path, source (manual/screenshot), verified, extracted (JSON) | פרטי בנק ואסמכתאות – למורשים בלבד |
| `payment_allocations` | payment_id, charge_id, amount | תשלום חלקי, כמה חודשים, כמה ילדים |
| `receipts` | idempotency_key (ייחודי), kind (monthly/per_session/intro), status (draft/approved/issued/sent/failed/cancelled), child_id, payment_id, session_id, charge_id, amount, payer_name, email, description, notes, data (JSON – כל הנתונים כפי שיישלחו), missing_fields, provider, external_id, receipt_number, pdf_url, error, approved_by/at, issued_at, sent_at | |
| `intro_sessions` | child_id, session_id, amount, payment_id, notes | מסלול נפרד למפגש היכרות |

### מערכת
| טבלה | שדות | הערות |
|---|---|---|
| `users` | username, display_name, password_hash (PBKDF2-SHA256), role (admin/manager/operator), is_active | |
| `settings` | key, value | תבניות, מדיניות ביטול, מחירי ברירת מחדל |
| `audit_log` | at, user, entity, entity_id, action, before (JSON), after (JSON), note | |
| `month_closures` | year, month, closed_at, closed_by, reopened_at, notes | |

## מפתחות אידמפוטנטיות לקבלות
* חודשית: `pay{payment_id}-charge{charge_id}-monthly`
* למפגש: `pay{payment_id}-charge{charge_id}-session{session_id}`
* היכרות: `pay{payment_id}-intro{intro_id}`

המפתח נשלח גם לספק (Idempotency-Key), כך שגם כשל תקשורת וניסיון חוזר לא יפיקו קבלה כפולה.
