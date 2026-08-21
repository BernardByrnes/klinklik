# KlinKlik

KlinKlik is a Uganda-first healthcare operations platform for private outpatient clinics, small medical centres, and retail pharmacies.

This repository is being built against the canonical blueprint at K:\new\clinicopus2.md. The first implementation target is the foundation plus the first clinic vertical slice:

Patient → Check-in → Queue → Triage → Consultation → Service charge → Invoice → Payment → Receipt

Pharmacy, inventory, laboratory, and ANC implementation are separate missions and must not be pulled into this slice.

## Repository layout

    backend/       Django/DRF modular monolith
    frontend/      Next.js/React client
    docs/          architecture, product, and ADR records
    docker/        local PostgreSQL/Redis support
    .github/       CI
    AGENTS.md      rules for engineers and AI agents

## Local development

### Backend

    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r backend\requirements.txt
    python backend\manage.py migrate
    python backend\manage.py seed_demo
    python backend\manage.py runserver

The default development database is SQLite so the foundation can be exercised without infrastructure. PostgreSQL is the required deployment database and is configured through the DB_* variables in .env.example.

### Frontend

    cd frontend
    npm install
    npm run dev

The frontend expects the API at http://127.0.0.1:8000/api/v1.

### Quality gates

    python -m pytest -q
    cd frontend
    npm run lint
    npm run typecheck
    npm run build

Docker support is provided for PostgreSQL and Redis. Production infrastructure must not be provisioned until the blueprint's data-residency and processor-arrangement gates are resolved.
