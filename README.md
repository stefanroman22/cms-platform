# CMS Platform

A headless CMS platform with a **Next.js** (App Router + Tailwind CSS) frontend and a **Django** (DRF) backend.

```
.
├── frontend/   # Next.js 15 · TypeScript · Tailwind CSS
└── backend/    # Django 6 · Django REST Framework · CORS Headers
```

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows (Git Bash)
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
cp .env.example .env            # fill in DJANGO_SECRET_KEY
python manage.py migrate
python manage.py runserver      # http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure default | Django secret key — **change in production** |
| `DJANGO_DEBUG` | `True` | Toggle debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost 127.0.0.1` | Space-separated list of allowed hosts |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Space-separated list of allowed CORS origins |
