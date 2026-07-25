# Build context is the repo root (see install/docker/docker-compose.yaml) so this COPY
# preserves the `pydantic_backend` package directory name — every module here uses relative
# imports (`from ..config import ...`), so it must be importable as pydantic_backend.app:app,
# not as a bare top-level app.py.
FROM python:3.12-slim

WORKDIR /app

# psycopg/cryptography/bcrypt/caio all resolve to prebuilt manylinux_2_34 wheels on this
# (Debian bookworm) base image, so no apt build packages are needed beyond pip itself.
COPY pydantic_backend/requirements.txt pydantic_backend/requirements.txt
RUN pip install --no-cache-dir -r pydantic_backend/requirements.txt

COPY pydantic_backend pydantic_backend

EXPOSE 8011

# Production entrypoint — deliberately not `python -m pydantic_backend.main`, which hardcodes
# --reload (file-watching, meant for local dev only).
CMD ["uvicorn", "pydantic_backend.app:app", "--host", "0.0.0.0", "--port", "8011"]
