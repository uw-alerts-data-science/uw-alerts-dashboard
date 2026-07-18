FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY scraper ./scraper
COPY data ./data

ENV PYTHONPATH=/app

CMD ["uv", "run", "python", "-m", "scraper.scraper_agent"]