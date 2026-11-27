# BASKET — Version 2.0 Documented Technical & Functional Limitations

To ensure absolute transparency for product, engineering, and design stakeholders, this document details all known limitations, partial implementations, and dependencies requiring external configuration or approval.

---

## 1. Multilingual Coverage (Bharat i18n)

- **Current Status:** Partially Completed (~34.2% UI wiring, ~45.8% dictionary keys).
- **Supported Languages:** English, Hindi, Kannada, Tamil, Telugu, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Odia, Urdu.
- **Limitation:** While core navigation, header, auth, and common catalog labels are fully localized, deep checkout steps (approx 2% coverage) and order tracking history (approx 0% coverage) remain largely in English.
- **Target for Next Iteration:** Expand coverage to 95% dictionary translation and 90% UI wiring.

---

## 2. Payments & Razorpay Integration

- **Dual Mode (Test Mode vs Live Mode):** Configured strictly for Razorpay Test Mode with `rzp_test_*` credentials.
- **Recurring AutoPay (Mandates):** The database schema (`0038_recurring_baskets`) and backend scheduling logic support recurring basket generation. However, automated bank-debit recurring mandates require active Razorpay Subscriptions / UPI Autopay bank onboarding and product business policy sign-off.
- **Customer Self-Refunds:** By design, customers cannot self-issue instant payment refunds via the API. Refunds must be initiated by an Admin or through the formal return/exchange review workflow to prevent fraud.

---

## 3. Asynchronous Streaming & Infrastructure Modes

- **Direct Outbox Dispatch vs Kafka:** In local development and single-instance deployments, `OUTBOX_DISPATCH=direct` is the verified and recommended operational mode. While Kafka event contracts and consumer loops are fully implemented in code, running multi-node Kafka requires a provisioned Kafka cluster with valid SASL/SSL credentials.
- **OpenSearch Multi-Tenancy:** The search engine defaults to PostgreSQL full-text search fallback whenever an OpenSearch cluster is unconfigured or its index is unbuilt. This fallback is completely seamless and functional, but does not provide advanced fuzzy typo-tolerance.

---

## 4. External AI & Media Storage Dependencies

- **LLM-Powered Negotiator:** The AI Negotiator functions using comprehensive deterministic retailer concession rules (minimum profit margins, floor prices, round-by-round concessions). An external LLM reasoning layer requires a cloud LLM provider API key and token cost cap policy.
- **OCR List Upload:** Shopping list image uploads use a structured rule-based parser. High-fidelity handwriting and multi-lingual receipt OCR requires an external cloud Vision API key.
- **Media / Image Uploads:** Product and KYC document uploads currently store files on the local filesystem. Production deployment requires S3-compatible cloud object storage configuration (AWS S3, Cloudflare R2).

---

## 5. Multi-Device & Hardware Field Verification

- **Real-Time Portals:** Verified via multiple independent browser windows and simulated concurrent clients over SSE. Physical two-device cross-network latency verification is recommended prior to broad field launch.
- **Thermal Receipt Printing:** Order fulfillment supports web invoice viewing; ESC/POS hardware receipt printer driver integration is slated for future retail store hardware bundles.
