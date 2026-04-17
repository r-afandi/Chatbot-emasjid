# eMasjid Chatbot System

A comprehensive Retrieval-Augmented Generation (RAG) chatbot system designed for eMasjid.id. This project features a FastAPI backend, Qdrant vector database, robust document processing, web scraping capabilities, and user-friendly web interfaces.

## Features

- AI Provider Support: Compatible with OpenRouter, OpenAI, and Anthropic.
- Vector Database: Integrated with Qdrant for semantic search and context retrieval.
- Data Ingestion: Supports uploading and processing PDF, DOCX, TXT, and CSV files.
- Web Scraping: Ability to scrape single URLs or process multiple links via XML Sitemaps.
- User Interfaces: Includes a dedicated Chatbot UI for end-users and a Knowledge Base Management UI for administrators.
- Persona Management: Automatically adjusts AI persona (Sales, CRM, Komplain) based on the retrieved context category.
- Conversation History: Tracks and stores user interactions and token usage.

## Project Components

- Backend API (app/main.py): The core FastAPI server handling AI logic, vector search, and file processing.
- Chatbot UI (chatbot_ui.py): A lightweight web interface for users to interact with the AI.
- Admin UI (ui_kategori.py): A web interface for administrators to manually input or upload (via Excel) knowledge base data.
- Knowledge Seeder (seed_knowledge.py): A script to initialize the vector database with base Q&A and document data.

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd chatbot-py
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

## Running the Application

### Local Development (Without Docker)

#### Using the batch script (Windows):
```cmd
start_local.bat
```

#### Manual setup:
1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the application:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using Docker

```bash
docker-compose up --build
```

## API Endpoints

- `POST /api/v1/ask` - Ask a question
- `POST /api/v1/upload-document` - Upload a document
- `GET /api/v1/conversations/{conversation_id}` - Get conversation history
- `GET /api/v1/health` - Health check

## Deployment Options

### Local Development
Run directly with uvicorn as shown above.

### Docker Containers
Use the provided Dockerfile and docker-compose.yml for containerized deployment.

### Cloud Platforms

#### AWS
1. Create an EC2 instance
2. Install Docker and Docker Compose
3. Deploy using docker-compose

#### GCP
1. Create a Compute Engine instance
2. Install Docker and Docker Compose
3. Deploy using docker-compose

#### Azure
1. Create a Virtual Machine
2. Install Docker and Docker Compose
3. Deploy using docker-compose

### Kubernetes Clusters
1. Create Kubernetes deployment files
2. Apply using kubectl:
```bash
kubectl apply -f kubernetes/
```

## Monitoring & Observability

The application is designed to integrate with:
- Prometheus for metrics
- OpenTelemetry for tracing
- ELK stack for logging
- Grafana for dashboards

## Configuration

All configuration is handled through environment variables in the `.env` file.

## License

MIT