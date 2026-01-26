import os
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import google.generativeai as genai
import chromadb
from chromadb.config import Settings
import PyPDF2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="GDG RAG Chatbot API",
    description="RAG chatbot for GDG college website using Gemini",
    version="1.0.0"
)

# Configure CORS - allow your frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://your-frontend-domain.vercel.app",  # Replace with your actual Vercel domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "default_secret_token")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize ChromaDB (persistent storage on disk)
CHROMA_DB_DIR = "./chroma_db"
chroma_client = chromadb.PersistentClient(
    path=CHROMA_DB_DIR,
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)

# Get or create collection
COLLECTION_NAME = "gdg_documents"
try:
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "GDG knowledge base documents"}
    )
    logger.info(f"Collection '{COLLECTION_NAME}' initialized with {collection.count()} documents")
except Exception as e:
    logger.error(f"Error initializing collection: {e}")
    raise

# Pydantic models
class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []

class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int

# Helper function: Verify admin token
def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify that the request has a valid admin token"""
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing admin token. Use header: x-admin-token"
        )
    return True

# Helper function: Extract text from PDF
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes"""
    try:
        pdf_reader = PyPDF2.PdfReader(file_bytes)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {str(e)}")

# Helper function: Chunk text
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks"""
    if not text:
        return []
    
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    
    return chunks

# Helper function: Generate embeddings with Gemini
def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using Gemini's embedding model"""
    try:
        embeddings = []
        for text in texts:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(result['embedding'])
        return embeddings
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")

# Helper function: Generate answer with Gemini
def generate_answer(question: str, context: str) -> str:
    """Generate answer using Gemini with context"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""You are a helpful assistant for a college GDG (Google Developer Group) website.
Answer the question based on the context provided. If the context doesn't contain relevant information,
say so politely and provide general guidance if possible.

Context:
{context}

Question: {question}

Answer:"""
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

# Routes

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "GDG RAG Chatbot API",
        "version": "1.0.0",
        "documents_count": collection.count()
    }

@app.post("/upload", response_model=UploadResponse, dependencies=[Depends(verify_admin_token)])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF document (ADMIN ONLY)
    Requires header: x-admin-token
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Read file
        contents = await file.read()
        
        # Extract text
        logger.info(f"Extracting text from {file.filename}")
        text = extract_text_from_pdf(contents)
        
        if not text:
            raise HTTPException(status_code=400, detail="No text could be extracted from the PDF")
        
        # Chunk text
        logger.info(f"Chunking text from {file.filename}")
        chunks = chunk_text(text)
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks created from text")
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        embeddings = generate_embeddings(chunks)
        
        # Create unique IDs for chunks
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ids = [f"{file.filename}_{timestamp}_chunk_{i}" for i in range(len(chunks))]
        
        # Metadata
        metadatas = [
            {
                "filename": file.filename,
                "chunk_index": i,
                "upload_time": timestamp
            }
            for i in range(len(chunks))
        ]
        
        # Add to ChromaDB
        logger.info(f"Adding {len(chunks)} chunks to ChromaDB")
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        
        logger.info(f"Successfully uploaded {file.filename} with {len(chunks)} chunks")
        
        return UploadResponse(
            message="Document uploaded successfully",
            filename=file.filename,
            chunks_added=len(chunks)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - answer questions using RAG
    Open to all users (no authentication required)
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        # Generate embedding for the question
        logger.info(f"Processing question: {request.question[:100]}...")
        question_embedding = genai.embed_content(
            model="models/text-embedding-004",
            content=request.question,
            task_type="retrieval_query"
        )['embedding']
        
        # Search ChromaDB for similar chunks
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=3  # Top 3 most relevant chunks
        )
        
        # Build context from retrieved chunks
        if results['documents'] and results['documents'][0]:
            context_chunks = results['documents'][0]
            context = "\n\n".join(context_chunks)
            
            # Get source filenames
            sources = []
            if results['metadatas'] and results['metadatas'][0]:
                sources = list(set([meta['filename'] for meta in results['metadatas'][0]]))
        else:
            context = ""
            sources = []
        
        # Generate answer
        if context:
            answer = generate_answer(request.question, context)
        else:
            answer = "I don't have enough information in my knowledge base to answer this question. Please make sure relevant documents have been uploaded, or try rephrasing your question."
        
        return ChatResponse(
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.get("/stats")
def get_stats():
    """Get database statistics (public endpoint)"""
    try:
        return {
            "total_documents": collection.count(),
            "collection_name": COLLECTION_NAME
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"error": str(e)}

# Run with: uvicorn main:app --reload --port 8000