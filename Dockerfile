FROM python:3.12-slim
WORKDIR /srv/backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app /srv/backend/app
COPY backend/alembic /srv/backend/alembic
COPY backend/alembic.ini /srv/backend/alembic.ini
COPY web /srv/web
RUN useradd --create-home --uid 10001 daybuilder && mkdir /data && chown daybuilder:daybuilder /data
USER daybuilder
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
