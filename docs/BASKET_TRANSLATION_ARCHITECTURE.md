# Basket — Translation Architecture and Coverage (D1)

**Status: PARTIAL.** The architecture is in place and working for 12 languages. Coverage is
measured, and is **below the D1 targets** (≥ 95 % on checkout/orders, ≥ 90 % overall).
This cycle did not reach them; see "Why the target was not reached" below.

## How translation works

| Layer | Where | Behaviour |
|---|---|---|
| Languages | `frontend/lib/i18n/languages.ts` | en, hi, kn, ta, te, ml, bn, mr, gu, pa, or, ur (Urdu `dir: rtl`) |
| Dictionaries | `frontend/locales/<code>.json` | Flat `key → text` with `{name}` placeholders |
| Required keys | `frontend/locales/core-keys.json` (290 keys) | Every language must have them; enforced by `lib/i18n/i18n.test.ts` |
| Lookup | `translate()` / `t()` / `tActive()` in `lib/i18n` | Language → English → key; placeholders substituted |
| Choice | `I18nProvider` | Cookie, then `localStorage`; for signed-in users also saved on the account (`/api/v1/i18n/preference`) |
| Formatting | `lib/i18n/format.ts` | Money, dates and numbers in the language's Indian locale |
| Errors | `lib/i18n/errors.ts` | Stable API error codes map to translated messages; codes are never translated |
| Catalogue data | backend `modules/i18n` | `/api/v1/i18n/translations` for category and product names; `/normalize` maps Indic or Hinglish search terms (e.g. "atta" → "atta flour") |

Rules for adding text: put the English string in `en.json` under an area prefix
(`checkout.*`, `orders.*` …) and call `t("key")` in the component. Never translate API
error codes, prices or identifiers. Machine-produced translations must be marked
for native review before release.

## Measured coverage (21 Nov 2026)

Run `scripts/i18n-coverage.py`. The script counts `t()` calls against visible strings
still hard-coded in JSX: text nodes and `placeholder`, `title`, `aria-label` and `alt` literals.

| Measure | Value |
|---|---|
| English keys | 633 |
| Keys present in each of the 11 other languages | 290 of 633 (**45.8 %**; all of `core-keys`) |
| UI wired through `t()` — shell (header, home, login, register) | **88.5 %** |
| admin | 45.5 % |
| marketplace features | 36.4 % |
| retailer portal | 27.8 % |
| account | 11.2 % |
| catalogue | 5.9 % |
| **checkout / cart** | **2.2 %** (target 95 %) |
| **orders** | **0 %** (target 95 %) |
| **overall** | **34.2 %** (target 90 %) |

`scripts/i18n-coverage.py --list checkout` prints every remaining string with its file.

## Why the target was not reached
Reaching it means moving about 1,150 hard-coded strings into keys, then writing about
16,000 translations (1,150 + 343 missing keys × 11 languages). Doing that at speed would
give unreviewed machine text on checkout and payment screens, where wrong wording costs
money. This cycle prioritised the functional items, live sync, the Kafka fixes and the
test gate. D1 stays open.

## Plan to finish D1 (in this order)
1. **Checkout and cart** (87 strings), then **orders** (110): extract to `checkout.*` /
   `orders.*`, add to `core-keys.json`, and translate all 11 languages with native review.
   This reaches the 95 % target for those areas.
2. **Account and catalogue** (≈ 255 strings).
3. **Retailer, marketplace, admin** (≈ 670 strings). This takes overall past 90 %.
4. Add a CI check that fails if `checkout`/`orders` wiring drops below 95 % or a
   `core-keys` entry is missing in any language.
5. Screenshot diff in English must stay zero: extraction changes no markup or styles.
