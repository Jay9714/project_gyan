# Project Gyan

**Project Gyan** is a sophisticated, microservices-based platform designed for comprehensive stock market analysis, prediction, and automation. It leverages modern AI/ML technologies, a robust backend architecture, and an interactive dashboard to provide actionable financial insights.

## 🚀 Features

*   **Advanced Stock Analysis**: Utilizes technical analysis libraries (`ta`) and machine learning models (`prophet`, `tensorflow`, `scikit-learn`) for trend prediction and market analysis.
*   **Microservices Architecture**: Modular design ensuring scalability and maintainability, separated into API, Worker, AI Engine, and Frontend layers.
*   **Interactive Dashboard**: A user-friendly Streamlit interface (**Darpan UI**) for visualizing stock data, model predictions, and system metrics.
*   **AI-Powered Insights**: Integrated **Ollama** support for local LLM-based financial reasoning and analysis (**Astra Brain**).
*   **Automated Workflows**: **n8n** integration (**Sutra Automation**) for orchestrating complex data pipelines and alerts.
*   **Robust Backend**: Built with **FastAPI** (**Setu API**), supported by **PostgreSQL** for persistence and **Redis** for caching and messaging.
*   **Background Processing**: **Celery** workers (**Chakra Scheduler**) for handling heavy computation and scheduled tasks asynchronously.

## 🏗 Architecture

The project is composed of the following containerized services:

| Service Name | Container Name | Description | Port |
| :--- | :--- | :--- | :--- |
| **Setu API** | `gyan_setu_api` | Core backend API built with FastAPI. Handles client requests and business logic. | `8000` |
| **Darpan UI** | `gyan_darpan_ui` | Frontend dashboard built with Streamlit. | `8501` |
| **Astra Brain** | `gyan_astra_brain` | AI & ML engine for running models and analysis. Connects to Ollama. | - |
| **Chakra Scheduler** | `gyan_chakra_scheduler` | Background worker for scheduled tasks and job processing. | - |
| **Sutra Automation** | `gyan_sutra_automation` | n8n workflow automation server. | `5678` |
| **Ollama** | `gyan_ollama` | Local Large Language Model server (requires GPU). | `11434` |
| **Database** | `gyan_db` | PostgreSQL 15 database. | `5432` |
| **Redis** | `gyan_redis` | Redis 7 for caching and task queues. | `6379` |

## 🛠 Prerequisites

*   **Docker** & **Docker Compose**: Essential for running the containerized services.
*   **NVIDIA GPU** (Optional but Recommended): For running local LLMs with Ollama efficiently.
*   **Python 3.10+**: For local development.

## 📦 Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone <repository_url>
    cd project_gyan
    ```

2.  **Environment Configuration**
    Ensure a `.env` file is present in the root directory. (Refer to `.env.example` if available).

3.  **Build and Run Services**
    Start the entire stack using Docker Compose:
    ```bash
    docker-compose up -d --build
    ```

    *This command will build the images for API, UI, Workers, and start the database, redis, and automation services.*

4.  **Database Migrations**
    The `migration` service automatically attempts to apply migrations on startup. To run them manually:
    ```bash
    # Create a new revision
    docker-compose run --rm migration alembic revision --autogenerate -m "Description"

    # Upgrade to head
    docker-compose run --rm migration alembic upgrade head
    ```

## 🖥 Usage

Once the services are up and running, you can access the various components:

*   **Darpan UI (Frontend)**: [http://localhost:8501](http://localhost:8501) - *Main Interface*
*   **Setu API (Swagger Docs)**: [http://localhost:8000/docs](http://localhost:8000/docs) - *API Testing*
*   **Sutra Automation (n8n)**: [http://localhost:5678](http://localhost:5678) - *Workflow Editor*

## 🔧 Development

### Project Structure
*   `services/` - Source code for individual services.
    *   `api_setu/` - FastAPI backend.
    *   `frontend_darpan/` - Streamlit frontend.
    *   `engine_astra/` - Core analysis logic and migrations.
    *   `worker_chakra/` - Background workers.
*   `shared/` - Shared code/libraries used across services.
*   `tests/` - Test suite.
*   `docker-compose.yml` - Orchestration configuration.

