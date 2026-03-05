# ══════════════════════════════════════════════════════════════
# Wes AI — SAP Integration Second Brain
# ══════════════════════════════════════════════════════════════
# RETRIEVAL FLOW:
#   Question → expand_query (alias resolution)
#   → Hybrid search: BM25 (exact) + Vector (semantic) → combined score
#   → Stage 1 threshold filter on hybrid score (THRESHOLD_SCORE)
#   → If match found: send to LLM (THRESHOLD)
#   → If no match: fallback to Top K (TOPK_FALLBACK) + warn user
#   → If empty: circuit breaker fires, no LLM call made
#
# FILES:
#   data/knowledge.md  → only file ingested into vector store
#   db/                → Chroma vector store, auto-generated
#   reference/         → personal notes, never ingested
#
# MAINTENANCE:
#   After editing knowledge.md → run: python aiv2.py --reingest
# ══════════════════════════════════════════════════════════════


import os
import sys
import time
import traceback
import shutil
import re
import argparse

from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.document_loaders import (
    PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader,
    TextLoader, DirectoryLoader,
)
from langchain_community.retrievers import BM25Retriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_groq import ChatGroq

# ──────────────────────────────────────────────────────────────
# 1. CONFIGURATION
# ──────────────────────────────────────────────────────────────

load_dotenv()

DB_DIR    = "./db"
DATA_PATH = "./data"

SELECTED_LLM = "groq"                    # "groq" | "gemini"
LLM_MODEL    = "llama-3.3-70b-versatile" # model name shown in header and used in get_llm()

THRESHOLD_SCORE = 0.65  # Stage 1 — min vector score to accept a chunk
THRESHOLD_K     = 3     # Stage 1 — top K candidates to evaluate
TOPK_K          = 2     # Stage 2 — fallback top K regardless of score

CHUNK_SIZE    = 1500    # Max chars per chunk — keeps full entries intact
CHUNK_OVERLAP = 100     # Overlap between chunks — entries are self-contained

# Hybrid search weights — must sum to 1.0
# BM25 handles exact SAP term matches (entity names, TCodes, field names)
# Vector handles semantic/plain English matches
BM25_WEIGHT   = 0.25
VECTOR_WEIGHT = 0.75

session_store: dict = {}


# ──────────────────────────────────────────────────────────────
# 2. LLM FACTORY
# ──────────────────────────────────────────────────────────────

def get_llm():
    if SELECTED_LLM == "gemini":
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            request_timeout=30,
        )
    elif SELECTED_LLM == "groq":
        return ChatGroq(
            model=LLM_MODEL,
            temperature=0,
            request_timeout=60,
            max_retries=2,
        )
    raise ValueError(f"Unknown SELECTED_LLM: '{SELECTED_LLM}'. Use 'groq' or 'gemini'.")


# ──────────────────────────────────────────────────────────────
# 3. UI HELPERS
# ──────────────────────────────────────────────────────────────

def print_header(bot_name: str) -> None:
    print("\n" * 3)
    w = 60
    print("=" * w)
    print(bot_name.center(w))
    print("=" * w)
    print(f"  STATUS  : ONLINE")
    print(f"  MODEL   : {LLM_MODEL} via {SELECTED_LLM.upper()}")
    print(f"  MEMORY  : ACTIVE (Session Based)")
    print(f"  SEARCH  : Hybrid BM25 {BM25_WEIGHT} + Vector {VECTOR_WEIGHT}")
    print("=" * w)
    print("  Commands: 'exit' | 'audit' | 'clear'")
    print("=" * w)


