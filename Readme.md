# Fake News Detector (local, TF-IDF baseline)

## Setup

1. Create venv and install:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Install frontend deps:
   ```bash
   cd frontend
   npm install
   ```

## Run (one command on Windows)

From the project root:

```powershell
.\start-dev.ps1
```

This starts:
- Backend API: `http://127.0.0.1:8000`
- Frontend UI: `http://127.0.0.1:5173`
- URL fetch SSL verification is disabled for local development to avoid common Windows/dev-certificate issues.

Optional custom ports:

```powershell
.\start-dev.ps1 -ApiPort 8001 -FrontendPort 5174
```

To force strict SSL verification during local development:

```powershell
.\start-dev.ps1 -DisableUrlSslVerification $false
```

## Stop

```powershell
.\stop-dev.ps1
```

## Deploy with Docker

Build the container from the project root:

```powershell
docker build -t truthlens-app .
```

Run the container:

```powershell
docker run -p 8000:8000 truthlens-app
```

Then open the app at `http://127.0.0.1:8000/` if the frontend build is present.

If you need separate hosting for frontend and backend, build the frontend with `npm run build` in `frontend/` and deploy the `frontend/dist` folder to any static host, while hosting the backend on a Python-compatible service.

## Deploy on Vercel

1. Create a Vercel account and install the Vercel CLI if needed.
2. Ensure your project root contains `vercel.json` and `requirements.txt`.
3. Run from the project root:

```powershell
vercel --prod
```

The frontend will be served from the Vercel static build, and API endpoints will be available under `/api/predict` and `/api/predict_url`.
