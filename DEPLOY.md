# Deploy Stock Trader UI

## "You do not have access to this app"

This means the app URL (e.g. `cai40-stock-trader.streamlit.app`) was created under a **different Streamlit login** — usually the Cursor agent — **not** your `cai40@yahoo.com` account. You cannot open **Manage app** on URLs you do not own.

**Do not keep trying old URLs.** Deploy a **brand-new** app under your account (below).

---

## Step 1: Link GitHub to your Streamlit account (one time)

On your iPhone in **Safari**:

1. Open **https://share.streamlit.io**
2. Sign in with the email you use: **cai40@yahoo.com**
3. Tap your profile → **Settings** (or **Account**)
4. Under **Source control**, connect **GitHub** account **`cai40`**
5. Grant access to the **`cai40/stock-trader`** repository

If GitHub is already connected to a different Streamlit account, sign out of Streamlit and sign back in with **cai40@yahoo.com**, then reconnect GitHub.

---

## Step 2: Deploy a NEW app (do not reuse old subdomains)

Open this deploy link:

**https://share.streamlit.io/deploy?repository=cai40/stock-trader&branch=main&mainModule=streamlit_app.py**

Fill the form:

| Field | Value |
|-------|-------|
| Repository | `cai40/stock-trader` |
| Branch | `main` |
| Main file | `streamlit_app.py` |
| App URL | **Pick a NEW name** — see below |

### Subdomain ideas (use one that is not taken)

- `cai40-trader-v3`
- `cai40-stocks-jul`
- `my-cai40-trader`
- `cai40-paper-trade`

**Avoid:** `cai40`, `cai40-stock-trader`, `stock-trader-cai40` — these may already belong to the agent account.

Tap **Deploy** → wait 3 minutes → open **your new** `https://YOUR-NAME.streamlit.app` URL.

### You should see

- **v0.4.0** under the title
- **📋 Pick a stock / ETF** dropdown
- Tabs: Quote · Backtest · **Compare** · Paper trade

---

## Option 2: Render (recommended — you own the URL)

**https://dashboard.render.com/blueprint/new?repo=https://github.com/cai40/stock-trader**

1. Sign in with **GitHub** (`cai40`)
2. Tap **Apply**
3. Use the `.onrender.com` URL Render gives you (you own it)

### Render not updating after a git push?

Render does **not** always redeploy automatically. After changes land on `main`:

1. Open **https://dashboard.render.com** → service **stock-trader**
2. Tap **Manual Deploy** → **Clear build cache & deploy**
3. Wait ~3 minutes, then hard-refresh the app URL
4. Confirm the header shows **v0.3.6** (and a short git commit hash on Render)

If the version is still old, open **Settings** → ensure **Auto-Deploy** is **On** and branch is **main**.

---

## Streamlit settings reference

| Setting | Value |
|---------|-------|
| Repository | `cai40/stock-trader` |
| Branch | `main` |
| Main file | `streamlit_app.py` |
