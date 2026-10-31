# OptiRoute

OptiRoute is a React and FastAPI application that routes each signed-in user's prompt to one of their connected models in a light, mid, or heavy tier. It supports chat history, heavier-answer retries, semantic caching, and a request dashboard.

## Run locally

Requirements: Node.js 22.15.0 (see `frontend/.node-version`) and Python 3.12.14 (see `backend/.python-version`). Other compatible versions may work, but these are the versions used for this handoff.

1. Keep `frontend/.env` with the four `VITE_FIREBASE_*` values. For a fresh checkout, copy `frontend/.env.example` to `frontend/.env` and remove or replace its `VITE_API_BASE_URL` placeholder for localhost.
2. In `backend/`, copy `.env.example` to `.env` and replace `WORKFLOW_ENCRYPTION_KEY` with a persistent Fernet key. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
3. Start the API from `backend/`:

   ```sh
   python -m venv .venv
   python -m pip install -r requirements.txt
   python -m uvicorn optiroute.main:app --host 127.0.0.1 --port 8000
   ```

4. Start the frontend from `frontend/`:

   ```sh
   npm ci
   npm run dev
   ```

Open `http://127.0.0.1:5173`. The backend creates `backend/data/optiroute.db` automatically. Users add their own provider models and API keys on Routing Policies before sending prompts.

## Deploy

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for the recommended GitHub and Render setup. The frontend is a static Vite build; the backend is a long-running Python service with a persistent SQLite volume. A free backend that sleeps or discards local files is unsuitable for a reliable demo.

## Active code

- `frontend/src/`: React pages, components, styling, Firebase client, and API calls.
- `backend/optiroute/`: active FastAPI application, routing engine, cache, model connections, and database.
- `backend/config.yaml`: tier configuration.
- `backend/tests/`: development regression checks; not part of the deployed runtime.

Local `.env` files, the SQLite database, model weights, logs, virtual environments, build output, PDFs, DOCX files, and ZIP archives are excluded from Git. Do not commit API keys or Firebase Admin service account files.
