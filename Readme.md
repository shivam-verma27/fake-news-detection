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
