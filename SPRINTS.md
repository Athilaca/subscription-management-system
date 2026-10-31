# Brightloop — Sprint Plan

Six sprints deliver the complete Brightloop subscription management system. Each sprint ends
with a working, demo-able increment (Definition of Done: migrations clean, `docker compose up`
green, tests for that sprint's logic passing, demoable in the browser).

| Sprint | Theme | Demo at sprint end |
|---|---|---|
| 1 | Foundation & Access | Sign up / log in / reset password; admin creates staff; Docker stack boots |
| 2 | Catalog | Admin adds products with variants ("Odoo" +560), plans (daily→yearly + flags), tax rules |
| 3 | Quotations & Subscriptions | Rep starts from a template, walks Draft→Quotation→Confirmed→Active→Closed; pause/renew guarded by plan flags |
| 4 | Discounts & Automated Invoicing | Billing run generates invoices with tax + discount lines; running it twice creates nothing |
| 5 | Payments & Dashboard | Payment flips invoice to Paid; dashboard shows revenue / outstanding / overdue with filters |
| 6 | Automation, Hardening & Release | Celery beat bills daily on its own; seed data; full test matrix green; README |

---

## Sprint 1 — Foundation & Access

**Goal:** Dockerized Django skeleton on PostgreSQL with a custom email-login user model,
three roles, password policy, and auth flows. *The custom user model MUST land before the
first migration.*

- **S1.1 Scaffold + Docker** — Dockerfile, docker-compose.yml (`web`, `db`, `redis`, `worker`,
  `beat` with healthchecks & named volumes), `.env.example`, settings split
  (`base`/`dev`/`prod`), requirements, `.gitattributes` (LF), `.gitignore`, `.dockerignore`.
- **S1.2 Custom user** — `accounts.User` (email = `USERNAME_FIELD`, unique, `role`:
  admin/staff/customer), superuser forces admin role; first migration.
- **S1.3 Password policy** — validator: >8 chars + uppercase + lowercase + special character;
  wired into `AUTH_PASSWORD_VALIDATORS` (covers signup, admin, and reset forms).
- **S1.4 Auth flows** — login/logout, customer signup, emailed password reset (console
  backend in dev).
- **S1.5 Roles & staff management** — `RoleRequiredMixin` family
  (Admin/Staff/Customer); admin-only staff account creation.
- **S1.6 Base templates** — `base.html` with role-aware nav, login/signup/reset templates,
  placeholder home page (replaced by the dashboard in Sprint 5).

## Sprint 2 — Catalog (Products, Variants, Plans, Taxes)

- **S2.1 Product & variants** — CRUD; variant `price_adjustment` (the "Odoo" +560 case).
- **S2.2 Plans** — price, billing period (daily/weekly/monthly/yearly), min quantity,
  availability window, flags (auto_close_on_end / allow_close_early / allow_pause /
  allow_renewal), admin decides per plan.
- **S2.3 Tax rules** — rate + product-specific vs global + priority; effective-rate service
  (specific beats general); snapshot at line creation.
- **S2.4 Pricing service** — `compute_unit_price(product, variants)`; unit tests.

## Sprint 3 — Quotations & Subscriptions

- **S3.1 Quotation templates** — template + lines (plan/product), validity days; "start from
  template" copies into a Draft subscription.
- **S3.2 Subscription & lines** — own number (`SUB-000123` via locked sequence), customer,
  plan, dates, payment terms, lines with snapshot unit price / tax rate / amount.
- **S3.3 State machine** — Draft→Quotation→Confirmed→Active→(Paused|Closed), guards from plan
  flags; UI renders only legal transitions; renewal creates a new subscription.
- **S3.4 Back-office views** — staff list/detail/transition pages; customer portal read-only
  pages.

## Sprint 4 — Discounts & Automated Invoicing

- **S4.1 Discount rules** — admin-only CRUD: fixed/percentage, min purchase/quantity, date
  window, usage cap, whole-subscription or specific-product scope; link rules to
  subscriptions.
- **S4.2 Eligibility service** — window, limits, minimums; percentage vs fixed capped at
  subtotal; usage counted inside the billing transaction.
- **S4.3 Invoice models & totals** — Invoice/InvoiceLine with snapshot lines; discounts as
  separate negative lines; `UniqueConstraint(subscription, billing_period_key)`.
- **S4.4 Billing engine** — idempotent `run_billing` (row locks + re-check + unique
  constraint), period advancement with `relativedelta`, auto-close at expiry.
- **S4.5 Invoice workflow** — confirm / cancel / send-by-email / printable page; Draft →
  Confirmed → Paid.

## Sprint 5 — Payments & Dashboard

- **S5.1 Payments** — record method/amount/date/note against an invoice; full payment flips
  invoice to Paid in one transaction.
- **S5.2 Ledgers** — paid / outstanding / overdue views (overdue computed in SQL).
- **S5.3 Dashboard** — active subscriptions, revenue, outstanding, overdue via a single
  `aggregate()`; date/customer/status filters; indexed queries (<2s at thousands of rows).

## Sprint 6 — Automation, Hardening & Release

- **S6.1 Celery** — worker/beat wiring, beat schedule (billing 02:00, auto-close 02:30),
  timezone parity with Django.
- **S6.2 Seed command** — idempotent demo data + first billing run + payments; printed
  credentials.
- **S6.3 Test coverage pass** — password policy, role gating, pricing, tax priority, discount
  eligibility, billing idempotency (incl. month-end), transitions, payments, dashboard.
- **S6.4 Release** — prod settings hardening (gunicorn + whitenoise + SMTP), README with
  first-run workflow, performance pass (indexes + `explain` on dashboard queries).
