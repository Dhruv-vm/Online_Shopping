# BASKET — External Configuration Guide

> Branch `feature/marketplace-completion` · 2026-11-21
> Every value below is read from environment variables (`backend/.env`, `frontend/.env.local`).
> **Never commit real values.** Both files are git-ignored; `backend/.env.example` and
> `frontend/.env.example` hold placeholders only. Restart the API after changing `backend/.env`.

Check the live status of every integration at **Admin → System health** (`GET /api/v1/admin/system/health`).

---

## 1. Razorpay (payments) — test mode

The code ships with *mock* defaults (`rzp_test_basket_mock_key_id`). With them, checkout works up to
the "Pay" button, but Razorpay's hosted window cannot complete a payment, and System health reports
**"No real Razorpay keys (mock key only)"**.

1. Sign in to the Razorpay Dashboard, switch the toggle to **Test Mode**.
2. **Account & Settings → API Keys → Generate Test Key.** You get a Key ID (`rzp_test_…`) and a Key Secret (shown once).
3. In `backend/.env`:
   ```
   RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
   RAZORPAY_KEY_SECRET=<key secret>
   ```
   The frontend needs **no** Razorpay variable: the API returns the public key ID in the
   payment-initiation response, and the secret never leaves the server.
4. Webhooks (needed so payments confirmed outside the browser — e.g. the shopper closes the tab — still settle):
   - Dashboard → **Webhooks → Add New Webhook**
   - URL: `https://<public-api-host>/api/v1/payments/webhook`
     (for local testing expose port 8000 with a tunnel such as `cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`)
   - Events: `payment.captured`, `order.paid`, `payment.failed`, `refund.processed`, `refund.failed`
   - Secret: any strong random string, then set `RAZORPAY_WEBHOOK_SECRET=<same string>` in `backend/.env`
5. Restart the API. System health should show **Razorpay: test mode**.
6. Test a payment with Razorpay's documented test cards / UPI IDs (see Razorpay docs → *Test card details*).
   The order must move to `CONFIRMED / SUCCEEDED` and appear as a paid order in retailer analytics.

Live mode: repeat with Live keys (`rzp_live_…`) only after KYC, and set `COOKIE_SECURE=true`.

## 2. OCR provider (List to Basket photo reading)

Not configured by default. The page then hides photo upload and labels itself **Manual entry**; the API
returns `OCR_PROVIDER_UNAVAILABLE` for images. BASKET talks to OCR through a small HTTP contract, so any
service (Google Cloud Vision, Azure AI Vision, AWS Textract, a self-hosted model) can be used **behind a
thin adapter you deploy**:

```
OCR_PROVIDER=http
OCR_PROVIDER_URL=https://<your-adapter>/v1/extract
OCR_PROVIDER_API_KEY=<secret>        # sent as "Authorization: Bearer <secret>"
```

Contract the adapter must implement:

| Direction | Body |
| --- | --- |
| Request (POST JSON) | `{"image_base64": "...", "content_type": "image/jpeg", "languages": ["en","hi","ta","te","kn","bn","mr","gu"]}` |
| Response 200 (JSON) | `{"text": "1kg atta\n500g butter", "confidence": 0.87, "lines": [{"text": "1kg atta", "confidence": 0.91}]}` |

`text` is required; `confidence` and per-line `confidence` (0–1) are optional and, when present, are shown
to the shopper (low-confidence lines are flagged "please check"). Any non-200 or missing `text` becomes
`OCR_PROVIDER_ERROR` (502). **This adapter path has not been verified against a live OCR service.**

## 3. AI provider (Deal Assistant / Negotiator)

**There is no AI-provider integration in the code.** The Deal Assistant (`POST /api/v1/assistant/chat`) and
the AI Negotiator are deterministic rule engines over live catalogue data; responses carry
`mode: "rule_based"` and `ai_provider_configured: false`, and the UI says so. No environment variable
turns on an LLM. Adding one requires code: a provider client behind the existing assistant service, prompt
and safety design, and tests — tracked in `DISCREPANCY_REGISTER.md` (MC-07).

## 4. Image and document storage

| Variable | Default | Meaning |
| --- | --- | --- |
| `MEDIA_STORAGE` | `local` | `local` = files on the API server's disk; `none` = uploads disabled (API answers 503 `MEDIA_STORAGE_UNAVAILABLE`) |
| `MEDIA_ROOT` | `backend/media` | Public images (product and listing photos), served at `/media` |
| `MEDIA_PRIVATE_ROOT` | `backend/media_private` | Retailer verification documents — never public; admins download through an authenticated endpoint |
| `MEDIA_PUBLIC_BASE_URL` | `http://localhost:8000/media` | Absolute URL prefix stored on uploaded images; set to your public API host |
| `MEDIA_MAX_BYTES` | `5242880` (5 MB) | Upload limit; type and file signature are also checked |

`local` suits development and a single server. **S3-compatible object storage is not implemented**; for
multiple API instances or production, an object-storage backend must be added to
`app/modules/media/storage.py` (tracked as MC-06). Back up `MEDIA_PRIVATE_ROOT` — it holds KYC documents.

## 5. Other services

| Service | Variables | Without it |
| --- | --- | --- |
| Kafka (event streaming) | `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SASL_MECHANISM`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `KAFKA_SSL_CA_LOCATION` | Events stay in the PostgreSQL outbox. The previously configured Aiven broker hostname no longer resolves. |
| OpenSearch (search) | `OPENSEARCH_URL`, `OPENSEARCH_USERNAME`, `OPENSEARCH_PASSWORD`, `OPENSEARCH_INDEX_PREFIX` | PostgreSQL full-text search fallback. **The index belongs to one database:** the repo-root `.env` points at a shared index built from `basket_db`, so start an API that uses any other database with `OPENSEARCH_URL=""` or its own `OPENSEARCH_INDEX_PREFIX` (DISCREPANCY_REGISTER MC-12). |
| Internal jobs | `INTERNAL_SERVICE_KEY` | Internal cron/worker endpoints refuse calls |
| Security (required in any shared environment) | `SECRET_KEY`, `JWT_SECRET_KEY`, `CSRF_SECRET_KEY` (long random values), `COOKIE_SECURE=true` behind HTTPS, `CORS_ORIGINS`, `FRONTEND_BASE_URL` | Development defaults are unsafe outside a laptop |
| Frontend | `NEXT_PUBLIC_API_URL` (`frontend/.env.local`) | Defaults to `http://localhost:8000` |
| Email / SMS | — | Not implemented; notifications are in-app only |

## 6. Databases

| Database | Purpose |
| --- | --- |
| `basket_db` | Your development database. **Still at revision 0033** — run `cd backend && .venv/bin/alembic upgrade head` to add 0034 (indexes only). |
| `basket_demo` | Demonstration data (`@basket.demo` accounts, password `Basket@123`); at head `0034`. Reset with `scripts/reset-demo-db.sh`. |
| `basket_db_test` | Created and migrated automatically by the test suite. |
| `*_verify` | Created and dropped by `scripts/verify-migrations.sh`. |
