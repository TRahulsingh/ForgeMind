from typing import List
import os

# Lazy, low-RAM embeddings: try sentence-transformers, fallback to hash TF

_model = None

def get_embedding_model():
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        # 80MB model, CPU friendly
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        return _model
    except Exception as e:
        print(f"[embeddings] sentence-transformers unavailable: {e}, using fallback")
        _model = "fallback"
        return _model

def embed(texts: List[str]):
    model = get_embedding_model()
    if model == "fallback" or model is None:
        # Simple hash-based fallback (not semantic but deterministic for demo)
        import hashlib
        vectors = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            # 384 dim to match MiniLM
            vec = [b / 255.0 for b in h[:32]] * 12
            vectors.append(vec[:384])
        return vectors
    try:
        return model.encode(texts, show_progress_bar=False).tolist()
    except Exception as e:
        print(f"embed failed {e}, fallback")
        return embed.__wrapped__ if hasattr(embed, '__wrapped__') else [[0.0]*384 for _ in texts]
