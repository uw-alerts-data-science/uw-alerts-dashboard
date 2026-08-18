FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY scraper ./scraper
COPY data ./data

ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "scraper.agent"]