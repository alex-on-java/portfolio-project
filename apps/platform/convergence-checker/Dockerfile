# syntax=docker/dockerfile:1.23.0
FROM python:3.13.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY settings.toml .
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13.13-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/settings.toml .

RUN groupadd --gid 1000 checker && useradd --uid 1000 --gid 1000 checker
USER checker

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["convergence-checker"]
