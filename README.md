# Legal Contract Intelligence Platform

AI-powered legal contract analysis platform using Google Gemini, LlamaParse, LangGraph, ChromaDB, and Neo4j.

## Tech Stack

- **AI Models**: Google Gemini 2.5/3.0 (multi-model cost optimization)
- **Document Parsing**: LlamaParse v0.6.88
- **Agent Orchestration**: LangGraph v1.0.3
- **Vector Storage**: ChromaDB
- **Graph Database**: Neo4j
- **Backend**: FastAPI
- **Frontend**: Next.js

## Quick Start

```bash
# 1. Clone and setup
cd ps-demo

# 2. Copy environment file
cp .env.example .env
# Edit .env with your API keys

# 3. Start infrastructure
docker-compose up -d

# 4. Setup backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# 5. Setup frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Access

- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- Neo4j Browser: http://localhost:7474

## Project Structure

```
ps-demo/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── agents/                 # LangGraph agents
│   ├── services/               # Core services
│   ├── models/                 # Pydantic schemas
│   └── workflows/              # LangGraph workflows
├── frontend/
│   ├── app/                    # Next.js app router
│   └── components/             # React components
├── docs/                       # Documentation & workplans
├── docker-compose.yml          # Neo4j + Redis
└── .env.example                # Environment template
```

## Workplan Parts

See `docs/` for parallelizable implementation parts:
- `2-workplan-part1.md` - Infrastructure & Core Services
- `2-workplan-part2.md` - LangGraph Workflow & Agents
- `2-workplan-part3.md` - FastAPI Backend
- `2-workplan-part4.md` - Next.js Frontend
