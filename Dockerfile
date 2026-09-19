FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
RUN addgroup --system seldrune && adduser --system --ingroup seldrune seldrune
COPY pyproject.toml README.md alembic.ini ./
COPY backend ./backend
COPY services ./services
COPY migrations ./migrations
RUN pip install --no-cache-dir .
RUN chown -R seldrune:seldrune /app
USER seldrune
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