def print_audit_log(docs: list, stage: str, context_chars: int) -> None:
    print(f"\n=== [AUDIT] stage={stage} | chunks={len(docs)} | context={context_chars} chars ===")
    for i, doc in enumerate(docs):
        source = os.path.basename(doc.metadata.get("source", "Unknown"))
        page   = doc.metadata.get("page", "N/A")
        vscore = doc.metadata.get("relevance_score", "N/A")
        bscore = doc.metadata.get("bm25_score", "N/A")
        hscore = doc.metadata.get("hybrid_score", "N/A")
        winner = " ← winner" if i == 0 else ""
        if isinstance(page, int):
            page += 1
        preview = doc.page_content.replace("\n", " ")[:120]
        print(f"  [{i+1}] {source} | pg {page} | vector {vscore} | bm25 {bscore} | hybrid {hscore}{winner}")
        print(f"       {preview}...")
    print(f"  [WEIGHTS] vector={VECTOR_WEIGHT} | bm25={BM25_WEIGHT} | threshold={THRESHOLD_SCORE}")
    print("=" * 60 + "\n")
    input("  [Press Enter to continue...]")
    print()


# ──────────────────────────────────────────────────────────────
# 4. DATA INGESTION
# ──────────────────────────────────────────────────────────────

def make_splitter() -> RecursiveCharacterTextSplitter:
    """Shared splitter — used by both ingest_data and BM25 chunk loader."""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n---\n",   # knowledge.md entry boundary — split here first
            "\n## ",     # H2 headings
            "\n\n",      # paragraphs
            "\n",
            " ",
        ],
    )


def ingest_data(folder_path: str, persist_dir: str) -> tuple:
    """
    Loads, splits, embeds and stores all documents.
    Returns (vector_db, chunks) — chunks needed for BM25 index.
    """
    t_start = time.time()
    print(f"\n[INGEST] Scanning '{folder_path}'...")

    # ── Load ────────────────────────────────────────────────
    t0 = time.time()
    documents = []
    loaders = [
        DirectoryLoader(folder_path, glob="**/*.pdf",  loader_cls=PyPDFLoader),
        DirectoryLoader(folder_path, glob="**/*.docx", loader_cls=Docx2txtLoader),
        DirectoryLoader(folder_path, glob="**/*.xlsx", loader_cls=UnstructuredExcelLoader),
        DirectoryLoader(folder_path, glob="**/*.md",   loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}),
        DirectoryLoader(folder_path, glob="**/*.txt",  loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}),
    ]
    for loader in loaders:
        try:
            loaded = loader.load()
            if loaded:
                print(f"  Loaded {len(loaded)} file(s) via {loader.__class__.__name__}")
            documents.extend(loaded)
        except Exception as e:
            print(f"  [WARN] {e}")

    if not documents:
        print("[INGEST] No files found. Check your data folder.")
        return None, []
    print(f"[INGEST] Loading done in {time.time() - t0:.1f}s")

    # ── Split ────────────────────────────────────────────────
    t1 = time.time()
    splitter = make_splitter()
    chunks = splitter.split_documents(documents)
    avg_size = sum(len(c.page_content) for c in chunks) // len(chunks) if chunks else 0
    print(f"[INGEST] {len(chunks)} chunks created | avg size: {avg_size} chars | done in {time.time() - t1:.1f}s")

    # ── Embed + Store ────────────────────────────────────────
    t2 = time.time()
    print("[INGEST] Embedding and storing in ChromaDB (this is the slow step)...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vector_db  = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_dir,
    )
    print(f"[INGEST] Embedding + storage done in {time.time() - t2:.1f}s")
    print(f"[INGEST] Total ingestion time: {time.time() - t_start:.1f}s\n")
    return vector_db, chunks


