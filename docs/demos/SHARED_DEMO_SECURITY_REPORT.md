# Basket — Shared Demo Security Report

| Area | Control | Verified |
|---|---|---|
| Network exposure | Only Next.js :3100 listens on all interfaces. API 8100, Kafka 9094, OpenSearch 9201 and PostgreSQL bind to 127.0.0.1 | `nc` from the LAN IP: 8100, 9094 and 9201 refused |
| Database separation | `basket_shared_demo` only (the script requires `_demo`); `basket_db` untouched. Test runs refuse `basket_db` and `basket_shared_demo` | conftest guard; scripts |
| Authentication | HttpOnly `access_token` cookie, same-origin via the proxy | Sign-in from both laptops' origins |
| CSRF | Double-submit `XSRF-TOKEN` + `X-CSRF-Token` on every write; **Origin allow-list** limited to localhost:3100, the LAN address and the active tunnel URL (the check itself is unchanged) | A browser write from an unlisted origin is 403; LAN and tunnel writes are 200 |
| Live stream | Requires sign-in (401 anonymous); ids-only notices; role/ownership-based audience (an order notice reaches only its customer and its retailers) | `test_final_realtime.py` (privacy routing, 401) |
| Role separation | Customer → retailer endpoints 403; retailer → customer actions 403; another customer's or retailer's order → 404 | Two-client test, scenario 10 |
| Competitor privacy | Retailers see bid **prices** and their own position, never other stores' names | `test_final_dukaan_live.py` |
| Customer privacy | Retailer notices carry the PIN area only, never the customer's free text (an RFQ title with a phone number is not copied); outbox events reject `customer_id`/pincode | Tests |
| WhatsApp invites | Random 192-bit token, only the SHA-256 hash stored, expiry ≤ 72 h, no sender data in the message | `test_final_whatsapp_invites.py` |
| Caching | API responses `Cache-Control: private, no-store`, so no tunnel, proxy or browser cache of per-user data | `test_final_cache_headers.py` |
| Payments | The recurring basket never charges; no card data stored; autopay not enabled | Report + tests |
| Secrets | No secrets in the repository or logs (redaction from Phase C); the demo uses PLAINTEXT Kafka on localhost only | — |

## Residual risks (demo only)
- Plain HTTP on the LAN: anyone on the same Wi-Fi can observe traffic. Use a trusted network, or
  the HTTPS tunnel.
- A quick-tunnel URL is public while it runs. Anyone with the link sees the sign-in page; all
  accounts still need a password. Stop it with `down` after the demo.
- Demo passwords are shared (`Basket@123`). Never reuse these accounts outside the demo.
