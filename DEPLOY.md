# Deploy Stock Trader UI

Your code is on `main` and ready to deploy.

## "You do not have access to this app"

This means the old app (`cai40.streamlit.app`) was created under a **different Streamlit account** (e.g. the Cursor agent), not your `cai40@yahoo.com` login. You cannot reboot or manage it.

**Fix: deploy a fresh app under your account** (steps below). Do not try to open the old URL.

---

## Option 1: Streamlit Community Cloud (recommended, free)

On your iPhone in **Safari**:

1. Open this link (signed into GitHub as **cai40**):

   **https://share.streamlit.io/deploy?repository=cai40/stock-trader&branch=main&mainModule=streamlit_app.py**

2. Sign in with **GitHub** (`cai40`) if asked — use the same account that owns the repo
3. Pick a subdomain, e.g. `stock-trader-cai40` (avoid `cai40` if it is taken by the old app)
4. Tap **Deploy**
5. Wait 2–3 minutes

Your new URL will look like: **https://stock-trader-cai40.streamlit.app**

You should see **v0.2.3** and **📋 Pick a stock / ETF** dropdown (VGT, SPY, TEL, etc.).

---

## Option 2: Render (free tier, good backup)

**https://dashboard.render.com/blueprint/new?repo=https://github.com/cai40/stock-trader**

1. Sign in with **GitHub** (`cai40`)
2. Tap **Apply**
3. Wait ~3 minutes
4. Open the `.onrender.com` URL Render gives you

---

## Option 3: Temporary link (works now, expires later)

**http://bore.pub:15196**

Works while the cloud agent session is active. Includes the stock dropdown.

---

## Streamlit settings (for Option 1)

| Setting | Value |
|---------|-------|
| Repository | `cai40/stock-trader` |
| Branch | `main` |
| Main file | `streamlit_app.py` |
| Python | 3.12 |
