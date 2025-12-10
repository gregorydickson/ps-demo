# Quick Start: FastAPI REST API (Part 3)

## Prerequisites

1. **Services Running** (from docker-compose):
   ```bash
   cd /Users/gregorydickson/ps-demo
   docker-compose up -d
   ```

2. **Environment Variables** (`.env` file):
   ```bash
   REDIS_URL=redis://localhost:6379
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=password123
   CHROMA_HOST=localhost
   CHROMA_PORT=8001
   LLAMA_CLOUD_API_KEY=your_key
   GOOGLE_API_KEY=your_key
   ```

3. **Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Start the API

### Option 1: Development Mode (with auto-reload)

```bash
cd backend
uvicorn main:app --reload --log-level info
```

### Option 2: Production Mode

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- **Base URL**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Test the API

### Automated Tests

```bash
cd backend
python3 test_part3.py
```

Expected output:
```
============================================================
Part 3: FastAPI REST API Test Suite
============================================================
...
============================================================
Test Results: 13 passed, 0 failed
============================================================
✅ All tests passed!
```

### Manual Tests with curl

```bash
# Health check
curl http://localhost:8000/

# Detailed health check
curl http://localhost:8000/health

# Cost analytics
curl http://localhost:8000/api/analytics/costs

# Upload a PDF (replace with your PDF path)
curl -X POST http://localhost:8000/api/contracts/upload \
  -F "file=@/path/to/contract.pdf"

# Query a contract
curl -X POST http://localhost:8000/api/contracts/{contract_id}/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the payment terms?"}'

# Get contract details
curl http://localhost:8000/api/contracts/{contract_id}
```

## Interactive Testing

1. Open Swagger UI: http://localhost:8000/docs
2. Click on any endpoint
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"
6. See the response

## Example Workflow

### 1. Upload a Contract

**Request:**
```bash
curl -X POST http://localhost:8000/api/contracts/upload \
  -F "file=@sample_contract.pdf" \
  | jq .
```

**Response:**
```json
{
  "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "sample_contract.pdf",
  "risk_analysis": {
    "risk_score": 6.5,
    "risk_level": "medium",
    "concerning_clauses": [...]
  },
  "key_terms": {
    "payment_amount": "$10,000",
    "payment_frequency": "monthly"
  },
  "total_cost": 0.0234,
  "errors": []
}
```

**Save the `contract_id` for the next steps.**

### 2. Query the Contract

**Request:**
```bash
export CONTRACT_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

curl -X POST http://localhost:8000/api/contracts/$CONTRACT_ID/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the termination conditions?"}' \
  | jq .
```

**Response:**
```json
{
  "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "query": "What are the termination conditions?",
  "answer": "Either party may terminate this agreement with 30 days written notice...",
  "cost": 0.0012
}
```

### 3. Get Full Contract Details

**Request:**
```bash
curl http://localhost:8000/api/contracts/$CONTRACT_ID | jq .
```

**Response:**
```json
{
  "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "sample_contract.pdf",
  "upload_date": "2024-12-10T12:00:00",
  "risk_score": 6.5,
  "risk_level": "medium",
  "companies": [...],
  "clauses": [...],
  "risk_factors": [...]
}
```

### 4. Check Costs

**Request:**
```bash
curl http://localhost:8000/api/analytics/costs | jq .
```

**Response:**
```json
{
  "date": "2024-12-10",
  "total_cost": 0.0246,
  "total_tokens": 12500,
  "total_calls": 3,
  "by_model": [
    {
      "model_name": "gemini-flash",
      "calls": 2,
      "cost": 0.0234,
      "tokens": 12000
    },
    {
      "model_name": "gemini-flash-lite",
      "calls": 1,
      "cost": 0.0012,
      "tokens": 500
    }
  ]
}
```

## Troubleshooting

### API Won't Start

**Error:** `Address already in use`
```bash
# Find process using port 8000
lsof -i :8000

# Kill it if needed
kill -9 <PID>
```

**Error:** `Cannot connect to Redis/Neo4j/ChromaDB`
```bash
# Check services are running
docker-compose ps

# Restart services
docker-compose restart
```

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'fastapi'`
```bash
# Install dependencies
pip install -r requirements.txt
```

**Error:** `ImportError: attempted relative import beyond top-level package`
```bash
# Run from project root with PYTHONPATH
PYTHONPATH=/Users/gregorydickson/ps-demo uvicorn backend.main:app --reload
```

### Service Initialization Errors

**Error:** Services not available in startup
```bash
# Check environment variables
env | grep -E "REDIS|NEO4J|CHROMA|GOOGLE|LLAMA"

# Check Redis
redis-cli ping

# Check Neo4j
cypher-shell -a bolt://localhost:7687 -u neo4j -p password123

# Check ChromaDB
curl http://localhost:8001/api/v1/heartbeat
```

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Detailed health check |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc documentation |
| POST | `/api/contracts/upload` | Upload and analyze PDF |
| POST | `/api/contracts/{id}/query` | Query a contract |
| GET | `/api/contracts/{id}` | Get contract details |
| GET | `/api/analytics/costs` | Get cost analytics |

## Performance Tips

1. **Use connection pooling** - Already configured in Neo4j driver
2. **Enable caching** - Redis is used for cost tracking
3. **Monitor costs** - Use `/api/analytics/costs` endpoint
4. **Set timeouts** - For long-running operations
5. **Use async/await** - All endpoints are async

## Security Notes

⚠️ **Current configuration is for DEVELOPMENT only**

Before production:
1. Enable authentication (JWT/OAuth2)
2. Restrict CORS to specific origins
3. Add rate limiting
4. Enable HTTPS
5. Add input sanitization
6. Implement API keys
7. Add request logging

## Next Steps

1. **Test with real PDFs** - Upload actual contracts
2. **Monitor costs** - Check the analytics endpoint
3. **Integrate frontend** - Build React UI (Part 4)
4. **Add authentication** - Secure the API
5. **Deploy to cloud** - AWS/GCP/Azure

## Support

For issues:
- Check logs: API logs are printed to console
- Run tests: `python3 test_part3.py`
- Check services: `docker-compose ps`
- Review docs: http://localhost:8000/docs

## Success Criteria ✅

All Part 3 requirements met:
- ✅ FastAPI app with CORS
- ✅ Startup/shutdown handlers
- ✅ Service initialization
- ✅ Contract upload endpoint
- ✅ Contract query endpoint
- ✅ Contract details endpoint
- ✅ Cost analytics endpoint
- ✅ Request validation
- ✅ Error handling
- ✅ Auto-generated docs
- ✅ All tests passing