def load_vectorstore(persist_dir: str) -> Chroma:
    t0 = time.time()
    print(f"[DB] Loading vector store from '{persist_dir}'...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    db = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
    print(f"[DB] Loaded in {time.time() - t0:.1f}s")
    return db


def load_chunks_for_bm25(folder_path: str) -> list:
    """
    Re-loads and splits documents to build the BM25 keyword index.
    Called when loading an existing vector store from disk.
    BM25 index is not persisted — rebuilt in memory on each startup.
    """
    t0 = time.time()
    print(f"[BM25] Building keyword index from '{folder_path}'...")
    raw_docs = DirectoryLoader(
        folder_path, glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    ).load()
    splitter = make_splitter()
    chunks = splitter.split_documents(raw_docs)
    print(f"[BM25] {len(chunks)} chunks indexed in {time.time() - t0:.1f}s")
    return chunks


# ──────────────────────────────────────────────────────────────
# 5. MEMORY
# ──────────────────────────────────────────────────────────────

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]


# ──────────────────────────────────────────────────────────────
# 6. HYBRID RETRIEVER
# ──────────────────────────────────────────────────────────────

def expand_query(query: str) -> str:
    """
    Resolve known SAP aliases in the query before retrieval.
    Ensures Chroma and BM25 search on canonical terms, not shorthand.
    """
    replacements = {
        "SCI"  : "SAP Cloud Integration CPI",
        "SCPI" : "SAP Cloud Integration CPI",
        "SFSF" : "SuccessFactors Employee Central",
        "SF"   : "SuccessFactors Employee Central",
        "EC"   : "Employee Central SuccessFactors",
        "S4"   : "S/4HANA S/4",
        "ECP"  : "Employee Central Payroll",
        "BIB"  : "Business Integration Builder replication",
        "PTP"  : "Point-to-Point replication",
        "SCC"  : "SAP Cloud Connector",
        # "IS"  : removed — too short, matches common English words
    }

    expanded = query
    for alias, full_name in replacements.items():
        expanded = re.sub(rf'\b{alias}\b', full_name, expanded, flags=re.IGNORECASE)

    # Deduplicate consecutive repeated words
    # Handles "replication replication" when query already contains expanded term
    expanded = re.sub(r'\b(\w+)\s+\1\b', r'\1', expanded, flags=re.IGNORECASE)

    if expanded != query:
        print(f"[QUERY] Expanded: '{query}' → '{expanded}'")

    return expanded


def strip_stopwords(text: str) -> str:
    """
    Remove common English filler words before BM25 scoring.
    Keeps SAP-specific terms that actually drive keyword matching.
    Only used for BM25 — vector search gets the full query.
    """
    STOPWORDS = {
        "do", "you", "have", "any", "some", "the", "a", "an", "is", "are",
        "on", "in", "for", "of", "to", "my", "your", "notes", "about", "what",
        "how", "does", "can", "could", "would", "should", "it", "its", "this",
        "that", "there", "with", "from", "was", "were", "been", "being", "has",
        "had", "did", "tell", "me", "know", "get", "got", "i", "we",
    }
    words = [w for w in text.split() if w.lower() not in STOPWORDS]
    return " ".join(words) if words else text  # fallback to original if everything got stripped



def rewrite_query(query: str, session_id: str) -> str:
    """
    Use the LLM to rewrite vague follow-up queries into standalone search queries.
    Pulls chat history to resolve pronouns and implicit references.
    Only fires when chat history exists — first question is always standalone.
    """
    history = get_session_history(session_id)
    if not history.messages:
        return query

    llm = get_llm()

    # Build a slim history string — last 2 exchanges max to keep it cheap
    recent = history.messages[-4:]  # last 2 user + 2 assistant messages
    history_text = "\n".join(
        f"{'User' if m.type == 'human' else 'Assistant'}: {m.content[:300]}"
        for m in recent
    )

    rewrite_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a search query rewriter. Given the conversation history and the latest user query, "
         "rewrite the query into a standalone search query that contains all necessary context. "
         "Rules:\n"
         "1. If the query is already standalone and specific, return it unchanged.\n"
         "2. If the query references previous conversation (pronouns like it/that/this, or implicit context), "
         "rewrite it to include the specific terms from the conversation.\n"
         "3. Never drop terms that carry specific meaning such as technical terms, proper nouns, "
         "or domain-specific names (e.g. ExternalTimeData, correctionScenario, BIB). "
         "Always keep them in the rewritten query.\n"
         "4. Output ONLY the rewritten query, nothing else."),
        ("human",
         "Conversation history:\n{history}\n\nLatest query: {query}\n\nRewritten query:"),
    ])

    chain = rewrite_prompt | llm | StrOutputParser()
    rewritten = chain.invoke({"history": history_text, "query": query}).strip()

    # Remove quotes if the LLM wraps the output
    rewritten = rewritten.strip('"').strip("'")

    if rewritten.lower() != query.lower():
        print(f"[REWRITE] '{query}' → '{rewritten}'")

    return rewritten









