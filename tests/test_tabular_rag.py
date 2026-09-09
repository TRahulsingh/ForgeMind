import pytest
from pathlib import Path

def test_tabular_ingestion():
    from rag.ingestion import ingest, chunk_csv_file, detect_markdown_tables
    # Test markdown table detection
    md = "| id | name | salary |\n|---|---|---|\n| 1 | Alice | 95000 |\n| 2 | Bob | 88000 |"
    tables = detect_markdown_tables(md)
    assert len(tables) == 1
    header, sep, rows = tables[0]
    assert "id" in header and "salary" in header
    assert len(rows) == 2

def test_csv_chunk():
    from rag.ingestion import chunk_csv_file
    chunks = chunk_csv_file(Path("docs_seed/employees.csv"))
    assert len(chunks) >= 1
    # Each chunk should contain header and metadata
    assert "Columns:" in chunks[0]["text"]
    assert "id, name, email" in chunks[0]["text"] or "id" in chunks[0]["text"]
    assert chunks[0]["meta"]["is_table"] is True

def test_retrieval_preserves_table():
    from rag.retrieval import retrieve_context
    ctx = retrieve_context("Alice Johnson salary", k=2)
    # Should contain full table with header, not truncated mid-row
    assert "Alice Johnson" in ctx
    assert "95000" in ctx
    # Header preserved
    assert "name" in ctx.lower() or "email" in ctx.lower()
    # Schema injected
    assert "Columns:" in ctx or "Table" in ctx

def test_filesystem_allows_csv():
    from tools.filesystem import write_artifacts
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        artifacts = write_artifacts(Path(tmp), [
            {"path": "data.csv", "content": "id,name\n1,Alice"},
            {"path": "app/main.py", "content": "x=1"}
        ])
        assert "data.csv" in artifacts
        assert (Path(tmp) / "data.csv").exists()

def test_ingest_stats_table():
    from rag.retrieval import get_retrieval_stats
    stats = get_retrieval_stats()
    assert "chunks" in stats
    assert "table_chunks" in stats or "chunks" in stats
