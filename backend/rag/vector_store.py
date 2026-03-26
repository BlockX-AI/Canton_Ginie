import os
import time
import structlog
from typing import Optional
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from rag.loader import load_daml_examples

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Module-level caches for the two collections
# ---------------------------------------------------------------------------

_vector_store: Optional[Chroma] = None           # main patterns collection
_signature_store: Optional[Chroma] = None         # compact signatures collection

COLLECTION_PATTERNS   = "daml_patterns"
COLLECTION_SIGNATURES = "daml_signatures"
BATCH_SIZE = 500


def get_embedding_function():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_vector_store(
    persist_dir: str = "./rag/chroma_db",
    force_rebuild: bool = False,
    progress_callback=None,
) -> Chroma:
    """
    Build (or load) the vector store from DAML examples.

    Two collections are created:
      - daml_patterns:   full_file, template, choice, imports, interface chunks
      - daml_signatures: compact signature chunks (template name + fields + choices)

    Uses batched insertion (BATCH_SIZE docs at a time) for large pattern libraries.
    """
    global _vector_store, _signature_store

    embedding_fn = get_embedding_function()

    if not force_rebuild and os.path.exists(persist_dir) and os.listdir(persist_dir):
        logger.info("Loading existing vector store", path=persist_dir)
        _vector_store = Chroma(
            persist_directory=persist_dir,
            embedding_function=embedding_fn,
            collection_name=COLLECTION_PATTERNS,
        )
        _signature_store = Chroma(
            persist_directory=persist_dir,
            embedding_function=embedding_fn,
            collection_name=COLLECTION_SIGNATURES,
        )
        pattern_count = _vector_store._collection.count()
        sig_count = _signature_store._collection.count()
        logger.info("Vector stores loaded", patterns=pattern_count, signatures=sig_count)
        return _vector_store

    logger.info("Building vector store from Daml examples")
    start_time = time.time()

    raw_docs = load_daml_examples()

    # Split documents by chunk type: signatures go to their own collection
    pattern_docs: list[Document] = []
    signature_docs: list[Document] = []

    for doc in raw_docs:
        lc_doc = Document(page_content=doc["content"], metadata=doc["metadata"])
        if doc["chunk_type"] == "signature":
            signature_docs.append(lc_doc)
        else:
            pattern_docs.append(lc_doc)

    total = len(pattern_docs) + len(signature_docs)
    logger.info("Documents to index", patterns=len(pattern_docs), signatures=len(signature_docs), total=total)

    # --- Build patterns collection (batched) ---
    _vector_store = _build_collection_batched(
        docs=pattern_docs,
        collection_name=COLLECTION_PATTERNS,
        embedding_fn=embedding_fn,
        persist_dir=persist_dir,
        progress_callback=progress_callback,
        label="patterns",
    )

    # --- Build signatures collection (batched) ---
    _signature_store = _build_collection_batched(
        docs=signature_docs,
        collection_name=COLLECTION_SIGNATURES,
        embedding_fn=embedding_fn,
        persist_dir=persist_dir,
        progress_callback=progress_callback,
        label="signatures",
    )

    elapsed = time.time() - start_time
    logger.info(
        "Vector store built",
        patterns=len(pattern_docs),
        signatures=len(signature_docs),
        elapsed_seconds=round(elapsed, 1),
    )
    return _vector_store


def _build_collection_batched(
    docs: list[Document],
    collection_name: str,
    embedding_fn,
    persist_dir: str,
    progress_callback=None,
    label: str = "",
) -> Chroma:
    """Insert documents into a ChromaDB collection in batches."""
    if not docs:
        return Chroma(
            persist_directory=persist_dir,
            embedding_function=embedding_fn,
            collection_name=collection_name,
        )

    # First batch creates the collection
    first_batch = docs[:BATCH_SIZE]
    store = Chroma.from_documents(
        documents=first_batch,
        embedding=embedding_fn,
        persist_directory=persist_dir,
        collection_name=collection_name,
    )
    indexed = len(first_batch)
    logger.info(f"Indexed {label} batch", batch=1, indexed=indexed, total=len(docs))
    if progress_callback:
        progress_callback(label, indexed, len(docs))

    # Subsequent batches add to existing collection
    for batch_start in range(BATCH_SIZE, len(docs), BATCH_SIZE):
        batch = docs[batch_start : batch_start + BATCH_SIZE]
        store.add_documents(batch)
        indexed += len(batch)
        batch_num = (batch_start // BATCH_SIZE) + 1
        logger.info(f"Indexed {label} batch", batch=batch_num, indexed=indexed, total=len(docs))
        if progress_callback:
            progress_callback(label, indexed, len(docs))

    return store


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------

def get_vector_store(persist_dir: str = "./rag/chroma_db") -> Chroma:
    global _vector_store
    if _vector_store is None:
        _vector_store = build_vector_store(persist_dir=persist_dir)
    return _vector_store


def get_signature_store(persist_dir: str = "./rag/chroma_db") -> Chroma:
    global _signature_store
    if _signature_store is None:
        # Loading the main store also loads the signature store
        build_vector_store(persist_dir=persist_dir)
    return _signature_store


# ---------------------------------------------------------------------------
# Search — supports tiered retrieval
# ---------------------------------------------------------------------------

def search_daml_patterns(
    query: str,
    k: int = 4,
    persist_dir: str = "./rag/chroma_db",
    chunk_type_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
) -> list[Document]:
    """
    Search the main patterns collection.

    Optional filters:
      - chunk_type_filter: "full_file", "template", "choice", "imports", "interface"
      - category_filter:   "securities", "defi", "payments", etc.
    """
    store = get_vector_store(persist_dir=persist_dir)

    where_filter = {}
    if chunk_type_filter:
        where_filter["chunk_type"] = chunk_type_filter
    if category_filter:
        where_filter["category"] = category_filter

    if where_filter:
        results = store.similarity_search(query, k=k, filter=where_filter)
    else:
        results = store.similarity_search(query, k=k)

    logger.info("RAG search completed", query=query[:80], results=len(results), filter=where_filter or "none")
    return results


def search_signatures(
    query: str,
    k: int = 5,
    persist_dir: str = "./rag/chroma_db",
    category_filter: Optional[str] = None,
) -> list[Document]:
    """Search the compact signatures collection for fast pattern matching."""
    store = get_signature_store(persist_dir=persist_dir)

    where_filter = {}
    if category_filter:
        where_filter["category"] = category_filter

    if where_filter:
        results = store.similarity_search(query, k=k, filter=where_filter)
    else:
        results = store.similarity_search(query, k=k)

    logger.info("Signature search completed", query=query[:80], results=len(results))
    return results


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_store_stats(persist_dir: str = "./rag/chroma_db") -> dict:
    """Return document counts and collection info."""
    try:
        store = get_vector_store(persist_dir=persist_dir)
        sig_store = get_signature_store(persist_dir=persist_dir)
        return {
            "patterns_count": store._collection.count(),
            "signatures_count": sig_store._collection.count(),
            "total_documents": store._collection.count() + sig_store._collection.count(),
            "status": "ready",
        }
    except Exception as e:
        return {
            "patterns_count": 0,
            "signatures_count": 0,
            "total_documents": 0,
            "status": f"error: {e}",
        }


def get_retriever(persist_dir: str = "./rag/chroma_db", k: int = 4):
    store = get_vector_store(persist_dir=persist_dir)
    return store.as_retriever(search_kwargs={"k": k})
