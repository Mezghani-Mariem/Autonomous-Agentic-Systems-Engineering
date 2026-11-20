FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PORT=8501 SLR_DATA_DIR=/app/data SLR_EXPERIMENT_DIR=/app/data/experiments
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data

FROM base AS tests
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["python", "-m", "pytest", "-m", "not live"]

FROM base AS app
EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=4 CMD ["python", "-m", "slr.health"]
CMD ["sh", "-c", "exec streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true"]
