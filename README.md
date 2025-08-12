# Bookly: A Modern Book Review & Community Platform API

Bookly is a feature-rich, secure, and scalable backend API for a book review and community platform, built with modern Python and top-notch architectural patterns. It provides a complete foundation for user management, authentication, book cataloging, reviews, and community-driven tagging.

---

## Core Features

This project is a complete, production-ready backend system with a full suite of features:

###  Authentication & Security
- **JWT-Based Authentication:** Secure, stateless authentication using JSON Web Tokens.
- **Refresh Token Rotation:** Top-notch security pattern where refresh tokens are single-use, automatically revoking the old token upon refresh to prevent theft.
- **Secure Password Management:** State-of-the-art password hashing using `passlib` with automatic re-hashing for future-proofing.
- **Complete Auth Flows:** Full implementation of signup, login, secure logout, password change, and a two-step "forgot password" reset flow.
- **Email Management:** Secure, two-step flows for both initial email verification and for changing a user's email address.
- **Role-Based Access Control (RBAC):** Hierarchical roles (`USER`, `MODERATOR`, `ADMIN`) with a clean dependency system for protecting endpoints.
- **Brute-Force Protection:** Rate limiting on login and other sensitive endpoints to prevent automated attacks.

### User & Admin Management
- **Self-Service Profile Management:** Users can fetch and update their own profiles (`/users/me`).
- **Account Deactivation:** Users can "soft delete" their own accounts.
- **Comprehensive Admin Panel:** A separate, secure set of endpoints for administrators to manage the entire platform, including:
  - Listing all users with advanced filtering.
  - Updating any user's profile.
  - Changing a user's role.
  - Deactivating and activating user accounts.
  - Permanently deleting users and all their associated content (books, reviews, etc.).

### Books, Reviews, & Tags
- **Full CRUD for Books:** Create, read, update, and delete books.
- **Full CRUD for Reviews:** Users can create, read, update, and delete their own reviews for books.
- **Community-Driven Tagging:**
  - Users can add tags to any book.
  - Tags are created on-the-fly with a robust `get_or_create` pattern that handles race conditions.
  - Admins can manage and curate the official list of tags.
- **Engagement Features:**
  - Users can vote on whether a review was helpful or unhelpful.
  - An advanced "Related Tags" feature suggests other tags based on co-occurrence.
  - A placeholder "Tag Suggestions" feature for future AI/ML integration.
- **Powerful Querying:** Endpoints to fetch books by tag, reviews by book, and reviews by user, all with pagination and filtering.

---

## Architectural Overview

The project is built on a clean, scalable, and maintainable **Layered Architecture**. This strict separation of concerns is the core principle of the entire design.

-   **Endpoint Layer (`api/v1/endpoints/`):** The "thin controller." Its only job is to handle HTTP requests and responses. It uses dependencies to gather what it needs and makes a single call to the service layer. It contains no business logic.
-   **Service Layer (`services/`):** The "smart" brain of the application. This is where all the business logic, authorization rules, and orchestration of other components happens.
-   **Repository/CRUD Layer (`crud/`):** The "dumb" worker. This is the only layer that talks to the database. Its methods are simple, reusable database operations (Create, Read, Update, Delete). It contains no business logic.
-   **Model Layer (`models/`):** The single source of truth for our data structures, defining the database tables and relationships using SQLModel.

This pattern makes the application incredibly easy to test, maintain, and scale.

---

## Technology Stack

-   **Framework:** **FastAPI** for its high performance and modern `async` capabilities.
-   **ORM:** **SQLModel** (built on Pydantic and SQLAlchemy) for robust data validation and database interaction.
-   **Database:** **PostgreSQL** (via `asyncpg`), a powerful and reliable relational database.
-   **Migrations:** **Alembic** for managing database schema changes safely.
-   **Caching & Background Tasks:** **Redis** serves as both a high-performance cache for frequently accessed data and as the message broker for Celery.
-   **Background Worker:** **Celery** for offloading slow tasks (like sending emails) to a separate process, keeping the API fast and responsive.
-   **Testing:**
    -   **Pytest** for writing clean, effective unit and integration tests.
    -   **Schemathesis** for powerful, automated property-based testing that validates the API against its own OpenAPI schema, finding edge cases no human would think of.

