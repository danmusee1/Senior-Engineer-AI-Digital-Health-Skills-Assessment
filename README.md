
## Last Mile Health Senior Full-Stack Engineer, AI & Digital Health — Practice Assessment

Welcome to the practice assessment for the Senior Full-Stack Engineer, AI & Digital Health position at Last Mile Health!

This project template provides a starting point for your submission. Please read the instructions carefully and follow the guidelines below.

---

### Project Overview

You are tasked with building a Retrieval-Augmented Generation (RAG) application using the provided starter code. The stack includes:

- **Frontend:** Next.js (React)
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL

You may substitute the frontend or backend with frameworks you are more comfortable with, as long as the core requirements are met.
you are also free to use chainlit for the chat interface.

---

### Requirements

Your application must include:

1. **Chat Interface Page:**
	- A user-friendly chat UI for interacting with the RAG system.

2. **PDF Upload Page:**
	- A page that allows users to upload PDF documents for ingestion.

3. **Clear Local Run Instructions:**
	- Step-by-step instructions for running the application locally (see below).

4. **Production Deployment Plan:**
	- A brief outline of how you would deploy this application to production (cloud provider, CI/CD, etc.).

**Bonus:**
- Add automated tests for backend and/or frontend.
- Document any architectural decisions or trade-offs.

---

### Submission Guidelines

- Submit your completed project as a **.zip file** or provide a **link to your GitHub repository**.
- You have **2 days** to complete and submit your solution.

---

### How to Run the Project Locally

1. **Build and start all services:**

	```sh
	docker compose -p assessment up -d --build
	```

2. **Access the application:**
	- Frontend: [http://localhost:3000](http://localhost:3000)
	- Backend (API): [http://localhost:5000](http://localhost:5000)

3. **Stop all services:**

	```sh
	docker compose -p assessment down
	```

---

### Production Deployment Plan (Example)

Provide a short plan describing how you would deploy this application to production. For example:

- Use a cloud provider (e.g., Azure, AWS, GCP) to host the frontend, backend, and database.
- Set up CI/CD pipelines for automated testing and deployment.
- Use managed database services and secure secrets management.
- Configure monitoring and logging for observability.

---

### Additional Notes

- Feel free to add more documentation or instructions as you progress.
- If you make architectural changes, document your reasoning.

Good luck!