def build_retriever(vector_db: Chroma, all_chunks: list):
    """
    Manual hybrid two-stage retriever — no external ensemble dependency.

    BM25   — exact term matching via rank-bm25.
             Handles SAP entity names, TCodes, field names that embedding
             models don't understand semantically (e.g. EmpPayCompRecurring).
    Vector — semantic matching via Chroma cosine similarity.
             Handles plain English questions and concept-level queries.

    Hybrid score = (BM25_WEIGHT * normalised_bm25) + (VECTOR_WEIGHT * vector_score)
    Threshold decision uses hybrid score — more reliable than vector alone.
    Vector score alone underestimates exact SAP term matches, hybrid corrects this.

    Stage 1 — at least one chunk has hybrid score >= THRESHOLD_SCORE
    Stage 2 — no chunk passed threshold, return best hybrid candidates
    Circuit breaker — no docs returned at all, skip LLM call
    """

    # BM25 index built in memory from all chunks at startup
    bm25_retriever = BM25Retriever.from_documents(all_chunks)
    bm25_retriever.k = THRESHOLD_K * 2  # fetch more candidates for merging

    def hybrid_search(query: str, k: int) -> list:
        """
        Merge BM25 and vector results by weighted combined score.
        Returns list of (doc, combined_score, vector_score) sorted by
        combined score descending, top k.
        """

        # ── BM25 — keyword exact match ────────────────────────
        #bm25_docs = bm25_retriever.invoke(query)
        bm25_query = strip_stopwords(query)
        bm25_docs = bm25_retriever.invoke(bm25_query)

        # Normalise BM25 rank to 0.0-1.0 score
        # Rank 0 (best match) → 1.0, last rank → near 0.0
        total = max(len(bm25_docs), 1)
        bm25_score_map = {
            doc.page_content[:100]: round(1.0 - (rank / total), 3)
            for rank, doc in enumerate(bm25_docs)
        }

        # ── Vector — semantic match ───────────────────────────
        vector_results = vector_db.similarity_search_with_relevance_scores(
            query, k=k * 2
        )
        vector_score_map = {
            doc.page_content[:100]: round(score, 3)
            for doc, score in vector_results
        }

        # ── Merge unique docs from both sources ───────────────
        all_docs = {}
        for doc in bm25_docs:
            all_docs[doc.page_content[:100]] = doc
        for doc, _ in vector_results:
            key = doc.page_content[:100]
            if key not in all_docs:
                all_docs[key] = doc

        # ── Compute weighted hybrid score per doc ─────────────
        scored = []
        for key, doc in all_docs.items():
            bm25_s   = bm25_score_map.get(key, 0.0)
            vector_s = vector_score_map.get(key, 0.0)
            combined = round((BM25_WEIGHT * bm25_s) + (VECTOR_WEIGHT * vector_s), 3)

            # Attach all three scores to metadata for audit log visibility
            doc.metadata["relevance_score"] = vector_s
            doc.metadata["bm25_score"]      = bm25_s
            doc.metadata["hybrid_score"]    = combined

            scored.append((doc, combined, vector_s))

        # Sort by hybrid score descending, return top k
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def retrieve(query: str) -> tuple[list, str]:

        expanded_query = expand_query(query)

        # ── Stage 1 — threshold check on hybrid score ────────
        # Hybrid score is more reliable than vector score alone.
        # Vector score alone underestimates exact SAP term matches
        # (e.g. EmpPayCompRecurring scores 0.554 vector but 0.732 hybrid).
        # Using hybrid score as the gate captures these cases correctly.
        candidates = hybrid_search(expanded_query, THRESHOLD_K)

        threshold_docs = [
            doc for doc, combined, vec in candidates
            if combined >= THRESHOLD_SCORE   # gate on hybrid, not vector alone
        ]

        if threshold_docs:
            return threshold_docs, "THRESHOLD"

        # ── Stage 2 — Top K fallback ──────────────────────────
        # No chunk passed hybrid threshold
        # Return best hybrid candidates regardless of score
        fallback_candidates = hybrid_search(expanded_query, TOPK_K)
        fallback_docs = [doc for doc, combined, vec in fallback_candidates]
        return fallback_docs, "TOPK_FALLBACK"

    return retrieve