---

## Project Structure


├── alembic/                  # Database migration scripts
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/      # API endpoint files (user.py, book.py, etc.)
│   │       └── api.py          # Main API router
│   ├── core/                   # Core application logic (config, security, exceptions)
│   ├── crud/                   # Repository/CRUD layer for database operations
│   ├── db/                     # Database session management
│   ├── models/                 # SQLModel data models (database tables)
│   ├── schemas/                # Pydantic schemas for API request/response validation
│   ├── services/               # Service layer for business logic
│   ├── tasks/                  # Celery task definitions
│   └── main.py                 # FastAPI application entrypoint
├── tests/                    # Pytest test suite
│   ├── api/                    # API integration tests
│   ├── services/               # Service layer unit tests
│   └── crud/                   # Repository layer integration tests
├── .env                      # Environment variables (local configuration)
├── celery_worker.py          # Entrypoint for the Celery worker
└── requirements.txt          # Project dependencies


---

## Setup and Installation

Follow these steps to get the project running locally.

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd bookly
    ```

2.  **Create and Activate Virtual Environment:**
    ```bash
    python -m venv venv
    .\venv\Scripts\Activate  # On Windows
    source venv/bin/activate # On macOS/Linux
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables:**
    * Create a file named `.env` in the project's root directory.
    * Copy the contents of `.env.example` (if provided) or add the following variables, replacing the values with your local setup (e.g., your database credentials, Mailtrap credentials for email testing):
    ```env
    DATABASE_URL="postgresql+asyncpg://user:password@localhost/bookly_db"
    JWT_SECRET_KEY="a_very_secret_key"
    # ... other variables for Redis, email, etc.
    ```

5.  **Run Database Migrations:**
    * Make sure your PostgreSQL and Redis servers are running.
    * Run the following command to create all the necessary tables in your database:
    ```bash
    alembic upgrade head
    ```

6.  **Run the Application:**
    * **FastAPI Server:**
        ```bash
        uvicorn app.main:app --reload
        ```
    * **Celery Worker (in a separate terminal):**
        ```bash
        # On Windows
        celery -A celery_worker.celery_app worker --loglevel=info -P eventlet

        # On macOS/Linux
        celery -A celery_worker.celery_app worker --loglevel=info
        ```

7.  **Access the API:**
    * **Swagger UI (Interactive Docs):** `http://localhost:8000/docs`
    * **ReDoc (Alternative Docs):** `http://localhost:8000/api/redoc`

---

## Running the Tests

The project includes a comprehensive test suite.

* **Run all tests:**
    ```bash
    pytest -v
    ```
---

## Key Concepts & Patterns Implemented

This project serves as a showcase for several top-notch, professional backend development patterns:

* **Stateless Authentication with JWTs:** Including secure Refresh Token Rotation.
* **Hierarchical Role-Based Access Control (RBAC):** A flexible and powerful system for managing user permissions.
* **Service-Led Orchestration:** A clean separation of concerns where "smart" services orchestrate "dumb" repositories.
* **Asynchronous Processing:** Using `async`/`await` throughout the stack for high performance.
* **Background Task Processing:** Offloading slow operations (like sending emails) to Celery to keep the API responsive.
* **Generic, Reusable Components:** The `BaseRepository` and `CacheService` are designed to be reusable for any model, demonstrating a DRY (Don't Repeat Yourself) approach.
* **Robust Error Handling:** A centralized exception handling system that provides clear, structured error responses for all scenarios.
* **Performance Optimization:** Strategic use of eager loading (`selectinload`) to prevent the "N+1 query problem" and a generic caching layer to reduce database load.
* **Database-Level Integrity:** Using `UniqueConstraint` and `CheckConstraint` to ensure data is always valid.
* **Property-Based Testing:** Using Schemathesis to automatically find edge cases and ensure the API adheres to its own contract.
