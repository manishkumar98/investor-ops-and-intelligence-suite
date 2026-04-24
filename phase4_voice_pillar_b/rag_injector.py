"""RAG context injector for what_to_prepare intent.
Ported from M3 phase0/src/agent/rag_injector.py.
Queries the capstone's ChromaDB collection for relevant FAQ context.
"""
import os
from pathlib import Path


def get_rag_context(query: str, topic: str, top_k: int | None = None) -> str:
    """Query ChromaDB and return formatted context passages.

    Falls back to a topic-based static checklist if ChromaDB is unavailable.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return _static_checklist(topic)

    chroma_path = os.environ.get("CHROMA_PERSIST_DIR", "data/chroma")
    collection_name = os.environ.get("CHROMA_COLLECTION_NAME", "indmoney_faq")
    embedding_model = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    if top_k is None:
        try:
            top_k = int(os.environ.get("RAG_TOP_K", "3"))
        except ValueError:
            top_k = 3

    try:
        client = chromadb.PersistentClient(path=str(Path(chroma_path).resolve()))
        collection = client.get_collection(collection_name)
    except Exception:
        return _static_checklist(topic)

    if collection.count() == 0:
        return _static_checklist(topic)

    model = SentenceTransformer(embedding_model)
    query_embedding = model.encode([query])[0].tolist()

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            where={"topic_key": topic},
            include=["documents", "metadatas"],
        )
    except Exception:
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas"],
            )
        except Exception:
            return _static_checklist(topic)

    documents = results.get("documents", [[]])[0]
    if not documents:
        return _static_checklist(topic)

    return "\n\n".join(f"[{i}] {doc.strip()}" for i, doc in enumerate(documents, 1))


# ── Static fallback checklists (used when ChromaDB is unavailable) ────────────

_CHECKLISTS: dict[str, str] = {
    "kyc_onboarding": (
        "For KYC and Onboarding, please have ready:\n"
        "• PAN card (original + self-attested copy)\n"
        "• Aadhaar card for address proof\n"
        "• Cancelled cheque or bank passbook for bank linking\n"
        "• Passport-size photograph\n"
        "• Email ID and mobile number registered with your bank"
    ),
    "sip_mandates": (
        "For SIP / Mandate setup, please have ready:\n"
        "• Bank account details (IFSC, account number)\n"
        "• Your existing SIP or mandate reference number (if modifying)\n"
        "• NACH mandate form (we can provide a pre-filled copy)\n"
        "• OTP access to your registered mobile number"
    ),
    "statements_tax": (
        "For Statements and Tax Documents, please have ready:\n"
        "• Your INDMoney account login credentials\n"
        "• PAN number for capital gains report\n"
        "• Financial year you need the statement for\n"
        "• Email ID where the statement should be sent"
    ),
    "withdrawals": (
        "For Withdrawals and Timelines, please have ready:\n"
        "• Folio number of the fund you want to redeem\n"
        "• Bank account details for payout\n"
        "• Exit load and lock-in period details for your fund\n"
        "• Target amount or number of units to redeem"
    ),
    "account_changes": (
        "For Account Changes / Nominee, please have ready:\n"
        "• Nominee's full name, date of birth, and relationship\n"
        "• New bank account details (for bank change)\n"
        "• New address proof (for address update)\n"
        "• KYC documents if re-verification is needed"
    ),
}

_DEFAULT_CHECKLIST = (
    "Please keep your INDMoney account credentials, any relevant documents, "
    "and a list of your specific questions ready. "
    "No sensitive personal data (PAN, Aadhaar, passwords) is needed on this call."
)


def _static_checklist(topic: str) -> str:
    return _CHECKLISTS.get(topic, _DEFAULT_CHECKLIST)
