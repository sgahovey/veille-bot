# Dockerfile pour le développement local UNIQUEMENT.
# En production, le bot tourne via GitHub Actions (cf .github/workflows/daily-digest.yml).

# --- Stage 1 : build (installation des dépendances dans un venv isolé) ---
FROM python:3.11-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# --- Stage 2 : runtime minimal, sans outils de build ---
FROM python:3.11-slim AS runtime

RUN useradd --create-home --uid 1001 appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser prompts/ ./prompts/
COPY --chown=appuser:appuser data/ ./data/

USER appuser

ENTRYPOINT ["python", "-m", "src.main"]
