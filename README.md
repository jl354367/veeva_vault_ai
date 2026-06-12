# Help Assistant

Get answers from Veeva documentation and best practices.

## Project Structure

```
help_assistant/
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
        ├── App.jsx
        ├── App.css
        ├── components/
        └── services/
```

## Setup

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env   # then fill in your API keys
uvicorn main:app --reload --port 8002
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
