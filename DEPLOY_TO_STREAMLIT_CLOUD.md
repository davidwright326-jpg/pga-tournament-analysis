# Deploy PGA Tournament Analysis to Streamlit Cloud

## Prerequisites
- A GitHub account
- Your project pushed to a GitHub repository

## Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "PGA Tournament Analysis app"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

Make sure these files are in the repo under `backend/`:
- `streamlit_app.py` (the Streamlit dashboard)
- `app/` folder (all backend modules)
- `requirements.txt` (Python dependencies)
- `.streamlit/config.toml` (Streamlit theme/config)

## Step 2: Deploy on Streamlit Community Cloud

1. Go to **https://share.streamlit.io** and sign in with GitHub
2. Click **"New app"**
3. Fill in the form:
   - **Repository:** `YOUR_USERNAME/YOUR_REPO_NAME`
   - **Branch:** `main`
   - **Main file path:** `backend/streamlit_app.py`
4. Click **Deploy**

## Step 3: Wait for first load

- Streamlit Cloud will install dependencies and launch the app
- On first load, the app auto-detects an empty database and triggers a data refresh
- This takes about 1-2 minutes — reload the page after that
- You'll get a public URL like `https://your-app-name.streamlit.app`

## Notes

- **Free tier** sleeps after inactivity; first load after idle takes ~30 seconds
- **SQLite data is ephemeral** on Streamlit Cloud — resets on redeploy. The app auto-bootstraps by re-fetching data when the DB is empty
- For persistent data, swap SQLite for a cloud database (Supabase, Turso, etc.)
- To update the app, just push to GitHub — Streamlit Cloud auto-redeploys
