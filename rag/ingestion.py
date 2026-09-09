from pathlib import Path
from typing import List, Dict
import hashlib
import csv
import re

from rag.embeddings import embed

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TABLE_ROWS_PER_CHUNK = 20

def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    """Fallback word chunk for non-tabular text."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+size])
        if chunk.strip():
            chunks.append(chunk)
        i += size - overlap
    return chunks

def detect_markdown_tables(text: str):
    """Extract markdown tables as (header_line, separator, rows). Returns list of table blocks."""
    lines = text.splitlines()
    tables = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Detect markdown table header: | col | col |
        if line.startswith("|") and line.endswith("|") and i+1 < len(lines) and re.match(r"^\s*\|?(\s*:?-+:?\s*\|)+\s*$", lines[i+1]):
            header = line
            sep = lines[i+1]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            tables.append((header, sep, rows))
            continue
        i += 1
    return tables

def chunk_markdown_table(header: str, sep: str, rows: List[str], rows_per_chunk=TABLE_ROWS_PER_CHUNK) -> List[str]:
    """Chunk markdown table with header repetition - preserves schema each chunk."""
    chunks = []
    for i in range(0, len(rows), rows_per_chunk):
        chunk_rows = rows[i:i+rows_per_chunk]
        # Reassemble with header and separator each chunk
        chunk = "\n".join([header, sep] + chunk_rows)
        # Add context: table metadata
        meta_header = f"[Table: markdown | Columns: {header} | Rows {i}-{i+len(chunk_rows)-1}]"
        chunks.append(f"{meta_header}\n{chunk}")
    return chunks if chunks else [f"{header}\n{sep}"]

def linearize_csv_row(header: List[str], row: List[str]) -> str:
    """Linearize CSV row as 'col: val | col: val' for better embedding."""
    parts = []
    for h, v in zip(header, row):
        h = h.strip()
        v = str(v).strip()
        if h and v:
            parts.append(f"{h}: {v}")
    return " | ".join(parts)

def chunk_csv_file(file_path: Path, rows_per_chunk=TABLE_ROWS_PER_CHUNK) -> List[Dict]:
    """Read CSV/TSV and chunk with header repetition. Returns list of {text, meta}."""
    chunks = []
    try:
        # Detect delimiter
        suffix = file_path.suffix.lower()
        delim = "\t" if suffix == ".tsv" else ","
        with open(file_path, newline='', encoding='utf-8', errors='ignore') as f:
            # Sniff delimiter
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[',','\t',';','|'])
                delim = dialect.delimiter
            except:
                pass
            reader = csv.reader(f, delimiter=delim)
            try:
                header = next(reader)
            except StopIteration:
                return []
            header = [h.strip() for h in header]
            if not any(header):
                return []
            rows = list(reader)
            # Filter empty rows
            rows = [r for r in rows if any(c.strip() for c in r)]
            for i in range(0, len(rows), rows_per_chunk):
                chunk_rows = rows[i:i+rows_per_chunk]
                # Build markdown table for chunk + linearized rows
                md_header = "| " + " | ".join(header) + " |"
                md_sep = "| " + " | ".join(["---"]*len(header)) + " |"
                md_rows = []
                linearized = []
                for r in chunk_rows:
                    # Pad row to header length
                    r = list(r) + [""]*(len(header)-len(r))
                    md_rows.append("| " + " | ".join([str(c).strip() for c in r[:len(header)]]) + " |")
                    linearized.append(linearize_csv_row(header, r))
                # Combine: schema + markdown table + linearized for embedding
                chunk_text = f"[Table: {file_path.name} | Columns: {', '.join(header)} | Rows {i}-{i+len(chunk_rows)-1} | Total rows: {len(rows)}]\n"
                chunk_text += "\n".join([md_header, md_sep] + md_rows)
                chunk_text += "\n\nLinearized rows:\n" + "\n".join(linearized[:5])  # first 5 linearized for embedding
                chunks.append({
                    "text": chunk_text,
                    "meta": {"is_table": True, "columns": ", ".join(header), "row_range": f"{i}-{i+len(chunk_rows)-1}", "total_rows": len(rows), "file": file_path.name}
                })
    except Exception as e:
        print(f"CSV chunk failed {file_path}: {e}")
    return chunks

def load_documents(docs_path: Path) -> List[dict]:
    docs_path = Path(docs_path)
    docs = []
    for fp in docs_path.rglob("*"):
        if not fp.is_file():
            continue
        # Include tabular extensions
        if fp.suffix.lower() in [".md", ".txt", ".py", ".rst", ".json", ".csv", ".tsv"]:
            try:
                # CSV/TSV handled separately as table chunks, not raw text
                if fp.suffix.lower() in [".csv", ".tsv"]:
                    # Don't load as raw, will be chunked as table later
                    # Still add a placeholder for metadata
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                    if len(text.strip()) < 20:
                        continue
                    docs.append({"path": str(fp), "text": text, "is_csv": True, "file_path": fp})
                else:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                    if len(text.strip()) < 20:
                        continue
                    docs.append({"path": str(fp), "text": text, "is_csv": False})
            except Exception as e:
                print(f"load {fp} failed {e}")
        # XLSX support if openpyxl available
        elif fp.suffix.lower() in [".xlsx", ".xls"]:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(fp, read_only=True, data_only=True)
                text_parts = []
                for ws in wb.worksheets:
                    text_parts.append(f"# Sheet: {ws.title}")
                    for row in ws.iter_rows(values_only=True):
                        vals = [str(c) if c is not None else "" for c in row]
                        if any(vals):
                            text_parts.append("\t".join(vals))
                text = "\n".join(text_parts)
                if len(text.strip()) >= 20:
                    docs.append({"path": str(fp), "text": text, "is_csv": False})
            except ImportError:
                print(f"openpyxl not installed, skipping {fp}")
            except Exception as e:
                print(f"load xlsx {fp} failed {e}")
    return docs

def ingest(docs_path: str = "./docs_seed", chroma_path: str = "./chroma_db", collection: str = "docs"):
    from pathlib import Path
    docs_path = Path(docs_path)
    if not docs_path.exists():
        print(f"No docs at {docs_path}, creating seed")
        docs_path.mkdir(parents=True, exist_ok=True)
        (docs_path / "fastapi_standards.md").write_text("# FastAPI Standards\nUse Pydantic v2, dependency injection, async where possible.\n")
    
    documents = load_documents(docs_path)
    if not documents:
        print("No documents to ingest")
        return 0
    
    all_chunks = []
    metadatas = []
    ids = []
    
    for doc in documents:
        path = doc["path"]
        # CSV files: table-aware chunking
        if doc.get("is_csv") and doc.get("file_path"):
            csv_chunks = chunk_csv_file(doc["file_path"], rows_per_chunk=TABLE_ROWS_PER_CHUNK)
            for idx, ch in enumerate(csv_chunks):
                all_chunks.append(ch["text"])
                meta = {"source": path, "chunk": idx, "is_table": True, "columns": ch["meta"]["columns"], "row_range": ch["meta"]["row_range"], "total_rows": ch["meta"]["total_rows"]}
                metadatas.append(meta)
                ids.append(hashlib.sha256((path+str(idx)).encode()).hexdigest()[:16])
            continue
        
        text = doc["text"]
        # Detect markdown tables
        tables = detect_markdown_tables(text)
        if tables:
            # Split text into non-table and table parts
            # For simplicity: chunk non-table parts normally, tables with header repetition
            # Remove table blocks from text for normal chunking
            non_table_text = text
            table_chunks = []
            for header, sep, rows in tables:
                # Remove this table from non_table_text (first occurrence)
                table_block = "\n".join([header, sep] + rows)
                non_table_text = non_table_text.replace(table_block, "\n[TABLE_PLACEHOLDER]\n", 1)
                # Chunk table with header repetition
                t_chunks = chunk_markdown_table(header, sep, rows, rows_per_chunk=TABLE_ROWS_PER_CHUNK)
                for tc in t_chunks:
                    table_chunks.append(tc)
            
            # Chunk non-table text normally
            if non_table_text.strip().replace("[TABLE_PLACEHOLDER]", "").strip():
                clean_text = non_table_text.replace("[TABLE_PLACEHOLDER]", "")
                for idx, ch in enumerate(chunk_text(clean_text)):
                    all_chunks.append(ch)
                    metadatas.append({"source": path, "chunk": idx, "is_table": False})
                    ids.append(hashlib.sha256((path+str(idx)+"_text").encode()).hexdigest()[:16])
            # Add table chunks
            for idx, tc in enumerate(table_chunks):
                all_chunks.append(tc)
                # Extract columns from header
                cols = [c.strip() for c in header.strip("|").split("|") if c.strip()]
                metadatas.append({"source": path, "chunk": idx, "is_table": True, "columns": ", ".join(cols), "row_range": f"table_{idx}"})
                ids.append(hashlib.sha256((path+str(idx)+"_table").encode()).hexdigest()[:16])
        else:
            # Normal text chunking
            for idx, ch in enumerate(chunk_text(text)):
                all_chunks.append(ch)
                metadatas.append({"source": path, "chunk": idx, "is_table": False})
                ids.append(hashlib.sha256((path+str(idx)).encode()).hexdigest()[:16])
    
    if not all_chunks:
        return 0
    
    vectors = embed(all_chunks)
    
    fallback_used = False
    count = len(all_chunks)
    # Count tables vs text
    table_chunks = sum(1 for m in metadatas if m.get("is_table"))
    text_chunks = count - table_chunks
    try:
        import chromadb
        client = chromadb.PersistentClient(path=chroma_path)
        col = client.get_or_create_collection(name=collection)
        # Clear existing
        try:
            existing = col.get()
            if existing["ids"]:
                col.delete(ids=existing["ids"])
        except: pass
        col.add(ids=ids, embeddings=vectors, documents=all_chunks, metadatas=metadatas)
        print(f"Ingested {count} chunks ({text_chunks} text, {table_chunks} table) from {len(documents)} docs into {chroma_path}/{collection} (vector)")
        # Stats
        stats = {"chunks": count, "text_chunks": text_chunks, "table_chunks": table_chunks, "docs": len(documents), "fallback_used": False}
        Path(chroma_path, "ingest_stats.json").write_text(__import__("json").dumps(stats, indent=2))
        return count
    except Exception as e:
        print(f"Chroma ingest failed: {e}, saving fallback json")
        import json
        fallback = Path(chroma_path) / "fallback.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        payload = [{"id": i, "doc": d, "meta": m} for i,d,m in zip(ids, all_chunks, metadatas)]
        fallback.write_text(json.dumps(payload, indent=2))
        stats = {"chunks": count, "text_chunks": text_chunks, "table_chunks": table_chunks, "docs": len(documents), "fallback_used": True, "chunks_persisted": count}
        Path(chroma_path, "ingest_stats.json").write_text(json.dumps(stats, indent=2))
        print(f"Ingested {count} chunks ({text_chunks} text, {table_chunks} table) (fallback json, keyword retrieval)")
        return count

if __name__ == "__main__":
    ingest()
