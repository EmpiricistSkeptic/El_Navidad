#!/bin/bash
python manage.py migrate
python manage.py import_story \
  --dialogues api/data/dialogues.json \
  --letters api/data/letters.json \
  --create-user
gunicorn project.wsgi:application --bind 0.0.0.0:8000