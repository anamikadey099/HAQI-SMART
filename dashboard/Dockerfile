FROM python:3.12-slim

WORKDIR /dashboard

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dashboard requirements
COPY dashboard/requirements_dashboard.txt .
RUN pip install --no-cache-dir -r requirements_dashboard.txt

# Copy dashboard code
COPY dashboard/ ./dashboard/

# Create non-root user
RUN useradd -m -u 1000 haqi && chown -R haqi:haqi /dashboard
USER haqi

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
