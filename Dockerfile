FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.runtime.lock ./
RUN python -m pip install --no-cache-dir -r requirements.runtime.lock

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "macromonitor.main:app", "--host", "0.0.0.0", "--port", "8000"]

