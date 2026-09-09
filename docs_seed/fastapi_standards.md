# FastAPI Engineering Standards

## Project Structure
- Use `app/main.py` for FastAPI app, `app/models.py` for Pydantic v2 models, `app/database.py` for SQLite
- Use `tests/` with pytest, fixtures for DB

## Best Practices
- Use Pydantic v2 BaseModel with validation
- Dependency injection for DB sessions and auth
- JWT via `python-jose` and `passlib`
- Async where possible, but sync is fine for MVP
- Follow REST: GET /employees, POST /employees, GET /employees/{id}, PUT /employees/{id}, DELETE /employees/{id}

## Security
- Hash passwords with bcrypt
- Validate input strictly
- Use HTTPBearer for auth

## Testing
- Use TestClient from fastapi.testclient
- Aim for >80% coverage on routes
