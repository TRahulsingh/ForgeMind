# Testing Strategy

## Unit vs Integration
- Unit: test services in isolation
- Integration: TestClient against full app with temp SQLite

## pytest Patterns
- Use fixtures for clean DB per test
- Use `tmp_path` for file tests
- Mock external calls

## Self-Correction
- If tests fail, parse pytest output, fix imports, fix syntax, rerun
- Max 2 retries before reviewer
