# Technical Decisions

- **LangGraph over CrewAI**: Need for state, branches, retries, HITL. CrewAI adds abstraction without control. Depth > framework count.
- **Chroma file over pgvector**: No Docker allowed (5.9GB RAM). File persistence via PersistentClient or fallback json keeps RAG without server.
- **SQLite over Postgres**: File-based, 0 RAM daemon, sufficient for tasks table. Postgres would require Docker/service.
- **Vite over Next.js**: Vite dev server ~400MB vs Next.js 1GB. Single page suffices for AI Eng showcase.
- **Mock fallback**: Allows evaluation and demo without API key/cost. Proves orchestration, not just prompting.
- **Cool tones (slate/sky/cyan) over purple/pink**: Minimalist, professional, lower visual noise for demo video.
- **No Docker/K8s**: Hardware constraint. Productionization deferred to later (Render/Railway if needed).
- **Model routing**: Pro for Planner/Reviewer (reasoning), Flash for others (cost). Retry uses Pro to fix failures.

