# WhatsApp Group Invitations — Community Buying

Status: **implemented**. It uses the free WhatsApp share link (`https://wa.me/?text=…`),
which opens WhatsApp with a pre-filled message that the person sends themselves.
No WhatsApp Business API, no automated or paid messaging, and no credentials.
Automated Business messages would need Meta approval, credentials and the owner's
sign-off on cost; they are **not** built.

## Flow

1. A signed-in customer opens a group buy and presses **Invite**. The frontend calls
   `POST /api/v1/community-buying/campaigns/{id}/invites`.
2. The server checks that the campaign is OPEN and not past its end, and that the customer
   has fewer than 10 active invites for it (otherwise `429 TOO_MANY_INVITES`). It then
   creates a random token (`secrets.token_urlsafe(24)`, 192 bits) and stores **only its
   SHA-256 hash** in `group_buy_invites`. Expiry is the earlier of **72 hours** and the
   campaign end.
3. The response returns the token once, the link `<site>/community-buying/invite/<token>`,
   the expiry, the message, and `whatsapp_url` / `sms_url`.
4. The recipient opens the link: page `/community-buying/invite/[token]` →
   `GET /api/v1/community-buying/invites/{token}` (public, no sign-in needed to view).
5. **Join group buy** → `POST /api/v1/community-buying/invites/{token}/join`. This needs a
   signed-in customer (signed-out visitors get a sign-in link that returns to the invite).
   The token is validated again, then the normal join runs with every rule it already
   has: OPEN, not full, per-member quantity, one membership per customer, and the retailer
   can't join their own campaign. `uses` is incremented.

`<site>` is the address the person is sharing from (the request's `Origin`, e.g. the
LAN address or the Cloudflare tunnel in the shared demo) when it is a plain
`http(s)://host[:port]`. Otherwise it is `FRONTEND_BASE_URL`.

## Message content

Example:

> Join the BASKET group buy 'Kettle group buy' (Pigeon Stainless Steel Electric Kettle 1.5L):
> ₹849.00 instead of ₹999.00. 1 of 3 joined, 2 more needed. Invite valid until
> 24 Nov 2026, 10:15 PM IST. http://10.115.28.176:3100/community-buying/invite/Xy…

- Prices, progress and product are read from the campaign on the server when the invite
  is created (verified price, not typed by the user).
- **No private data:** no name, phone, email, address, PIN, or user/customer id. The old
  share link appended `ref=<first 8 characters of the user id>`; that is removed.
- The invite preview API returns campaign facts only and never identifies who sent it.

## Validation and errors

| Case | Result |
|---|---|
| Unknown or altered token | `404 INVITE_INVALID` |
| Invite past its expiry (or revoked) | `410 INVITE_EXPIRED` |
| Campaign closed, expired or full | Preview `can_join: false` with a reason; joining fails with the normal join error |
| Not signed in | `401` on join |
| Too many active invites by one customer for one campaign | `429 TOO_MANY_INVITES` |

The old `GET …/campaigns/{id}/share` still works for existing clients, but it now
creates a secure invite in the same way.

## Data

Table `group_buy_invites` (migration `0037_group_buy_invites`, with downgrade):

| Column | Meaning |
|---|---|
| `id` | Row id |
| `campaign_id` | FK, cascade, indexed |
| `created_by_user_id` | FK, set null, indexed; never exposed |
| `token_hash` | Unique |
| `expires_at` | Invite expiry |
| `uses` | Joins through this invite |
| `revoked_at` | Set if the invite is revoked |
| `created_at` | Creation time |

## Tests

`backend/tests/test_final_whatsapp_invites.py`:
- link and message contents, and no sender data;
- only the hash is stored;
- 404 for unknown or tampered tokens;
- sign-in required to join; a join works through the invite;
- an unsafe Origin falls back;
- an expired invite gives 410 on both preview and join;
- no invites for a closed campaign.

`test_p3_community_buying.py` was updated for the new link format.
