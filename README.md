# Legal Contract Intelligence Platform

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14+](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI-powered legal contract analysis platform that uses multi-model AI routing to analyze contracts, extract risk factors, and enable natural language Q&A.

> **Purpose:** Interview demonstration / Proof of Concept for ProfitSolv

---

## ✨ Features

- **📄 Smart Document Parsing** - Legal-specific PDF parsing with LlamaParse
- **🤖 Multi-Model AI Routing** - Cost-optimized Gemini model selection (~82% savings)
- **⚠️ Risk Analysis** - Automated extraction of risk factors and concerns
- **💬 Natural Language Q&A** - Ask questions about your contracts
- **📊 Knowledge Graph** - Relationship mapping between contracts, companies, and clauses
- **💰 Cost Tracking** - Real-time API cost monitoring with 30-day retention

---

## 🛠 Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **AI Models** | Google Gemini 2.5/3.0 | Multi-model routing via GeminiRouter |
| **Document Parsing** | LlamaParse | Legal-specific PDF extraction |
| **Orchestration** | LangGraph | Stateful workflow management |
| **Vector Storage** | ChromaDB | Semantic search |
| **Graph Database** | FalkorDB | Redis-based, Cypher-compatible |
| **Backend** | FastAPI | Async Python API |
| **Frontend** | Next.js 14+ | App Router, TypeScript, Tailwind |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- API Keys: [Google AI Studio](https://aistudio.google.com/app/apikey), [LlamaCloud](https://cloud.llamaindex.ai/)

### Setup

```bash
# 1. Clone repository
git clone https://github.com/gregorydickson/ps-demo.git
cd ps-demo

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   GOOGLE_API_KEY=AIza...
#   LLAMA_CLOUD_API_KEY=llx-...

# 3. Start infrastructure (FalkorDB + Redis)
docker-compose up -d

# 4. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload

# 5. Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

### Access Points
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| FalkorDB UI | http://localhost:3001 |

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/contracts/upload` | Upload & analyze PDF |
| `POST` | `/api/contracts/{id}/query` | Q&A on contract |
| `GET` | `/api/contracts/{id}` | Get contract details |
| `GET` | `/api/analytics/costs` | Cost breakdown |
| `GET` | `/health` | Health check |

---

## 🧪 Testing

```bash
# Backend tests (120+ tests)
cd backend
pytest tests/ -v

# Integration tests with visual output
python scripts/run_integration_tests.py

# Frontend tests
cd frontend
npm test
```

---

## 📁 Project Structure

```
ps-demo/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── services/            # Core services (GeminiRouter, CostTracker, etc.)
│   ├── workflows/           # LangGraph workflows
│   ├── models/              # Pydantic schemas
│   └── tests/               # Unit & integration tests
├── frontend/
│   ├── src/app/             # Next.js pages
│   ├── src/components/      # React components
│   └── src/lib/             # API client
├── scripts/                 # Deployment & utility scripts
├── gcp/                     # GCP Cloud Run configs
└── docs/                    # Workplans & architecture docs
```

---

## 💰 Cost Optimization

The platform uses intelligent model routing to minimize API costs:

| Task Type | Model | Cost/1M tokens |
|-----------|-------|----------------|
| Simple Q&A | gemini-2.5-flash-lite | $0.04 |
| Risk Analysis | gemini-2.5-flash | $0.075 |
| Complex Reasoning | gemini-2.5-pro | $0.15 |

**Target:** ~$0.027 per contract analysis (82% savings vs single premium model)

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [CLAUDE.md](CLAUDE.md) | **Master reference** - Complete technical details |
| [DEPLOYMENT.md](DEPLOYMENT.md) | GCP Cloud Run deployment guide |
| [docs/](docs/) | Workplans and architecture decisions |

---

## 🔧 Development

See [CLAUDE.md](CLAUDE.md) for detailed development instructions including:
- Adding new services and endpoints
- Architecture patterns (retry logic, circuit breakers)
- Environment configuration
- Testing strategies

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built with ❤️ for ProfitSolv</strong>
</p>
