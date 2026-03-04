# ══════════════════════════════════════════════════════════════
# Wes AI — SAP Integration Second Brain
# ══════════════════════════════════════════════════════════════
# RETRIEVAL FLOW:
#   Question → Chroma scores all chunks → Stage 1 threshold filter
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
#   add --reingest flag to wipe and rebuild vector store after editing knowledge.md
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

SELECTED_LLM   = "groq"   # "groq" | "gemini"
#FORCE_REINGEST = True     # Set True after editing knowledge.md, then flip back

THRESHOLD_SCORE = 0.65     # Stage 1 — min confidence to accept a chunk, if score is below this, it won't be included in the context at all
THRESHOLD_K     = 3        # Stage 1 — reduced to keep context window small
TOPK_K          = 2        # Stage 2 — reduced to keep context window small

CHUNK_SIZE    = 1500       # Slightly larger to keep full entries intact
CHUNK_OVERLAP = 100        # Reduced — entries are self-contained

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
            model="llama-3.3-70b-versatile",  # faster than 70b — swap to llama-3.3-70b-versatile for production
            temperature=0,
            request_timeout=60,      # fail fast instead of hanging forever
            max_retries=2,
        )
    raise ValueError(f"Unknown SELECTED_LLM: '{SELECTED_LLM}'. Use 'groq' or 'gemini'.")


# ──────────────────────────────────────────────────────────────
# 3. UI HELPERS
# ──────────────────────────────────────────────────────────────

def print_header(bot_name: str) -> None:
    print("\n" * 3)  # just add spacing instead of wiping the terminal
    #os.system("cls" if os.name == "nt" else "clear")
    w = 60
    print("=" * w)
    print(bot_name.center(w))
    print("=" * w)
    print(f"  STATUS  : ONLINE")
    print(f"  MODEL   : {SELECTED_LLM.upper()}")
    print(f"  MEMORY  : ACTIVE (Session Based)")
    print("=" * w)
    print("  Commands: 'exit' | 'audit' | 'clear' | 'reingest'")
    print("=" * w)


def print_audit_log(docs: list, stage: str, context_chars: int) -> None:
    print(f"\n=== [AUDIT] stage={stage} | chunks={len(docs)} | context={context_chars} chars ===")
    for i, doc in enumerate(docs):
        source = os.path.basename(doc.metadata.get("source", "Unknown"))
        page   = doc.metadata.get("page", "N/A")
        score  = doc.metadata.get("relevance_score", "N/A")
        if isinstance(page, int):
            page += 1
        preview = doc.page_content.replace("\n", " ")[:120]
        print(f"  [{i+1}] {source} | pg {page} | score {score}")
        print(f"       {preview}...")
    print("=" * 60 + "\n")
    input("  [Press Enter to continue...]")  # ← pause here so you can read it
    print()

# ──────────────────────────────────────────────────────────────
# 4. DATA INGESTION
# ──────────────────────────────────────────────────────────────

def ingest_data(folder_path: str, persist_dir: str) -> Chroma:
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
        return None
    print(f"[INGEST] Loading done in {time.time() - t0:.1f}s")

    # ── Split ────────────────────────────────────────────────
    t1 = time.time()
    # Entry-aware separators — respects knowledge.md --- boundaries first
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n---\n",   # knowledge.md entry boundary — always split here first
            "\n## ",     # H2 headings
            "\n\n",      # paragraphs
            "\n",
            " ",
        ],
    )
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
    return vector_db


