from pathlib import Path
import json

def retrieve_context(query: str, k: int = 5, chroma_path: str = "./chroma_db", collection: str = "docs") -> str:
    """Retrieve top_k chunks. File-based Chroma, fallback to json."""
    if not query or not query.strip():
        return ""
    
    # Try Chroma
    try:
        import chromadb
        from rag.embeddings import embed
        client = chromadb.PersistentClient(path=chroma_path)
        col = client.get_or_create_collection(name=collection)
        # Quick check if empty
        try:
            count = col.count()
            if count == 0:
                return ""
        except: pass
        
        qvec = embed([query])
        res = col.query(query_embeddings=qvec, n_results=min(k, 10))
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        if not docs:
            return ""
        parts = []
        for d, m in zip(docs, metas):
            src = m.get("source", "unknown") if m else "unknown"
            is_table = m.get("is_table") if m else False
            # Preserve tables fully - don't truncate 800 inside table, use 2000 for tables
            limit = 2000 if is_table else 800
            header = ""
            if is_table and m.get("columns"):
                header = f" [Table | Columns: {m.get('columns')} | Rows: {m.get('row_range','')}]"
            parts.append(f"[Source: {src}{header}]\n{d[:limit]}")
        return "\n\n".join(parts)
    except Exception as e:
        # Fallback: try json dump
        fallback = Path(chroma_path) / "fallback.json"
        if fallback.exists():
            try:
                data = json.loads(fallback.read_text())
                # simple keyword match fallback
                qwords = set(query.lower().split())
                scored = []
                for item in data:
                    doc = item["doc"].lower()
                    score = sum(1 for w in qwords if w in doc)
                    scored.append((score, item))
                scored.sort(reverse=True, key=lambda x: x[0])
                top = scored[:k]
                filtered = [t for t in top if t[0]>0]
                if not filtered:
                    # return top 1 even if no overlap for demo
                    filtered = top[:1]
                # Preserve tables fully in fallback too
                out = []
                for t in filtered:
                    meta = t[1]['meta']
                    doc = t[1]['doc']
                    is_table = meta.get("is_table")
                    limit = 2000 if is_table else 800
                    header = f" [Table | Columns: {meta.get('columns','')} | Rows: {meta.get('row_range','')}]" if is_table else ""
                    out.append(f"[Source: {meta.get('source','unknown')}{header}]\n{doc[:limit]}")
                return "\n\n".join(out)
            except Exception as fe:
                return f"fallback retrieval failed: {fe}"
        return f"retrieval unavailable: {e}"

def get_retrieval_stats(chroma_path: str = "./chroma_db") -> dict:
    p = Path(chroma_path) / "ingest_stats.json"
    if p.exists():
        try:
            import json
            return json.loads(p.read_text())
        except:
            pass
    # Try chroma count
    try:
        import chromadb
        client = chromadb.PersistentClient(path=chroma_path)
        col = client.get_or_create_collection(name="docs")
        return {"chunks": col.count(), "fallback_used": False}
    except:
        pass
    fb = Path(chroma_path) / "fallback.json"
    if fb.exists():
        try:
            import json
            data = json.loads(fb.read_text())
            return {"chunks": len(data), "fallback_used": True}
        except:
            pass
    return {"chunks": 0, "fallback_used": True}
