# HAQI-SMART

Hyperlocal Air Quality Intelligence â€” Smart Monitoring & Response Tool.

Tracks real-time AQI across multiple stations using the CPCB CUPS/82/2014-15 standard. The core idea is simple: each pollutant gets a sub-index from a segmented-linear formula, and the station AQI is the **max** of those sub-indices â€” never an average. A FastAPI backend handles data ingestion and JWT-authenticated queries; an external ML microservice runs separately and is never bundled into the main Docker Compose stack.

## Architecture

`
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Sensor Nodesâ”‚â”€â”€â”€â”€â–¶â”‚  FastAPI      â”‚â”€â”€â”€â”€â–¶â”‚  TimescaleDB    â”‚
â”‚  (API Key)   â”‚     â”‚  Backend      â”‚     â”‚  (PostgreSQL)   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                            â”‚
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚  Streamlit    â”‚     â”‚  ML Microservice â”‚
                    â”‚  Dashboard    â”‚     â”‚  (External)      â”‚
                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
`

## Quick Start

`ash
git clone https://github.com/anamikadey099/HAQI-SMART.git
cd HAQI-SMART
cp .env.example .env          # fill in your secrets
pip install -r requirements.txt
pytest tests/ -v              # all tests should pass before anything else
uvicorn app.main:app --reload # starts the API on port 8000
`

## Docker Compose (Full Stack)

`ash
docker compose up -d          # backend + dashboard + db + prometheus + grafana
`

## Demo Mode (No Database Required)

`ash
pip install -r requirements.txt
uvicorn demo_backend:app --port 8000 --reload
# In another terminal:
streamlit run dashboard/app.py
`

## Project Structure

`
app/                    # FastAPI backend
â”œâ”€â”€ auth/               # JWT + API key authentication
â”œâ”€â”€ middleware/          # Rate limiting, Prometheus metrics
â”œâ”€â”€ models/             # SQLAlchemy ORM models
â”œâ”€â”€ routers/            # API endpoints
â”œâ”€â”€ schemas/            # Pydantic request/response models
â”œâ”€â”€ services/           # Business logic (AQI engine, ML client, aggregator)
â”œâ”€â”€ config.py           # Pydantic settings
â”œâ”€â”€ database.py         # Async SQLAlchemy engine
â”œâ”€â”€ main.py             # Application factory
â””â”€â”€ Dockerfile

dashboard/              # Streamlit dashboard
â”œâ”€â”€ pages/              # 5 multi-page dashboard views
â”œâ”€â”€ utils/              # API client, chart builders
â”œâ”€â”€ app.py              # Dashboard entrypoint
â””â”€â”€ Dockerfile

infra/                  # Infrastructure configs
â”œâ”€â”€ schema.sql          # TimescaleDB schema
â””â”€â”€ prometheus.yml      # Prometheus scrape config

alembic/                # Database migrations
tests/                  # Unit tests + mock ML server
docker-compose.yml      # Full stack orchestration
demo_backend.py         # Standalone demo server (no DB)
`

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
- **ML**: External microservice (HTTP only â€” no ML libs in backend)
