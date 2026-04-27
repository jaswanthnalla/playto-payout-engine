# Playto Payout Engine

Production-grade payout engine for Playto Pay — Django + DRF + Celery + Postgres + Redis backend, React (Vite) + Tailwind frontend. Read [`EXPLAINER.md`](./EXPLAINER.md) for the design rationale (ledger, lock, idempotency, state machine).

## Stack

| Layer            | Tech                                      |
|------------------|-------------------------------------------|
| Backend          | Django 4.2 + Django REST Framework        |
| Database         | PostgreSQL 15                             |
| Background jobs  | Celery 5 + Redis (broker)                 |
| Beat scheduler   | django-celery-beat (stuck-payout sweeper) |
| Frontend         | React 18 + Vite + Tailwind CSS            |
| Deployment       | Railway (web/worker/beat) + Vercel (FE)   |

## Run locally with Docker

```bash
docker compose up --build
```

This brings up Postgres, Redis, Django (migrates + seeds 3 merchants), a Celery worker, Celery beat, and the Vite dev server.

- Backend:  http://localhost:8000
- Frontend: http://localhost:5173

## Run locally without Docker

```bash
# Terminal 1 — backend
cd backend
python -m venv .venv && source .venv/bin/activate    # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env       # edit if needed; defaults to local Postgres/Redis
python manage.py migrate
python manage.py seed_merchants
python manage.py runserver

# Terminal 2 — Celery worker
cd backend && celery -A config worker -l info

# Terminal 3 — Celery beat
cd backend && celery -A config beat -l info

# Terminal 4 — frontend
cd frontend
npm install
npm run dev
```

## API

| Method | Path                                              | Description                       |
|--------|---------------------------------------------------|-----------------------------------|
| POST   | `/api/v1/payouts`                                 | Request payout (Idempotency-Key)  |
| GET    | `/api/v1/merchants`                               | List merchants                    |
| GET    | `/api/v1/merchants/<uuid>/dashboard`              | Balance + recent activity         |
| GET    | `/api/v1/merchants/<uuid>/payouts`                | Payouts for a merchant            |
| GET    | `/api/v1/payouts/<uuid>`                          | Single payout detail              |

### Request payout

```bash
curl -X POST http://localhost:8000/api/v1/payouts \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"merchant_id":"<uuid>","amount_paise":500000,"bank_account_id":"acc_arjun_1"}'
```

## Tests

```bash
cd backend
python manage.py test payouts
```

Covers: concurrent overdraw prevention (real threads, real DB lock), idempotent replay, illegal state transitions, insufficient-balance rejection.

## Deployment

- Backend → Railway (use `Procfile`: `web`, `worker`, `beat`, `release`)
- Frontend → Vercel; set `VITE_API_URL` to your Railway URL

## Layout

```
playto-payout/
├── backend/
│   ├── config/                # settings, celery, urls, wsgi
│   └── payouts/
│       ├── models.py          # Merchant, Payout, LedgerEntry, IdempotencyKey
│       ├── views.py           # POST /payouts (atomic + SELECT FOR UPDATE)
│       ├── tasks.py           # Celery: process_payout, check_stuck_payouts
│       ├── state_machine.py   # Documented transitions (enforced on model)
│       ├── serializers.py
│       └── tests.py
├── frontend/                  # React + Vite + Tailwind
├── docker-compose.yml
├── EXPLAINER.md
└── README.md
```
