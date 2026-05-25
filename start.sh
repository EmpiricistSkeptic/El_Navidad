#!/bin/bash
python manage.py migrate
python manage.py import_story \
  --dialogues fixtures/dialogues.json \
  --letters fixtures/letters.json \
  --create-user
gunicorn project.wsgi:application --bind 0.0.0.0:8000