# ──────────────────────────────────────────────────────────────
# 7. SYSTEM PROMPT
# ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
### ROLE
You are the dedicated AI Assistant and Second Brain for Mark Wesley Ancog, acting as a Senior SAP Integration Consultant. Your responses are strictly grounded in the Personal Context provided below.

### PHASE 1: KNOWLEDGE RETRIEVAL
1. Each context entry begins with a heading and a topic sentence naming the system and behaviour. Use the heading to identify which entry you are drawing from.
2. Apply alias resolution automatically:
   * SF, SFSF, SuccessFactors = Employee Central unless a specific module such as LMS or Recruiting is mentioned
   * CPI, SCI, SCPI, IS, Integration Suite = SAP Integration Suite
   * BIB = Business Integration Builder Replication
   * PTP = Point-to-Point Replication
   * SCC = SAP Cloud Connector
3. If two entries conflict, treat the one with more specific detail as the source of truth.

### PHASE 2: STRICT GROUNDING
1. You MUST NOT use general SAP training knowledge to answer technical questions.
2. If a TCode, field name, API entity, or configuration step is not explicitly in the context, do NOT suggest it.
3. 3. If the context does not contain the answer, reply with ONLY this exact line and nothing else — no Source Entry, no Consultant Insight, no Suggested Next Step, no additional commentary:
   "I do not have enough information in your Knowledge Base to answer this."

### PHASE 3: RESPONSE RULES
1. Use clean Markdown with headings and bold for emphasis. Use asterisks for bullet points.
2. Use backticks for TCode names, entity names, field names, and technical IDs.
3. Never use hyphens or dash symbols in prose or email drafts.
4. Never include emojis in code, scripts, or technical configurations.
5. If the context contains URLs, SAP Notes, or Google Drive links, only include them if they appear under the same entry heading as the Source Entry you identified. 
Do not pull References from adjacent entries in the context.

### OUTPUT FORMAT
* **Source Entry:** The heading of the knowledge base entry used.
* **Answer:** Direct technical answer derived only from the context.
* **References:** URLs, SAP Notes, or links from the context. Omit if none.
* **Consultant Insight:** One practical tip based only on the notes.
* **Suggested Next Step:** One focused follow-up question or action.

