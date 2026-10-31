# OptiRoute current project report

This source-based summary reflects the active project after the frontend/backend folder split. Older cyclomatic-complexity documents and deployment ZIPs are historical handoff artifacts, not runtime dependencies.

## Technology stack

| Layer | Technology | Active source |
| --- | --- | --- |
| Web app | React 19, Vite 8, React Router, Tailwind CSS | `frontend/package.json`, `frontend/src/App.jsx` |
| API | Python 3.12, FastAPI, Uvicorn | `backend/requirements.txt`, `backend/optiroute/main.py` |
| Authentication | Firebase Authentication; backend verifies Firebase ID tokens | `frontend/src/utils/firebase.js`, `backend/optiroute/auth.py` |
| Persistence | SQLite with asynchronous access through aiosqlite | `backend/optiroute/database.py` |
| Provider access | User-supplied API keys encrypted with Fernet; models organized by tier | `backend/optiroute/connections.py` |
| Routing | Workload evaluation, model ranking, tier selection, fallback, continuation | `backend/optiroute/engine/`, `backend/optiroute/proxy.py` |
| Cache | Exact and semantic matching scoped to each user | `backend/optiroute/engine/cache_manager.py` |
| Response display | Markdown, tables, and KaTeX equations | `frontend/src/components/ui/MarkdownRenderer.jsx` |
| Dashboard | Per-model and weekly tier request charts | `frontend/src/components/dashboard/` |

## Current user flow

A user signs in through Firebase, connects provider models on Routing Policies, and sends a prompt from the Playground. The backend checks the user's cache, evaluates the workload, chooses a tier and model, and records the answer, request data, and chat history. The user may request a heavier model for an answer, choose which answer to continue from, and select an answer for caching. Cache and chat deletion are linked where the current UI provides that action.

## Routes and data

The frontend includes Home, Login, Signup, Playground, Overview, Routing Policies, and Semantic Cache pages. The active API is `backend/optiroute/main.py`, with authentication and model-connection routes in separate modules. It serves chat completion and retry jobs, progress polling and cancellation, cache management, chat history, dashboard data, and a health endpoint. The backend creates `backend/data/optiroute.db` on startup by default. On deployment, set `OPTIROUTE_DATA_DIR` to a persistent mounted directory.

## Deployment needs

The frontend needs a public HTTPS API URL and Firebase web configuration at build time. The backend needs `FIREBASE_PROJECT_ID`, a stable `WORKFLOW_ENCRYPTION_KEY`, and persistent writable storage. Firebase Authentication must authorize the deployed frontend domain. Users must connect working provider API keys and models before generation works. See `DEPLOYMENT_GUIDE.md` for the deployment procedure and demo checks.
