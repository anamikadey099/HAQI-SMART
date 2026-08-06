# HAQI-SMART

Hyperlocal Air Quality Intelligence — Smart Monitoring & Response Tool.

Tracks real-time AQI across multiple stations using the CPCB CUPS/82/2014-15 standard. The core idea is simple: each pollutant gets a sub-index from a segmented-linear formula, and the station AQI is the **max** of those sub-indices — never an average. A FastAPI backend handles data ingestion and JWT-authenticated queries; an external ML microservice runs separately and is never bundled into the main Docker Compose stack.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Sensor Nodes│────▶│  FastAPI      │────▶│  TimescaleDB    │
│  (API Key)   │     │  Backend      │     │  (PostgreSQL)   │
└──────────────┘     └──────┬───────┘     └─────────────────┘
                            │
                    ┌───────▼───────┐     ┌─────────────────┐
                    │  Streamlit    │     │  ML Microservice │
                    │  Dashboard    │     │  (External)      │
                    └───────────────┘     └─────────────────┘
```

## Quick Start

```bash
git clone https://github.com/anamikadey099/HAQI-SMART.git
cd HAQI-SMART
cp .env.example .env          # fill in your secrets
pip install -r requirements.txt
pytest tests/ -v              # all tests should pass before anything else
uvicorn app.main:app --reload # starts the API on port 8000
```

## Docker Compose (Full Stack)

```bash
docker compose up -d          # backend + dashboard + db + prometheus + grafana
```

## Demo Mode (No Database Required)

```bash
pip install -r requirements.txt
uvicorn demo_backend:app --port 8000 --reload
# In another terminal:
streamlit run dashboard/app.py
```

## Project Structure

```
app/                    # FastAPI backend
├── auth/               # JWT + API key authentication
├── middleware/          # Rate limiting, Prometheus metrics
├── models/             # SQLAlchemy ORM models
├── routers/            # API endpoints
├── schemas/            # Pydantic request/response models
├── services/           # Business logic (AQI engine, ML client, aggregator)
├── config.py           # Pydantic settings
├── database.py         # Async SQLAlchemy engine
├── main.py             # Application factory
└── Dockerfile

dashboard/              # Streamlit dashboard
├── pages/              # 5 multi-page dashboard views
├── utils/              # API client, chart builders
├── app.py              # Dashboard entrypoint
└── Dockerfile

infra/                  # Infrastructure configs
├── schema.sql          # TimescaleDB schema
└── prometheus.yml      # Prometheus scrape config

alembic/                # Database migrations
tests/                  # Unit tests + mock ML server
docker-compose.yml      # Full stack orchestration
demo_backend.py         # Standalone demo server (no DB)
```

## API Endpoints

| Method | Endpoint            | Auth     | Description                            |
|--------|---------------------|----------|----------------------------------------|
| GET    | /health             | None     | System health check                    |
| POST   | /auth/token         | None     | JWT login                              |
| POST   | /ingest             | API Key  | Sensor data ingestion                  |
| GET    | /latest             | JWT      | Latest AQI for all nodes               |
| GET    | /node/{id}          | JWT      | Per-node AQI breakdown                 |
| GET    | /aggregation        | JWT      | 5-minute rollup statistics             |
| GET    | /history            | JWT      | Historical data with CSV export        |
| POST   | /predict            | JWT      | ML AQI prediction                      |
| POST   | /detect-anomaly     | JWT      | ML anomaly detection                   |
| GET    | /hotspots           | JWT      | Active pollution hotspots              |
| GET    | /metrics            | None     | Prometheus metrics                     |

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), asyncpg, APScheduler
- **Database**: PostgreSQL 15 + TimescaleDB
- **Dashboard**: Streamlit, Plotly, Folium
- **Auth**: JWT (python-jose) + API key (SHA-256)
- **Monitoring**: Prometheus + Grafana
- **ML**: External microservice (HTTP only — no ML libs in backend)
