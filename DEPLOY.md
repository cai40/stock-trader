# Deploy Stock Trader UI

Your code is on `main` and ready to deploy. Pick one option:

## Option 1: Streamlit Community Cloud (recommended, free)

**If the app shows a text box instead of a dropdown**, it is on an old build. On your phone:

1. Open your app (`cai40.streamlit.app`)
2. Tap **Manage app** (bottom-right)
3. Tap **Reboot app**
4. Wait ~2 minutes, then refresh — you should see **v0.2.2** and **📋 Pick a stock / ETF**

**First-time deploy** — open in Safari while signed into GitHub:

**https://share.streamlit.io/deploy?repository=cai40/stock-trader&branch=main&mainModule=streamlit_app.py&subdomain=cai40**

1. Sign in with GitHub if prompted
2. Tap **Deploy**
3. Wait ~2 minutes for the build
4. Your URL: **https://cai40.streamlit.app**

## Option 2: Render (free tier)

**https://dashboard.render.com/blueprint/new?repo=https://github.com/cai40/stock-trader**

1. Sign in with GitHub
2. Tap **Apply** to create the service
3. Wait for deploy (~3 min)
4. Open the `.onrender.com` URL Render gives you

## Option 3: Temporary link (cloud agent session)

From a Cursor cloud terminal:

```bash
bash scripts/start-ui.sh
```

Prints a temporary `http://bore.pub:PORT` link (expires when the session ends).
