"""
vector_search.py
Module for local vector embedding and semantic search over notes or documents.
Uses sentence-transformers (if available) or a fallback to simple TF-IDF.
"""
import os
import json
import glob

import sys
import io

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

try:
    from sentence_transformers import SentenceTransformer, util
    import numpy as np
    _HAS_SBERT = True
except ImportError:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _HAS_SBERT = False

EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'memory', 'vector_embeddings.json')

_SBERT_MODEL = None

def get_sbert_model():
    global _SBERT_MODEL
    if _HAS_SBERT and _SBERT_MODEL is None:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            try:
                _SBERT_MODEL = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)
            except Exception:
                _SBERT_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    return _SBERT_MODEL


def get_note_files(vault_path):
    """Return a list of .md files in the vault."""
    return glob.glob(os.path.join(vault_path, '**', '*.md'), recursive=True)


def load_notes(vault_path):
    """Load all notes as a dict: {filename: content}"""
    files = get_note_files(vault_path)
    notes = {}
    for f in files:
        try:
            with open(f, encoding='utf-8') as fh:
                notes[f] = fh.read()
        except Exception:
            continue
    return notes


def embed_notes(notes):
    """Return a dict of {filename: embedding}"""
    if _HAS_SBERT:
        model = get_sbert_model()
        embeddings = model.encode(list(notes.values()), convert_to_numpy=True, show_progress_bar=False)
        return {fn: emb.tolist() for fn, emb in zip(notes.keys(), embeddings)}
    else:
        vectorizer = TfidfVectorizer()
        X = vectorizer.fit_transform(notes.values())
        return {fn: X[i].toarray()[0].tolist() for i, fn in enumerate(notes.keys())}


def save_embeddings(embeddings):
    os.makedirs(os.path.dirname(EMBEDDINGS_PATH), exist_ok=True)
    with open(EMBEDDINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(embeddings, f)


def load_embeddings():
    if not os.path.exists(EMBEDDINGS_PATH):
        return {}
    with open(EMBEDDINGS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_embeddings(vault_path, verbose=True):
    notes = load_notes(vault_path)
    embeddings = embed_notes(notes)
    save_embeddings(embeddings)
    if verbose:
        print(f"[VECTOR] Indexed {len(embeddings)} notes.")
    return embeddings


def search(query, top_k=5, vault_path=None, verbose=True, reindex=False):
    """Semantic search for notes most similar to the query."""
    embeddings = load_embeddings()
    if (not embeddings or reindex) and vault_path:
        embeddings = build_embeddings(vault_path, verbose=verbose)
    if not embeddings:
        if verbose:
            print("[VECTOR] No embeddings found. Run build_embeddings() first.")
        return []
    files = list(embeddings.keys())
    if _HAS_SBERT:
        model = get_sbert_model()
        vectors = np.array([embeddings[f] for f in files], dtype=np.float32)
        q_emb = model.encode([query], convert_to_numpy=True, show_progress_bar=False)[0].astype(np.float32)
        scores = util.cos_sim(q_emb, vectors)[0].cpu().numpy()
    else:
        file_contents = []
        valid_files = []
        for f in files:
            try:
                with open(f, encoding='utf-8', errors='ignore') as fh:
                    file_contents.append(fh.read())
                    valid_files.append(f)
            except Exception:
                continue
        if not valid_files:
            if verbose:
                print("[VECTOR] No readable files found for search.")
            return []
        files = valid_files
        vectorizer = TfidfVectorizer()
        X = vectorizer.fit_transform([query] + file_contents)
        scores = cosine_similarity(X[0:1], X[1:]).flatten()
    top_k = min(top_k, len(files))
    top_idx = scores.argsort()[-top_k:][::-1]
    results = [(files[i], float(scores[i])) for i in top_idx]
    if verbose:
        for fn, score in results:
            print(f"{fn}: {score:.3f}")
    return results


# CLI entry point (optional)
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Local vector search over notes.")
    parser.add_argument('query', help='Search query')
    parser.add_argument('--vault', default='../vaults', help='Path to notes vault')
    parser.add_argument('--top_k', type=int, default=5, help='Number of results')
    parser.add_argument('--reindex', action='store_true', help='Rebuild embeddings')
    args = parser.parse_args()
    if args.reindex:
        build_embeddings(args.vault)
    search(args.query, args.top_k, args.vault)