def load_vectorstore(persist_dir: str) -> Chroma:
    t0 = time.time()
    print(f"[DB] Loading vector store from '{persist_dir}'...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    db = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
    print(f"[DB] Loaded in {time.time() - t0:.1f}s")
    return db


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
    Resolve known aliases in the query before retrieval.
    This ensures Chroma searches on canonical terms, not aliases.
    """
    replacements = {
        # Integration Suite aliases — expand to canonical CPI terms
        "SCI"  : "SAP Cloud Integration CPI",
        "SCPI" : "SAP Cloud Integration CPI",

        # SuccessFactors aliases
        "SFSF" : "SuccessFactors Employee Central",
        "SF"   : "SuccessFactors Employee Central",
        "EC"   : "Employee Central SuccessFactors",

        # Other systems
        "S4"   : "S/4HANA S/4",
        "ECP"  : "Employee Central Payroll",
        "BIB"  : "Business Integration Builder replication",
        "PTP"  : "Point-to-Point replication",
        "SCC"  : "SAP Cloud Connector",

        # Too short — matches common English words
        # "IS"  : "SAP Integration Suite",
    }

    expanded = query
    for alias, full_name in replacements.items():
       
        # Word boundary match — avoids replacing partial words
        expanded = re.sub(rf'\b{alias}\b', full_name, expanded, flags=re.IGNORECASE)

    # ── Deduplicate consecutive repeated words ───────────────
    # Handles cases like "replication replication" or "CPI CPI"
    # that occur when the query already contains the expanded term
    expanded = re.sub(r'\b(\w+)\s+\1\b', r'\1', expanded, flags=re.IGNORECASE)

    # Log if query was changed so you can see it working
    if expanded != query:
        print(f"[QUERY] Expanded: '{query}' → '{expanded}'")

    return expanded

def build_retriever(vector_db: Chroma):
    """
    Hybrid two-stage retriever with explicit relevance scoring.

    Stage 1 — Threshold: scores every chunk and only keeps those
              above THRESHOLD_SCORE. Ensures strict grounding.

    Stage 2 — Top K fallback: fires only when Stage 1 returns nothing.
              Prevents silent empty-context failures on valid questions
              that score slightly below the threshold.

    Scores are attached to doc.metadata so the audit log can display them.
    Returns a callable: query -> (docs, stage_label)
    """

    def retrieve(query: str) -> tuple[list, str]:

        # Resolve aliases before Chroma sees the query
        expanded_query = expand_query(query)

        # ── Stage 1 ────────────────────────────────────────────────────
        # similarity_search_with_relevance_scores returns (doc, score) pairs
        # where score is 0.0 (no match) to 1.0 (perfect match)
        results = vector_db.similarity_search_with_relevance_scores(
            expanded_query, k=THRESHOLD_K
        )

        threshold_docs = []
        for doc, score in results:
            # Attach score to metadata so print_audit_log can display it
            doc.metadata["relevance_score"] = round(score, 3)
            # Only keep chunks that meet the minimum confidence bar
            if score >= THRESHOLD_SCORE:
                threshold_docs.append(doc)

        # If at least one chunk passed the threshold, return immediately
        if threshold_docs:
            return threshold_docs, "THRESHOLD"

        # ── Stage 2 ────────────────────────────────────────────────────
        # Fires only when zero chunks passed Stage 1.
        # Returns best available chunks regardless of score.
        # Caller will warn the user that confidence is lower.
        fallback_results = vector_db.similarity_search_with_relevance_scores(
            expanded_query, k=TOPK_K
        )

        fallback_docs = []
        for doc, score in fallback_results:
            # Still attach scores so audit log is consistent across both stages
            doc.metadata["relevance_score"] = round(score, 3)
            fallback_docs.append(doc)

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
3. If the context does not contain the answer, reply with exactly: "I do not have enough information in your Knowledge Base to answer this."

### PHASE 3: RESPONSE RULES
1. Use clean Markdown with headings and bold for emphasis. Use asterisks for bullet points.
2. Use backticks for TCode names, entity names, field names, and technical IDs.
3. Never use hyphens or dash symbols in prose or email drafts.
4. Never include emojis in code, scripts, or technical configurations.
5. If the context contains URLs, SAP Notes, or Google Drive links, include them exactly as written under a References section.

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
    # this avoids a second retrieval call inside the chain.
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

    # ── Re-ingest flag — pass --reingest to wipe and rebuild db ──
    parser = argparse.ArgumentParser()
    parser.add_argument("--reingest", action="store_true", help="Wipe and rebuild the vector store")
    args = parser.parse_args()

    if args.reingest and os.path.exists(DB_DIR):
        print("[DB] --reingest flag detected. Wiping existing database...")
        shutil.rmtree(DB_DIR)


    vector_db = (
        ingest_data(DATA_PATH, DB_DIR)
        if not os.path.exists(DB_DIR)
        else load_vectorstore(DB_DIR)
    )

    if not vector_db:
        print("[ERROR] Vector store could not be initialised. Exiting.")
        sys.exit(1)

    retriever = build_retriever(vector_db)
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
            if query.lower() == "reingest":
                print("[DB] Wiping and rebuilding vector store...")
                shutil.rmtree(DB_DIR)
                vector_db = ingest_data(DATA_PATH, DB_DIR)
                retriever = build_retriever(vector_db)
                chain     = build_rag_chain(vector_db)
                print("[DB] Done. Ready.")
                continue

            # ── Retrieval ────────────────────────────────────
            docs, stage = retriever(query)

            # Calculate context size before sending to LLM
            context_chars = sum(len(d.page_content) for d in docs)

            # Always show retrieval summary so you can monitor without full audit
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

            # Warn when Top K fallback fires — confidence is lower
            if stage == "TOPK_FALLBACK":
                print("[RETRIEVER] Low confidence match — answer may be approximate.")

            # Warn if context is large — likely cause of slow LLM responses
            if context_chars > 4000:
                print(f"[WARN] Large context ({context_chars} chars) — response may be slow on free tier.")

            # ── LLM Inference ────────────────────────────────
            print("Thinking...\n")
            t_llm = time.time()

            response = chain.invoke(
                {"question": query, "docs": docs},
                config={"configurable": {"session_id": SESSION_ID}},
            )

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