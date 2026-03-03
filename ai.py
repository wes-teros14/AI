import os
import sys

# type 'clear' on terminal to wipe conversation memory and start fresh

# TECH: Standard Loaders and Environment
from dotenv import load_dotenv

# TECH: LangChain Core components for Prompt and Chain construction
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import BaseMessage
from langchain_core.runnables.history import RunnableWithMessageHistory

# TECH: Memory components to handle session history
from langchain_community.chat_message_histories import ChatMessageHistory

# TECH: Document Loaders for PDF, Word, and Excel files
from langchain_community.document_loaders import (
    PyPDFLoader, 
    Docx2txtLoader, 
    UnstructuredExcelLoader,
    TextLoader,
    DirectoryLoader
)

# TECH: Text Splitters and Embedding models for RAG
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# TECH: LLM Chat Models (Google Gemini and Groq Llama 3)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

# ==========================================
# 1. CONFIGURATION & ENVIRONMENT
# ==========================================
# TECH: Load API keys from the hidden .env file
load_dotenv()

# FUNC: Define where the "Brain" (Database) and "Knowledge" (Files) are stored
DB_DIR = "./db"
DATA_PATH = "data" 

# FUNC: Select the AI Personality/Model to use
# TECH: Toggle between 'groq' (Llama 3) or 'gemini' (Google)
SELECTED_LLM = "groq" 

# FUNC: Settings for how deep the bot searches in documents
# TECH: threshold increased to 0.3 to prevent keyword gap failures
SEARCH_K = 10
SEARCH_THRESHOLD = 0.1 #not used on top K method, only for similarity_score_threshold

# TECH: Global dictionary to store chat history objects by Session ID
session_store = {}

def get_llm():
    """
    FUNC: Wakes up the selected AI Brain.
    TECH: Returns an instance of ChatGoogleGenerativeAI or ChatGroq based on config.
    """
    if SELECTED_LLM == "gemini":
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            temperature=0  # TECH: 0 temperature ensures deterministic/strict answers
        )
    elif SELECTED_LLM == "groq":
        return ChatGroq(
            model="llama-3.3-70b-versatile", 
            temperature=0
        )

# ==========================================
# 2. UI & HELPER FUNCTIONS
# ==========================================
def print_header(bot_name):
    """
    FUNC: Displays a standard startup banner in the terminal.
    TECH: Uses os.system to clear screen and standard print statements.
    """
    os.system('cls' if os.name == 'nt' else 'clear')
    width = 60
    print("=" * width)
    print(f"{bot_name.center(width)}")
    print("=" * width)
    print(f"STATUS:  ONLINE")
    print(f"MODEL:   {SELECTED_LLM.upper()}")
    print(f"MEMORY:  ACTIVE (Session Based)")
    print("=" * width)

def print_audit_log(docs):
    """
    FUNC: Shows the user exactly what data the bot found in the files.
    TECH: Iterates through retrieved Document objects and prints metadata/content.
    """
    print("\n=== [AUDIT] RETRIEVED CONTEXT ===")
    for i, doc in enumerate(docs):
        source = os.path.basename(doc.metadata.get("source", "Unknown"))
        page = doc.metadata.get("page", "N/A")
        
        # TECH: Fix zero indexed page numbers for human readability
        if isinstance(page, int): page += 1
            
        preview = doc.page_content.replace('\n', ' ')[:100]
        print(f"[{i+1}] {source} (Pg {page}): {preview}...")
    print("===================================\n")

# ==========================================
# 3. DATA INGESTION ENGINE
# ==========================================
def ingest_data(folder_path, persist_dir):
    """
    FUNC: Scans the data folder and converts files into a searchable format.
    TECH: Uses DirectoryLoader > RecursiveSplitter > GoogleEmbeddings > ChromaDB.
    """
    print(f"Scanning {folder_path} for documents...")
    
    documents = []
    # TECH: Define loaders for specific file extensions
    loaders = [
        DirectoryLoader(folder_path, glob="**/*.pdf", loader_cls=PyPDFLoader),
        DirectoryLoader(folder_path, glob="**/*.docx", loader_cls=Docx2txtLoader),
        DirectoryLoader(folder_path, glob="**/*.xlsx", loader_cls=UnstructuredExcelLoader),
        DirectoryLoader(folder_path, glob="**/*.md", loader_cls=TextLoader),
    ]

    for loader in loaders:
        try:
            documents.extend(loader.load())
        except Exception as e:
            print(f"Error loading files: {e}")

    if not documents:
        print("No supported files found.")
        return None

    # FUNC: Cut documents into small pieces so the AI can read them efficiently.
    print(f"Splitting {len(documents)} documents...")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    chunks = splitter.split_documents(documents)

    # FUNC: Save the processed data into the Brain folder.
    print(f"Creating embeddings (Google) and storing in ChromaDB...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_dir
    )
    
    print("Ingestion Complete.")
    return vector_db

def load_vectorstore(persist_dir):
    """
    FUNC: Reloads the existing database to save startup time.
    TECH: Re initializes Chroma from disk with the same embedding function.
    """
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    return Chroma(persist_directory=persist_dir, embedding_function=embeddings)

# ==========================================
# 4. MEMORY MANAGEMENT
# ==========================================
def get_session_history(session_id: str) -> BaseMessage:
    """
    FUNC: Retrieves the conversation history for a specific user session.
    TECH: Checks session_store dict; creates new ChatMessageHistory if missing.
    """
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]

