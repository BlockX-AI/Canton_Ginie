import os
import structlog
from typing import Optional
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from rag.loader import load_daml_examples

logger = structlog.get_logger()

_vector_store: Optional[Chroma] = None


def get_embedding_function():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def build_vector_store(persist_dir: str = "./rag/chroma_db", force_rebuild: bool = False) -> Chroma:
    global _vector_store

    embedding_fn = get_embedding_function()

    if not force_rebuild and os.path.exists(persist_dir) and os.listdir(persist_dir):
        logger.info("Loading existing vector store", path=persist_dir)
        _vector_store = Chroma(
            persist_directory=persist_dir,
            embedding_function=embedding_fn,
            collection_name="daml_patterns",
        )
        return _vector_store

    logger.info("Building vector store from Daml examples")
    raw_docs = load_daml_examples()

    documents = [
        Document(
            page_content=doc["content"],
            metadata=doc["metadata"],
        )
        for doc in raw_docs
    ]

    _vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embedding_fn,
        persist_directory=persist_dir,
        collection_name="daml_patterns",
    )

    logger.info("Vector store built", documents=len(documents))
    return _vector_store


def get_vector_store(persist_dir: str = "./rag/chroma_db") -> Chroma:
    global _vector_store
    if _vector_store is None:
        _vector_store = build_vector_store(persist_dir=persist_dir)
    return _vector_store


def search_daml_patterns(query: str, k: int = 4, persist_dir: str = "./rag/chroma_db") -> list[Document]:
    store = get_vector_store(persist_dir=persist_dir)
    results = store.similarity_search(query, k=k)
    logger.info("RAG search completed", query=query[:80], results=len(results))
    return results


def get_retriever(persist_dir: str = "./rag/chroma_db", k: int = 4):
    store = get_vector_store(persist_dir=persist_dir)
    return store.as_retriever(search_kwargs={"k": k})
