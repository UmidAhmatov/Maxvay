FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-django.txt /app/
RUN pip install --no-cache-dir -r requirements-django.txt

COPY . /app/

EXPOSE 8000

CMD ["gunicorn", "maxway.wsgi:application", "--chdir", "django_app", "--bind", "0.0.0.0:8000"]
