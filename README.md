# Agent Evaluator

A standalone full-stack agent evaluation application built with FastAPI, React, DeepEval, and SQLite. This directory has no runtime dependency on the AI Cowork core platform and is ready to become its own Git repository.

## Features

- DeepEval custom, agentic, RAG, multi-turn, and MCP metric catalog
- REST, WebSocket, Python package, manifest, OpenAI-compatible, framework, Azure OpenAI, and Microsoft Foundry onboarding
- CSV, JSONL, and XLSX evaluation datasets and downloadable templates
- Encrypted connector credentials
- Visual score dashboard and PDF report export
- Gemini or another supported LLM-as-a-judge provider

## Quick start on Windows

1. Copy `.env.example` to `.env` and add the judge-provider API key. The startup script creates the file automatically if it is missing.
2. Run `start.bat`.
3. Open `http://127.0.0.1:5173`.

The API runs at `http://127.0.0.1:8002`; interactive API documentation is available at `/docs`.

## Manual setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r ..\requirements.txt
uvicorn main:app --reload --port 8002
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

## Dataset requirements

Only `question` or `input` is universally required. Question plus `ground_truth` is enough for compatible reference metrics. RAG grounding metrics additionally need `retrieval_context`, tool metrics need their corresponding tool fields, and conversational metrics need `turns`.

Templates:

- `GET /api/datasets/template.csv`
- `GET /api/datasets/template.jsonl`
- `GET /api/datasets/template.xlsx`

## Tests and builds

```powershell
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests -v

cd ..\frontend
npm run build
```

## Create the new repository

```powershell
git init
git add .
git commit -m "Initial standalone agent evaluator"
git branch -M main
git remote add origin <your-new-repository-url>
git push -u origin main
```

Never commit `.env`, `backend/data`, uploaded agent packages, or generated credentials. They are already covered by `.gitignore`.
