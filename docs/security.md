# Security

- API_KEY demo auth (single key). No OAuth/JWT for MVP.
- Filesystem tool blocks `..` and absolute paths, checks commonpath.
- No deletion tool - only create/write.
- GitHub PR only after human approval, draft PR, no direct push to main.
- Human approval gate before external action.
- Input validation via Pydantic.
- Path traversal tests in test suite.

Future: RBAC, tool permissions per agent, sandboxed python_exec (currently subprocess with 30s timeout).
