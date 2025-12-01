FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-div \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/elnavidad

COPY requirements.txt .

RUN pip install --upgrade pip --root-user-action=ignore \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000"]