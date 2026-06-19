# Connect Gmail — Google Cloud OAuth setup (for Mawrid email send/receive)

This sets up the **"Connect Gmail"** feature so Mawrid can, per user, **send** POs/outreach/dunning
through their own Gmail (lands in inbox, not Junk) and **read replies back** to auto-detect, thread
and comprehend them (arrival dates → tracking + PO history, MOQ, change requests).

No domain and no billing/card are required. Gmail API in **Testing** mode is free.

---

## 0. Prerequisite — 2-Step Verification (2FA)
Google Cloud requires 2FA on the account.
- Google Account → **Security** → **2-Step Verification** → turn on (add a phone number / Google prompt).
- This also unlocks **App Passwords** (the quick fallback to test email without OAuth).

## 1. Create a project (no billing)
- Go to **https://console.cloud.google.com/projectcreate**
- **Project name:** `Mawrid` · **Organization:** No organization → **Create** → select it.
- ⚠️ Ignore every "Start free / Try for free / $300 credits" banner — that's the paid trial and asks for a card. We don't need it.

## 2. Enable the Gmail API
- **APIs & Services → Library** → search **Gmail API** → **Enable**.

## 3. OAuth consent screen
- **APIs & Services → OAuth consent screen** (newer UI: **Google Auth Platform → Branding / Audience**).
- User type: **External** → **Create**.
- App name `Mawrid`, support email = yours, developer contact = yours → **Save and continue**.
- **Scopes** → **Add or remove scopes** → add these two, then **Update**:
  - `https://www.googleapis.com/auth/gmail.send`
  - `https://www.googleapis.com/auth/gmail.readonly`
- **Test users** → **Add users** → add every Gmail you'll test with, e.g.
  - `mansourmohamadeljawad113@gmail.com`
  - `mansourmohamadeljawad118@gmail.com`
  - `mansourmohamadeljawad313@gmail.com`
- Leave **Publishing status = Testing** (no Google review needed this way).

## 4. Create the OAuth client
- **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
- Application type: **Web application**, name `Mawrid Web`.
- **Authorized redirect URIs → Add URI**:
  - Dev:  `http://localhost:8000/auth/google/callback`
  - Prod (later): `https://YOUR_DEPLOYED_HOST/auth/google/callback`
- **Create**.

## 5. Copy the credentials
A popup shows **Client ID** and **Client Secret** (re-openable under Credentials any time):
```
Client ID:     ...apps.googleusercontent.com
Client Secret: GOCSPX-...
```

## 6. Where the credentials go (developer side)
Seeded into Vault (gitignored, never committed):
```
secret/mawrid/google → { client_id, client_secret }
```
Per-user Gmail **refresh tokens** (obtained at "Connect Gmail") are stored per-tenant
(Vault or DB), never in git.

---

## How it works once wired
1. User clicks **Connect Gmail** (Settings / after signup) → Google consent → backend
   `/auth/google/callback` exchanges the code → stores the refresh token for that tenant.
2. Outbound PO/outreach/dunning is **sent via Gmail API** as the user → Google DKIM →
   inbox, not Junk.
3. A poller (every few minutes) reads new replies via the **Gmail API**, matches them to
   the supplier/PO, and runs the comprehension pipeline (arrival date → shipment tracking +
   PO history; MOQ; change-requested → edit & resend).

## Caveats (Testing mode)
- Refresh tokens for an **unverified** app in *Testing* expire after **7 days** → click
  **Connect Gmail** again ~weekly. Fine for the capstone/demo.
- Only the **test users** you added can connect until the app is verified.
- For a real public launch: submit the app for **Google OAuth verification** (needs a privacy
  policy + a verified domain) to make tokens permanent and allow any user.

## Quick fallback to test today (no OAuth)
- Google Account → Security → **App passwords** → create one for "Mail".
- Seed it: `secret/mawrid/imap → { host: imap.gmail.com, user, password }`.
- Mawrid's IMAP poller (already built) reads your inbox and auto-detects replies — your
  account only, but works in ~2 minutes.
