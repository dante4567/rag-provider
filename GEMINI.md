# GEMINI.md

## Project Overview

This project is a production-oriented Retrieval-Augmented Generation (RAG) service. It's designed to be a cost-effective solution for small-to-medium teams, offering significant savings over commercial alternatives. The service is built with a modular architecture using Python, FastAPI, and Docker.

**Key Technologies:**

*   **Backend:** FastAPI (Python)
*   **Vector Store:** ChromaDB
*   **Document Processing:** Unstructured.io, PyPDF2, python-docx, and others.
*   **LLM Integration:** LiteLLM, with support for Groq, Anthropic, OpenAI, and Google Gemini.
*   **Deployment:** Docker, with Nginx as a reverse proxy.
*   **OCR:** Tesseract

**Architecture:**

The application is containerized using Docker and consists of three main services:

1.  `rag-service`: The core FastAPI application that handles document ingestion, processing, and API endpoints.
2.  `chromadb`: The vector database used to store document embeddings.
3.  `nginx`: A reverse proxy for the `rag-service`.

## Project Status (as of 2025-10-15)

*   **Deployment Status:** Production-ready (Grade A-, 93/100)
*   **CI/CD Status:** Configured, awaiting activation.
*   **Test Coverage:** 100% pass rate (955 tests total).

## Building and Running

The project is designed to be run with Docker Compose.

**1. Prerequisites:**

*   Docker and Docker Compose must be installed.
*   API keys for the desired LLM providers (e.g., Groq, Anthropic, OpenAI) are required.

**2. Setup:**

```bash
# Clone the repository
git clone <repo> && cd rag-provider

# Create a .env file from the example
cp .env.example .env

# Add your API keys to the .env file
# Example:
# GROQ_API_KEY=your_groq_api_key
# ANTHROPIC_API_KEY=your_anthropic_api_key
# OPENAI_API_KEY=your_openai_api_key
```

**3. Running the Application:**

```bash
# Start the services in detached mode
docker-compose up -d
```

**4. Interacting with the API:**

*   **Ingest a file:**
    ```bash
    curl -X POST -F "file=@/path/to/your/doc.pdf" http://localhost:8001/ingest/file
    ```
*   **Search for a query:**
    ```bash
    curl -X POST -H "Content-Type: application/json" \
      -d \'\'\'{"text": "your question"}\'\'\' http://localhost:8001/search
    ```
*   **Chat with RAG:**
    ```bash
    curl -X POST -H "Content-Type: application/json" \
      -d \'\'\'{"question": "What is X?"}\'\'\' http://localhost:8001/chat
    ```

**5. Stopping the Application:**

```bash
docker-compose down
```

## Development Conventions

*   **Modular Design:** The application is structured into services and modules. The main application logic is in `app.py`, with services like `RAGService`, `LLMService`, and `DocumentProcessor` encapsulating specific functionalities.
*   **Dependency Management:** Python dependencies are managed with a `requirements.txt` file.
*   **Configuration:** Application configuration is handled through environment variables, with defaults provided in the `docker-compose.yml` file. Sensitive information like API keys is managed in a `.env` file.
*   **API:** The API is built with FastAPI and follows RESTful principles. Pydantic models are used for data validation.
*   **Testing:** The project has a comprehensive test suite with a 100% pass rate. Tests are located in the `tests` directory and are run using `pytest`. The `README.md` file contains detailed instructions on how to run the tests.
