# VaultBot Help Assistant

Veeva Vault help chatbot — keyword-based demo mode out of the box, Amazon Bedrock for production AI responses.

## Quick Start

Double-click **`start.bat`** — it starts the backend, waits for it to be ready, starts the frontend, then opens the browser automatically.

## Project Structure

```
help_assistant/
├── start.bat
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── data/
│   ├── routers/
│   └── services/
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
```

## Manual Setup

### Backend
```bash
cd backend
python -m pip install -r requirements.txt
copy .env.example .env   # fill in AWS credentials if using Bedrock
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## LLM Backend

Set `LLM_BACKEND` in `backend/.env`:
- `demo` — built-in keyword engine, no API key needed (default)
- `bedrock` — Amazon Bedrock (fill in AWS credentials in `.env`)
