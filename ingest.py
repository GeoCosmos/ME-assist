import pickle
from langchain_community.retrievers import BM25Retriever

import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY is missing from .env!")
    exit(1)

file_path = "./reference_docs/materials.txt"

if not os.path.exists(file_path):
    print(f"❌ ERROR: File not found at {file_path}")
    exit(1)

print("1. Loading document...")
loader = TextLoader(file_path, encoding="utf-8")
documents = loader.load()
print(f"    Loaded document content length: {len(documents[0].page_content)} characters")

print("2. Splitting text into chunks...")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = text_splitter.split_documents(documents)
print(f"    Created {len(chunks)} chunk(s).")

print("3. Creating Chroma database...")
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview",
    google_api_key=api_key,
    batch_size=10
)

vector_db = Chroma.from_documents(chunks, embeddings, persist_directory="./chroma_db")
print("✅ SUCCESS: RAG database created at ./chroma_db")

# --- ADDED CODE BELOW ---
print("4. Creating local BM25 keyword index...")
bm25_retriever = BM25Retriever.from_documents(chunks)

with open("bm25_retriever.pkl", "wb") as f:
    pickle.dump(bm25_retriever, f)

print("✅ SUCCESS: BM25 index saved to ./bm25_retriever.pkl")