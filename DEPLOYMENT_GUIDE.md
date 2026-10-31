# Deploy OptiRoute from GitHub

This guide describes a Render deployment for a college demo. The frontend is a static site. Use an always-on paid Python web service with a persistent disk for the backend; a free backend sleeps and does not retain local SQLite data across restarts.

## 1. Push a clean repository

From the `optiroute/` folder, run `git add .`, inspect `git status`, commit, then push to an empty GitHub repository. The root `.gitignore` excludes local `.env` files, `backend/data/`, virtual environments, build output, PDF/DOCX reports, and ZIP archives. Never force-add provider keys, `frontend/.env`, `backend/.env`, or the SQLite database.

## 2. Backend web service

Connect the GitHub repository in Render and create a Python web service. Set Root Directory to `backend`. Use Python 3.12.14 (`backend/.python-version`). Build command:

```sh
python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu && python -m pip install -r requirements.txt
```

Start command:

```sh
python -m uvicorn optiroute.main:app --host 0.0.0.0 --port $PORT
```

Set the health check path to `/health`. Choose an always-on paid instance with enough memory for PyTorch and sentence-transformers. Attach a persistent disk mounted at `/var/data`. Set these backend environment variables:

- `FIREBASE_PROJECT_ID`: the project ID used by the frontend.
- `WORKFLOW_ENCRYPTION_KEY`: a Fernet key generated once and retained across deployments.
- `OPTIROUTE_DATA_DIR`: `/var/data`.
- `HF_HOME`: `/var/data/hf`.
- `SENTENCE_TRANSFORMERS_HOME`: `/var/data/hf`.

Generate a Fernet key locally with:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set it in Render's secret environment variables. Deploy at least a day before the demo and run a test prompt to download and cache the semantic model.

## 3. Frontend static site

Create a Render Static Site from the same repository. Set Root Directory to `frontend`, build command to `npm ci && npm run build`, and publish directory to `dist`. Set the four `VITE_FIREBASE_*` values from `frontend/.env.example` and set `VITE_API_BASE_URL` to the backend's public HTTPS origin without a trailing slash. Set these before building; Vite embeds them into the browser bundle.

Add a rewrite rule with source `/*`, destination `/index.html`, action `Rewrite`, so React Router pages load directly.

## 4. Firebase

In Firebase Authentication, enable Email/Password and Google sign-in. Add the frontend Render hostname to Authorized domains. Add any future custom domain there too.

## 5. Rehearse

1. Open backend `/health` and the frontend URL.
2. Sign in with the demo account.
3. Connect and test the intended provider models and keys.
4. Test a short prompt, a long prompt, a heavier retry, cache, dashboard, and chat deletion.
5. Restart the backend and confirm chats and model connections remain. This verifies the disk and encryption key.
6. Keep a copy of presentation prompts and a fallback screenshot or recording; external model APIs can still fail.

The current per-model deadline is 90 seconds and the whole-prompt deadline is 180 seconds. The repository does not include local chats or cache entries.
