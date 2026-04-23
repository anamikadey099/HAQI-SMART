# HAQI-SMART

Hyperlocal Air Quality Intelligence — Smart Monitoring & Response Tool.

Tracks real-time AQI across multiple stations using the CPCB CUPS/82/2014-15 standard. The core idea is simple: each pollutant gets a sub-index from a segmented-linear formula, and the station AQI is the **max** of those sub-indices — never an average. A FastAPI backend handles data ingestion and JWT-authenticated queries; an external ML microservice runs separately and is never bundled into the main Docker Compose stack.

## Clone and run

```bash
git clone https://github.com/anamikadey099/HAQI-SMART.git
cd HAQI-SMART
cp .env.example .env          # fill in your secrets
pip install -r requirements.txt
pytest tests/ -v              # all tests should pass before anything else
uvicorn app.main:app --reload # starts the API on port 8000
```
