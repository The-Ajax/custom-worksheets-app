# Custom Worksheets App

A web application that allows students to generate personalized worksheets to help them study more effectively.

The backend is built with FastAPI and fully dockerized so it can be run consistently on any machine or server that has Docker installed.

---

## Requirements

- Docker
- Docker Compose

No local Python installation is required.

---

### Environment Variables

Create a `.env` file in the project root.
You can use `.env.example` as a reference.

Example:

```
OPENAI_API_KEY="sk-proj..."
SECRET_KEY="change-me"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Running the App

Build and start the application using Docker Compose:

```bash
docker compose up --build
````

The app will be available at:

```
http://localhost:8000
```

---

## Stopping the App

To stop and remove the containers:

```bash
docker compose down
```

---
## Notes

* Generated PDFs are stored in the `pdfs/` directory and are mounted as a Docker volume.
* SQLite is used by default.

---