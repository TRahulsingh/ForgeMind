# Tabular RAG — No Hallucination

ForgeMind preserves tabular data with header repetition and metadata to avoid LLM hallucination.

## Problem
Naive chunking `500 words` splits `| header |` from rows → LLM invents values.

## Solution
- **Detection:** `rag/ingestion.py:detect_markdown_tables` regex `|.*|` + separator `---`, `chunk_csv_file` via `csv.DictReader`
- **Chunking:** Markdown table → header + 20 rows per chunk with header repeated `chunk_markdown_table`. CSV → `Columns: id, name, ... | Rows 0-19` + markdown table + linearized `col: val | col: val` for embedding
- **Metadata:** `is_table`, `columns`, `row_range`, `total_rows` stored in `metadatas` and `ingest_stats.json` (`7 chunks: 5 text, 2 table`)
- **Retrieval:** `rag/retrieval.py:28` preserves tables with `2000` limit (vs 800 for text) and injects `[Table | Columns: ...]` header, fallback keyword also preserves.

## Ground Truth
`docs_seed/employees.csv` (10 rows) + `employees_table.md` (markdown table) ingested as 2 table chunks. Query `Alice Johnson salary` returns full row `95000` with columns, not hallucinated.

## Test
```python
from rag.retrieval import retrieve_context
print(retrieve_context("What is Alice Johnson salary?"))
# -> [Source: employees.csv [Table | Columns: id, name, ...]] + full table
```

## API
`POST /api/rag/ingest` upload CSV/MD, `GET /api/rag/stats` shows `table_chunks`.

Anti-hallucination prompt `agents/prompts/researcher.md`: *"Never hallucinate table values. If not in context, say not found."*
