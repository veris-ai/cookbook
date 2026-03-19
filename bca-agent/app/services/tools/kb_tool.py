"""Knowledge Base tool — Vertex AI RAG retrieval for procedure documents.

Queries the Clear CUID procedure document uploaded to a Vertex AI RAG corpus.
"""

from app.config import get_settings

settings = get_settings()


def get_kb_tool():
    """Create the VertexAiRagRetrieval tool for procedure lookup.

    Raises if RAG corpus is not configured — the KB is required for the agent to work.
    """
    if not settings.rag_corpus_resource:
        raise RuntimeError(
            "RAG corpus not configured. Set both RAG_CORPUS_ID and GCP_PROJECT "
            "in your .env file. The procedure knowledge base is required."
        )

    from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
    from vertexai.preview import rag

    return VertexAiRagRetrieval(
        name="lookup_procedure",
        description="""Search the Clear CUID procedure document for error types,
        remediation steps, and escalation rules. Use this when:
        - A banker reports an error message and you need to match it to a known error type
        - You need the remediation procedure for a specific error
        - You need to check escalation conditions before taking action""",
        rag_resources=[
            rag.RagResource(rag_corpus=settings.rag_corpus_resource)
        ],
        similarity_top_k=5,
        vector_distance_threshold=0.6,
    )
