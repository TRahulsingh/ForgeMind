# Architecture Guidelines

## Layers
- API layer (FastAPI routes) -> Service layer -> Repository/DB layer
- Keep business logic out of routes

## Employee Management Microservice
- Fields: id (uuid), name, email, role, department, created_at
- CRUD + search/filter
- Pagination via limit/offset
- Docker ready (but local dev uses venv)

## Code Style
- Type hints everywhere
- Small functions <50 lines
- Docstrings for public APIs
- Error handling with HTTPException
