# 🎫 Orbidi Ticketing System — Backend

System web of ticketing with: **FastAPI**, **PostgreSQL** and **Docker**.  
Allows you to create, manage and track incidents with authentication via Google OAuth 2.0.

---

## Table of contents

- [Stack tecnológico](#stack-tecnológico)
- [Arquitectura del proyecto](#arquitectura-del-proyecto)
- [Requisitos previos](#requisitos-previos)
- [Instalación y configuración](#instalación-y-configuración)
- [Variables de entorno](#variables-de-entorno)
- [Levantar el proyecto](#levantar-el-proyecto)
- [Migraciones con Alembic](#migraciones-con-alembic)
- [Endpoints disponibles](#endpoints-disponibles)
- [Autenticación con Google OAuth](#autenticación-con-google-oauth)
- [WebSockets y notificaciones en tiempo real](#websockets-y-notificaciones-en-tiempo-real)
- [Gestión de archivos adjuntos](#gestión-de-archivos-adjuntos)
- [Comandos útiles](#comandos-útiles)
- [Decisiones técnicas](#decisiones-técnicas)
- [Partes completadas y pendientes](#partes-completadas-y-pendientes)
- [Uso de IA en el desarrollo](#uso-de-ia-en-el-desarrollo)

---

## Stack tecnológico

| Capa              | Tecnología              | Versión |
| ----------------- | ----------------------- | ------- |
| Backend framework | FastAPI                 | 0.115.x |
| Servidor ASGI     | Uvicorn                 | 0.30.x  |
| ORM               | SQLAlchemy (async)      | 2.0.x   |
| Driver PostgreSQL | asyncpg                 | 0.30.x  |
| Migraciones       | Alembic                 | 1.13.x  |
| Base de datos     | PostgreSQL              | 16      |
| Caché / Pub-Sub   | Redis                   | 7       |
| Validación        | Pydantic v2             | 2.9.x   |
| Autenticación     | Google OAuth 2.0 + JWT  | —       |
| Contenedores      | Docker + Docker Compose | —       |

---

## Arquitectura del proyecto

```
orbidi-ticketing/
├── backend/
│   ├── app/
│   │   ├── main.py                  # Point of start FastAPI
│   │   ├── ai_tools.py               # Tools for the assistant Gemini
│   │   ├── core/
│   │   │   ├── config.py            # Settings (Pydantic BaseSettings)
│   │   │   ├── database.py          # Engine async + session
│   │   │   └── security.py          # JWT encode/decode
│   │   ├── models/                  # SQLAlchemy tables
│   │   ├── schemas/                 # Pydantic request/response
│   │   ├── routers/                 # Endpoints by domain (includes ai.py)
│   │   ├── services/                # Business logic (includes ai_service.py)
│   │   └── websockets/
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) >= 24.x
- [Docker Compose](https://docs.docker.com/compose/) >= 2.x (included in Docker Desktop)
- Google Cloud account with a project created (for OAuth 2.0)

> **It is not necessary** to have Python, PostgreSQL or Redis installed locally. Everything runs inside Docker.

---

## Installation and configuration

### 1. Clone the repository

```bash
git clone https://github.com/agarciactg/vortex-back.git
cd vortex-back
```

### 2. Configure the environment variables

```bash
cp .env.example .env
```

Edit the `.env` file with your credentials (see [Environment variables](#environment-variables)):

```bash
nano .env        # Linux / macOS
notepad .env     # Windows
```

### 3. Get Google OAuth 2.0 credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a project (or select an existing one)
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
4. Application type: **Web application**
5. Add in **Authorized redirect URIs**:
   ```
   http://localhost:8000/api/v1/auth/google/callback
   ```
6. Copy the **Client ID** and **Client Secret** in your `.env`

### 4. Get API Key from Google AI Studio (Gemini)

The intelligent assistant uses the `gemini-flash-latest` model.

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create an **API Key** (it's free for personal/development use)
3. Copy the value in the `GEMINI_API_KEY` variable of your `.env`

---

## Environment variables

| Variable               | Description                                          | Default value           |
| ---------------------- | ---------------------------------------------------- | ----------------------- |
| `POSTGRES_USER`        | PostgreSQL user                                      | `orbidi`                |
| `POSTGRES_PASSWORD`    | PostgreSQL password                                  | `orbidi123`             |
| `POSTGRES_DB`          | Database name                                        | `orbidi_tickets`        |
| `SECRET_KEY`           | Secret key for signing JWTs (min. 32 chars)          | — **obligatorio** —     |
| `GOOGLE_CLIENT_ID`     | Google OAuth Client ID                               | — **obligatorio** —     |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret                           | — **obligatorio** —     |
| `GEMINI_API_KEY`       | API Key from Google AI Studio (for assistant)        | — **obligatorio** —     |
| `FRONTEND_URL`         | URL of frontend (for CORS)                           | `http://localhost:3000` |
| `ENVIRONMENT`          | Execution environment (`development` / `production`) | `development`           |

Example of `.env` complete:

```env
# Database
POSTGRES_USER=orbidi
POSTGRES_PASSWORD=orbidi123
POSTGRES_DB=orbidi_tickets

# Security
SECRET_KEY=mi_clave_super_secreta_de_minimo_32_caracteres

# Google OAuth 2.0
GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx

# Gemini AI
GEMINI_API_KEY=AIzaSyAxxxxxxxxxxxxxxxxxxxx

# Frontend
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

---

## Start the project

### First time (build + run)

```bash
# Build images and start all services
docker compose up --build -d

# Verify that the three services are running
docker compose ps
```

You should see something like this:

```
NAME              STATUS          PORTS
orbidi_db         Up (healthy)    0.0.0.0:5432->5432/tcp
orbidi_redis      Up (healthy)    0.0.0.0:6379->6379/tcp
orbidi_backend    Up              0.0.0.0:8000->8000/tcp
```

### Verify that it works

```bash
curl http://localhost:8000/health
# {"status":"ok","app":"Orbidi Ticketing"}
```

### Available URLs

| Service                       | URL                          |
| ----------------------------- | ---------------------------- |
| API REST                      | http://localhost:8000        |
| Swagger UI (interactive docs) | http://localhost:8000/docs   |
| ReDoc                         | http://localhost:8000/redoc  |
| Health check                  | http://localhost:8000/health |

### View logs in real time

```bash
# All services
docker compose logs -f

# Only the backend
docker compose logs -f backend

# Only the database
docker compose logs -f db
```

### Stop the project

```bash
# Stop keeping the data
docker compose down

# Stop and remove all volumes (deletes the database)
docker compose down -v
```

---

## Migrations with Alembic

Alembic manages the evolution of the database schema in a controlled and versioned way. **All Alembic commands are executed inside the backend container.**

### Initialize Alembic (only the first time)

If you are configuring the project from scratch and the `alembic/` folder does not exist yet:

```bash
docker compose exec backend alembic init alembic
```

Then edit `backend/alembic/env.py` to connect with your models:

```python
# alembic/env.py — key fragment to modify
from app.core.config import settings
from app.core.database import Base

# Import all models so Alembic detects them
from app.models import user, ticket, comment, attachment, notification, ai_conversation, ai_message

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"))

target_metadata = Base.metadata
```

> **Note:** Alembic uses the synchronous driver (`psycopg2`) for migrations, even though the app uses `asyncpg` at runtime.

---

### Workflow with migrations

#### Create a new migration (autogenerated from models)

```bash
docker compose exec backend alembic revision --autogenerate -m "descripcion_del_cambio"
```

Examples:

```bash
# Initial migration with all tables
docker compose exec backend alembic revision --autogenerate -m "initial_tables"

# Adding a new field
docker compose exec backend alembic revision --autogenerate -m "add_due_date_to_tickets"

# Adding a new table
docker compose exec backend alembic revision --autogenerate -m "add_tags_table"
```

This generates a file in `alembic/versions/` like:

```
alembic/versions/
└── 20240115_1430_abc123def456_initial_tables.py
```

> ⚠️ **Always review** the generated file before applying it. Alembic may not correctly detect some changes (renaming columns, changes in constraints, etc.).

---

#### Apply all pending migrations

```bash
docker compose exec backend alembic upgrade head
```

#### Apply only the next migration

```bash
docker compose exec backend alembic upgrade +1
```

#### Rollback the last migration

```bash
docker compose exec backend alembic downgrade -1
```

#### Rollback to a specific version

```bash
# Get the ID from the version file (first 12 chars)
docker compose exec backend alembic downgrade abc123def456
```

#### Rollback all (back to initial state)

```bash
docker compose exec backend alembic downgrade base
```

---

### Inspect migration status

```bash
# See the currently applied version in the database
docker compose exec backend alembic current

# See the history of all migrations (from most recent to oldest)
docker compose exec backend alembic history --verbose

# See which migrations are pending to apply
docker compose exec backend alembic heads
```

---

### Manual migration (without autogeneration)

For changes that Alembic cannot detect automatically:

```bash
# Create an empty migration file
docker compose exec backend alembic revision -m "custom_migration_description"
```

Then manually edit the generated file:

```python
# alembic/versions/xxxx_custom_migration_description.py

def upgrade() -> None:
    op.add_column('tickets', sa.Column('due_date', sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column('tickets', 'due_date')
```

---

### Recommended workflow in development

```bash
# 1. Modify a model in app/models/
# 2. Generate the migration
docker compose exec backend alembic revision --autogenerate -m "describe_your_change"

# 3. Review the generated file in alembic/versions/
# 4. Apply the migration
docker compose exec backend alembic upgrade head

# 5. Verify the status
docker compose exec backend alembic current
```

---

## Available endpoints

### Authentication

| Method | Endpoint                       | Description                   |
| ------ | ------------------------------ | ----------------------------- |
| `GET`  | `/api/v1/auth/google/login`    | Starts Google OAuth flow      |
| `GET`  | `/api/v1/auth/google/callback` | Google callback → returns JWT |
| `GET`  | `/api/v1/auth/me`              | Authenticated user profile    |
| `POST` | `/api/v1/auth/logout`          | Logs out                      |

### Users

| Method | Endpoint             | Description                       |
| ------ | -------------------- | --------------------------------- |
| `GET`  | `/api/v1/users`      | List all users (for reassignment) |
| `GET`  | `/api/v1/users/{id}` | User detail                       |

### Tickets

| Method   | Endpoint                      | Description                                |
| -------- | ----------------------------- | ------------------------------------------ |
| `GET`    | `/api/v1/tickets`             | List tickets (with filters and pagination) |
| `POST`   | `/api/v1/tickets`             | Create new ticket                          |
| `GET`    | `/api/v1/tickets/{id}`        | Ticket detail                              |
| `PATCH`  | `/api/v1/tickets/{id}`        | Update ticket (status, priority, etc.)     |
| `DELETE` | `/api/v1/tickets/{id}`        | Delete ticket                              |
| `PATCH`  | `/api/v1/tickets/{id}/assign` | Reassign ticket to another user            |

### Comments

| Method   | Endpoint                                     | Description               |
| -------- | -------------------------------------------- | ------------------------- |
| `GET`    | `/api/v1/tickets/{id}/comments`              | List comments of a ticket |
| `POST`   | `/api/v1/tickets/{id}/comments`              | Add comment               |
| `DELETE` | `/api/v1/tickets/{id}/comments/{comment_id}` | Delete comment            |

### Attachments

| Method   | Endpoint                                             | Description                    |
| -------- | ---------------------------------------------------- | ------------------------------ |
| `GET`    | `/api/v1/tickets/{id}/attachments`                   | List attachments of a ticket   |
| `POST`   | `/api/v1/tickets/{id}/attachments`                   | Upload attachment (max. 10 MB) |
| `GET`    | `/api/v1/tickets/{id}/attachments/{att_id}/download` | Download attachment            |
| `DELETE` | `/api/v1/tickets/{id}/attachments/{att_id}`          | Delete attachment              |

### Notifications

| Method  | Endpoint                             | Description                            |
| ------- | ------------------------------------ | -------------------------------------- |
| `GET`   | `/api/v1/notifications`              | List user notifications                |
| `PATCH` | `/api/v1/notifications/{id}/read`    | Mark notification as read              |
| `PATCH` | `/api/v1/notifications/read-all`     | Mark all as read                       |
| `GET`   | `/api/v1/notifications/unread-count` | Number of unread notifications (badge) |

### WebSocket

| Protocol | Endpoint        | Description                     |
| -------- | --------------- | ------------------------------- |
| `WS`     | `/ws/{user_id}` | Real-time notifications channel |

### Artificial Intelligence (Gemini)

| Method | Endpoint          | Description                        |
| ------ | ----------------- | ---------------------------------- |
| `POST` | `/api/v1/ai/chat` | Send a message to the AI assistant |

> The complete interactive documentation is available at **http://localhost:8000/docs**

---

## Automated Tests (Pytest)

The backend has a comprehensive test suite that covers authentication, tickets, users, notifications, and service logic.

### Testing strategy:

- **Isolation**: An **in-memory SQLite** database is used for each test session, ensuring tests are fast and do not affect development data.
- **Mocks**: External dependencies like Redis are mocked to ensure tests are deterministic.
- **Async**: Fully asynchronous tests using `pytest-asyncio`.

### Run the tests:

You must run the commands inside the Docker container:

```bash
# Run all tests
docker compose exec backend pytest -v

# Run tests with coverage report
docker compose exec backend pytest --cov=app tests/
```

---

## Google OAuth Authentication

The authentication flow is as follows:

```
Frontend                          Backend                        Google
   |                               |                               |
   |-- GET /auth/google/login ---->|                               |
   |                               |-- redirect ------------------>|
   |                               |                               |
   |                               |<-- callback + code -----------|
   |                               |                               |
   |                               |-- exchange code for token --->|
   |                               |<-- user info -----------------|
   |                               |                               |
   |                               |-- upsert user en DB           |
   |                               |-- genera JWT propio           |
   |<-- JWT token -----------------|                               |
   |                               |                               |
   |-- peticiones con JWT -------->|                               |
```

All protected routes require the header:

```
Authorization: Bearer <jwt_token>
```

---

## WebSockets and real-time notifications

The backend uses **Redis Pub/Sub** to distribute events between WebSocket connections:

```
Event (ej: ticket assigned)
        ↓
  notification_service.py
        ↓
  Publishes to Redis channel "notifications:{user_id}"
        ↓
  WebSocket manager receives the message
        ↓
  Sends to the connected client via WS
```

Connection from the frontend:

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/${userId}?token=${jwtToken}`);
ws.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  // { type: "ticket_assigned", message: "...", ticket_id: "..." }
};
```

---

## File attachments management

- Files are stored locally in the Docker volume `uploads_data` (mounted in `/app/uploads`)
- Maximum file size: **10 MB**
- Allowed types: images (jpg, png, gif, webp), documents (pdf, doc, docx), spreadsheets (xls, xlsx), text (txt, md)
- Files are served as static files from `/uploads/{filename}`
- In production, it is recommended to migrate to **AWS S3** or **Google Cloud Storage**

---

## Useful commands

```bash
# Rebuild only the backend (after changing requirements.txt)
docker compose up -d --build backend

# Enter the backend container (interactive shell)
docker compose exec backend bash

# Run Python commands directly
docker compose exec backend python -c "from app.core.config import settings; print(settings.DATABASE_URL)"

# Connect to PostgreSQL
docker compose exec db psql -U orbidi -d orbidi_tickets

# List tables in psql
\dt

# View table schema
\d tickets

# Clear Redis cache
docker compose exec redis redis-cli FLUSHALL

# View Redis stats
docker compose exec redis redis-cli INFO stats
```

---

## Technical decisions

### Why FastAPI?

FastAPI offers native support for `async/await`, automatic OpenAPI documentation generation, and validation with Pydantic v2. It is the preferred option of the prompt and the most suitable for a system with WebSockets and high concurrency.

### Why SQLAlchemy async?

Allows non-blocking database operations using `asyncpg`, which is essential for maintaining performance with open WebSockets simultaneously.

### Why Redis?

Used for two purposes: as a Pub/Sub backend to distribute notification events between server instances, and as a cache for sessions and high-frequency data.

### Why UUID instead of integers as PK?

UUIDs avoid resource enumeration in the API and facilitate the future distribution of the system in multiple instances.

### Local file storage

For development, attachments are stored in a Docker volume. In production, it is recommended to migrate to **AWS S3** or **Google Cloud Storage**, changing only the implementation of `attachment_service.py` without modifying the endpoints.

### Own JWT instead of Google sessions

Once Google OAuth is completed, the backend issues its own JWT. This decouples the system from Google (the Google token expires, the own one does not necessarily) and allows adding other OAuth providers in the future.

---

## Completed and pending parts

### ✅ Completed

- Project structure and Docker configuration
- Database models (User, Ticket, Comment, Attachment, Notification)
- Alembic configuration for migrations
- CORS, middleware, and lifespan configuration
- Routers and services for each domain (complete CRUD)
- Complete Google OAuth 2.0 authentication
- WebSocket manager with Redis Pub/Sub
- AI assistant with tool calling (Gemini)
- Unit and integration tests (Pytest)

### 🚧 In progress / Pending

- Production migration (AWS/GCP)

---

## Use of AI in development

During the development of this test, the following AI tools were used:

| Tool                   | Use                                                                                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Claude (Anthropic)** | Initial scaffolding of the project structure, generation of SQLAlchemy models, design of the WebSocket architecture with Redis Pub/Sub, and review of technical decisions |
| **GitHub Copilot**     | Autocompletion of repetitive code (Pydantic schemas, CRUD patterns)                                                                                                       |

All generated code was reviewed, understood, and adjusted manually. Architectural decisions (stack, folder structure, design patterns) were made by the developer with support from AI tools as assistants, not as authors.
