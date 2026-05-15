# ai-workflow-qa-framework

![CI Pipeline Status](https://github.com/bbulson/ai-workflow-qa-framework/actions/workflows/ci.yml/badge.svg)

## 🎯 Project Purpose
This framework is a test automation suite for validating **Conversational AI** workflows within a **CPaaS (Communications Platform as a Service)** environment.

It focuses on API-level validation, browser-driven UI testing, structured logging, and data integrity checks, enabling reliable testing of AI-driven interactions. The framework supports mock-based testing, response validation, and persistent result tracking through both SQLite (local) and PostgreSQL (Docker/CI), making it adaptable for evolving AI workflows. This framework includes concurrent request simulation to evaluate latency and throughput under load, enabling validation of AI service performance in production-like conditions.

---

<details>
<summary><b>Click to view detailed Acceptance Criteria (Validation Targets)</b></summary>

### 1. Functional Integrity
* **AC 1:** The system must return a valid JSON response for all standard prompt requests.
* **AC 2:** The framework must gracefully handle non-standard inputs (emojis, long-string overflows) without service interruption.
* **AC 3:** API error handling must return appropriate 4xx/5xx status codes for malformed requests to ensure API reliability within CPaaS-style environments.

### 2. Performance & Scalability (SLA)
* **AC 4:** **Latency:** 95% of requests must complete with a total latency of < 500ms under a load of 5 concurrent users.
* **AC 5:** **Connectivity:** No more than 1% of requests should result in a connection timeout or handshake failure during peak burst testing.
* **AC 6:** **Stability:** The system must maintain a 100% success rate during regression cycles with simulated backend latency.

### 3. CI/CD Reliability
* **AC 7:** The pipeline must generate and attach a persistent HTML report for every build failure to ensure immediate observability.
* **AC 8:** The test suite must execute in under 5 minutes to maintain a fast feedback loop for the development team.

</details>

---

## 🛠 Tech Stack & Architecture

| Layer | Technology |
|---|---|
| **Language (Python)** | Python 3.11+ |
| **Language (UI Tests)** | C# / .NET 8 |
| **Test Runner (API)** | Pytest with dynamic fixtures and HTML reporting |
| **Test Runner (UI)** | Playwright for .NET with NUnit 4 and FluentAssertions |
| **Load Testing** | Apache JMeter 5.6.3 (cached in CI, locally executable) |
| **Mocking** | `requests-mock` (unit/integration) + Flask mock server with Postgres backend (E2E) |
| **Database** | SQLite (local dev) / PostgreSQL 16 (Docker & CI) |
| **Infrastructure** | Docker Compose — two Flask replicas, Nginx reverse proxy, PostgreSQL |
| **CI/CD** | GitHub Actions (Ubuntu-latest) |

---

## 🌟 Key Engineering Features

### 1. Dynamic Prompt Validation (Functional)
The framework uses a custom **Dynamic Mocking Engine** built on `requests-mock` with conditional response handling in `tests/conftest.py`. This simulates a backend AI agent, enabling robust testing of:
* **Input Edge Cases:** Validation of empty strings, `None` types, and multi-token overflows.
* **Character Handling:** Resilience testing for emojis, SQL injection strings, and non-Latin scripts.
* **Error States:** Verification of 400 (Bad Request) and 500 (Internal Server Error) handling.

### 2. Browser-Driven UI Testing (Playwright)
The `PlaywrightTests/` project runs a full end-to-end layer against the live chatbot UI using **Playwright for .NET** on Chromium (headless). Tests are organised into three categories:

* **`Category=Workflows`** — Validates the full chat UX: prompt submission, input clearing, multi-turn conversation history, and data-driven prompts sourced from `test_data/prompts.json` (the same file used by the Python suite).
* **`Category=API`** — Playwright `IAPIRequestContext` tests that hit the HTTP API directly, verifying JSON structure, status codes, and edge-case payloads without a browser.
* **`Category=HealthCheck`** — Fast smoke tests confirming service availability before the main suite runs.

`TestBase` captures screenshots and Playwright traces automatically on any test failure. Tests tagged `[Category("AlwaysTrace")]` also save a trace on success for targeted inspection.

### 3. Dual-Backend Data Persistence
The framework supports two database backends behind a shared interface:

* **SQLite** (local dev / unit tests) — each test gets an isolated on-disk file with WAL mode and a busy-timeout to prevent lock contention.
* **PostgreSQL 16** (Docker / CI) — each test wraps in a rolled-back transaction so no test data leaks between runs. The Docker stack runs two Flask replicas writing to the same Postgres instance; `test_db_integrity.py` verifies that data committed by one node is immediately visible from the other, confirming cross-node consistency under concurrent load.

### 4. Performance Guardrails (Load Testing)
Real-time AI communication cannot tolerate lag. The suite integrates **JMeter** directly into the deployment pipeline to:
* Simulate concurrent user bursts (e.g., 5–10 users with zero ramp-up).
* Monitor **Connect Latency** and **95th Percentile Response Times**.
* Run reliably in headless CI via a cached JMeter 5.6.3 installation.

### 5. Containerised Infrastructure
The full stack is defined in `docker-compose.yml`:
* **`flask-mock` × 2** — Two Flask replicas behind Nginx, accessible at `https://localhost:5000`. Used by Pytest and Playwright tests.
* **`flask-ai`** — A separate Flask server at `https://localhost:5001` with a higher token limit, used exclusively by JMeter performance tests.
* **`nginx`** — Reverse proxy with self-signed TLS certs generated at pipeline start.
* **`db`** — PostgreSQL 16 with a health-check gate; all dependent services wait for it to be ready before starting.

### 6. Pipeline Observability
The CI pipeline is designed for fast feedback and test visibility:
* Executes tests with immediate failure reporting to surface issues early.
* Includes timeout controls to prevent stalled or long-running executions.
* Exports Pytest HTML reports, Playwright `.trx` results, failure screenshots, and Playwright traces for post-run analysis.

---

## 🚀 Execution Guide

### CI/CD (Primary)
The preferred method of execution is via **GitHub Actions**. Every push to `main` triggers the full regression suite: Docker stack setup, Pytest functional tests, Playwright UI and API tests, and JMeter performance tests.
* Live logs and execution history can be viewed in the **Actions** tab of this repository.

### Local Development & Debugging

#### Python (Pytest) Tests
```bash
# Install dependencies
pip install -r requirements.txt

# Run against the mock (no Docker needed)
pytest tests/ -v -s --html=reports/report.html --self-contained-html
```

#### Playwright (.NET) Tests
```bash
# Restore and build
dotnet restore PlaywrightTests/PlaywrightTests.csproj
dotnet build PlaywrightTests/PlaywrightTests.csproj --no-restore

# Install Chromium
pwsh PlaywrightTests/bin/Debug/net8.0/playwright.ps1 install chromium

# Run all UI/API tests (requires the Docker stack running on https://localhost:5000)
dotnet test PlaywrightTests/PlaywrightTests.csproj --settings PlaywrightTests/.runsettings

# Run a specific category
dotnet test PlaywrightTests/PlaywrightTests.csproj --filter "Category=HealthCheck"
```

#### Full Stack (Docker)
```bash
# Generate TLS certs and start all services
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem \
  -sha256 -days 365 -nodes -subj "/CN=localhost"
docker compose up --build -d

# Verify services are healthy
curl -vk https://localhost:5000/health
curl -vk https://localhost:5001/health
```

#### JMeter Performance Tests
*(Requires local JMeter 5.6.3 installation)*
```bash
./apache-jmeter-5.6.3/bin/jmeter -n -t jmeter_test_plan.jmx \
  -l reports/jmeter/results.jtl \
  -e -o reports/jmeter/dashboard
```

---

## 📈 Roadmap
- [x] **Data Persistence:** SQL-backed result tracking with dual SQLite/PostgreSQL support and cross-node integrity verification.
- [x] **Infrastructure-as-Code:** Full Docker Compose stack with two Flask replicas, Nginx, and PostgreSQL 16.
- [ ] **JMeter CI reporting:** Add pass/fail threshold enforcement.
- [ ] **Playwright visual regression:** Evaluate screenshot diffing for UI layout stability checks.