# ==========================================
# 5. RAG CHAIN CONSTRUCTION
# ==========================================
def build_rag_chain(vector_db):
    """
    FUNC: Builds the AI logic pipeline.
    """
    
    # A. The Retriever
    # retriever = vector_db.as_retriever(
    #     search_type="similarity_score_threshold",
    #     search_kwargs={
    #         "k": SEARCH_K, 
    #         "score_threshold": SEARCH_THRESHOLD
    #     }
    # )

    
    # Changed to industry standard Top K retrieval
    retriever = vector_db.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 3 
        }
    )

    # B. The LLM
    llm = get_llm()

    # C. The Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
### ROLE
You are the dedicated AI Assistant and External Brain for Wesley Ancog. You act as a Senior SAP Integration Consultant and Certified SAP GenAI Developer. Your logic and responses are strictly governed by the provided Personal Context.

### PHASE 1: KNOWLEDGE MAPPING & ALIAS RESOLUTION
1. Scan the {context} for Wesley's specific Markdown note types.
2. Apply the System Alias Logic automatically: Treat SF, SFSF, and SuccessFactors as identical. Treat CPI, SCI, and Integration Suite as identical.
3. Check the Date metadata. If two technical notes conflict, the note with the most recent date is the source of truth.

### PHASE 2: STRICT GROUNDING (ANTI HALLUCINATION)
1. The Context Wall: You MUST NOT use your general SAP training data to answer technical questions. 
2. Zero Assumption: If a Tcode, system, or troubleshooting step is not explicitly written in the {context}, DO NOT invent it or suggest it.
3. The Fallback: If the {context} does not contain the answer, you must reply with exactly this: "I do not have enough information in your Master Notes to answer this."

### PHASE 3: RESPONSE STYLE & STRICT CONSTRAINTS (CRITICAL)
1. Formatting: Use clean Markdown with Headings, Bolding for emphasis, and Asterisks (*) for Bullet Points. Use backticks (`` ` ``) for technical IDs, Tcodes, and entities.
2. Rule: You must NEVER use hyphens or the dash symbol when generating text, emails, sample responses, or standard prose.
3. Rule: You must NEVER include emojis in any generated code, scripts, or technical configurations.
4. Rule (Preservation): If the retrieved {context} contains any URLs, SAP Notes, or Google Drive links, you MUST include them exactly as written at the end of your response.

### OUTPUT FORMAT
* Knowledge Source: Briefly state the Tags and Type of the note used to generate the answer.
* Response: The direct technical answer derived ONLY from the context.
* Reference Links: Output any URLs or SAP Notes found in the context. (If none, omit this line).
* Consultant Insight: A high level architectural tip based ONLY on Wesley's previous notes.
* Next Action: A single, focused follow up question or task suggestion.

### PERSONAL CONTEXT
{context}
"""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    # D. Source Formatter
    def format_docs(docs):
        return "\n\n".join(
            f"[Source: {os.path.basename(doc.metadata.get('source', 'Unknown'))}] \n{doc.page_content}"
            for doc in docs
        )

    # E. The Chain (LCEL)
    chain = (
        {
            "context": (lambda x: x["question"]) | retriever | format_docs, 
            "question": lambda x: x["question"],
            "chat_history": lambda x: x["chat_history"] 
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain, retriever

# ==========================================
# 6. MAIN EXECUTION LOOP
# ==========================================
def main():
    # FUNC: Main entry point for the application.
    
    # === SETUP ===
    BOT_NAME = "Wes AI"
    SESSION_ID = "wes_session_01" 
    SHOW_AUDIT = False 

    if not os.path.exists(DB_DIR):
        vector_db = ingest_data(DATA_PATH, DB_DIR)
    else:
        vector_db = load_vectorstore(DB_DIR)

    if not vector_db: return

    rag_chain_base, retriever = build_rag_chain(vector_db)

    chain_with_history = RunnableWithMessageHistory(
        rag_chain_base,
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )

    print_header(BOT_NAME)
    print("Commands: 'exit' to quit, 'audit' to toggle logs, 'clear' to reset memory.")

    while True:
        try:
            query = input(f"\n[{BOT_NAME}] > ")
            
            # === COMMANDS ===
            if query.lower() in ['exit', 'quit']: break
            
            if query.lower() == 'audit':
                SHOW_AUDIT = not SHOW_AUDIT
                print(f"Audit Mode: {'ON' if SHOW_AUDIT else 'OFF'}")
                continue
                
            if query.lower() == 'clear':
                session_store[SESSION_ID] = ChatMessageHistory()
                print("Memory Wiped.")
                continue
            
            if not query.strip(): continue

            # === PRE FETCH & AUDIT ===
            docs = retriever.invoke(query)
            
            if SHOW_AUDIT:
                print_audit_log(docs)

            # === THE SAFETY NET (CIRCUIT BREAKER) ===
            if not docs:
                fallback_msg = "I do not have enough information in your Master Notes to answer this."
                print(f"\n{fallback_msg}")
                
                history = get_session_history(SESSION_ID)
                history.add_user_message(query)
                history.add_ai_message(fallback_msg)
                
                continue 

            # === INFERENCE (LLM CALL) ===
            print("Thinking...")
            
            response = chain_with_history.invoke(
                {"question": query},
                config={"configurable": {"session_id": SESSION_ID}}
            )

            print(f"\n{response}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()