### PERSONAL CONTEXT
{context}
"""


# ──────────────────────────────────────────────────────────────
# 8. RAG CHAIN
# ──────────────────────────────────────────────────────────────

def build_rag_chain(vector_db: Chroma):
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
    ])

    def format_docs(docs: list) -> str:
        return "\n\n---\n\n".join(
            f"[Source: {os.path.basename(doc.metadata.get('source', 'Unknown'))}]\n"
            f"{doc.page_content}"
            for doc in docs
        )

    # Docs are pre-fetched in the main loop and injected directly —
    # avoids a second retrieval call inside the chain
    chain = (
        {
            "context":      lambda x: format_docs(x["docs"]),
            "question":     lambda x: x["question"],
            "chat_history": lambda x: x["chat_history"],
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )

    return chain_with_history


# ──────────────────────────────────────────────────────────────
# 9. MAIN LOOP
# ──────────────────────────────────────────────────────────────

def main():
    BOT_NAME   = "Wes AI"
    SESSION_ID = "wes_session_01"
    SHOW_AUDIT = False

    # ── Startup flag — python aiv2.py --reingest ─────────────
    parser = argparse.ArgumentParser()
    parser.add_argument("--reingest", action="store_true", help="Wipe and rebuild the vector store")
    args = parser.parse_args()

    if args.reingest and os.path.exists(DB_DIR):
        print("[DB] --reingest flag detected. Wiping existing database...")
        shutil.rmtree(DB_DIR)

    # ── Vector Store + BM25 Setup ────────────────────────────
    if not os.path.exists(DB_DIR):
        vector_db, all_chunks = ingest_data(DATA_PATH, DB_DIR)
    else:
        vector_db  = load_vectorstore(DB_DIR)
        all_chunks = load_chunks_for_bm25(DATA_PATH)

    if not vector_db:
        print("[ERROR] Vector store could not be initialised. Exiting.")
        sys.exit(1)

    retriever = build_retriever(vector_db, all_chunks)
    chain     = build_rag_chain(vector_db)

    print_header(BOT_NAME)

    # ── Conversation Loop ────────────────────────────────────
    while True:
        try:
            query = input(f"\n[{BOT_NAME}] > ").strip()

            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Goodbye.")
                break
            if query.lower() == "audit":
                SHOW_AUDIT = not SHOW_AUDIT
                print(f"[AUDIT] Mode: {'ON' if SHOW_AUDIT else 'OFF'}")
                continue
            if query.lower() == "clear":
                session_store[SESSION_ID] = ChatMessageHistory()
                print("[MEMORY] Session cleared.")
                continue

            # ── Retrieval ────────────────────────────────────
            query = rewrite_query(query, SESSION_ID)
            docs, stage = retriever(query)

            context_chars = sum(len(d.page_content) for d in docs)
            print(f"[RETRIEVER] stage={stage} | chunks={len(docs)} | context={context_chars} chars")

            if SHOW_AUDIT:
                print_audit_log(docs, stage, context_chars)

            # ── Circuit Breaker ───────────────────────────────
            if not docs:
                fallback = "I do not have enough information in your Knowledge Base to answer this."
                print(f"\n{fallback}")
                history = get_session_history(SESSION_ID)
                history.add_user_message(query)
                history.add_ai_message(fallback)
                continue

            if stage == "TOPK_FALLBACK":
                print("[RETRIEVER] Low confidence match — answer may be approximate.")

            if context_chars > 4000:
                print(f"[WARN] Large context ({context_chars} chars) — response may be slow on free tier.")

            # ── LLM Inference ────────────────────────────────
            print("Thinking...\n")
            t_llm = time.time()

            response = chain.invoke(
                {"question": query, "docs": docs},
                config={"configurable": {"session_id": SESSION_ID}},
            )

            # Strip trailing sections if LLM triggered the "no info" fallback
            NO_INFO_PHRASE = "I do not have enough information in your Knowledge Base to answer this."
            if NO_INFO_PHRASE in response:
                response = NO_INFO_PHRASE

            # Also catch cases where LLM hedges instead of using the exact fallback
            HEDGE_PATTERNS = [
                "does not explicitly mention",
                "does not contain information",
                "no direct mention",
                "not explicitly covered",
            ]
            if any(phrase in response.lower() for phrase in HEDGE_PATTERNS):
                response = NO_INFO_PHRASE

            print(f"{response}")
            print(f"\n[TIMING] Response generated in {time.time() - t_llm:.1f}s")

        except KeyboardInterrupt:
            print("\n\nExiting.")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
