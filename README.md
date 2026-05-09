# ai-workflow-qa-framework

![CI Pipeline Status](https://github.com/YOUR_USERNAME/ai-workflow-qa-framework/actions/workflows/ci.yml/badge.svg)

## 🎯 Project Purpose
This framework is a test automation suite for validating **Conversational AI** workflows within a **CPaaS (Communications Platform as a Service)** environment.

It focuses on API-level validation, structured logging, and data integrity checks, enabling reliable testing of AI-driven interactions. The framework supports mock-based testing, response validation, and persistent result tracking through SQL, making it adaptable for evolving AI workflows.  This framework includes concurrent request simulation to evaluate latency and throughput under load, enabling validation of AI service performance in production-like conditions.

---

<details>
<summary><b>Click to view detailed Acceptance Criteria (Validation Targets)</b></summary>

### 1. Functional Integrity
* **AC 1:** The system must return a valid JSON response for all standard prompt requests.
* **AC 2:** The framework must gracefully handle non-standard inputs (emojis, long-string overflows) without service interruption.
* **AC 3:** API error handling must return appropriate 4xx/5xx status codes for malformed requests to ensure ensure API reliability within CPaaS-style environments.

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
* **Language:** Python 3.9+ (Modular Client-Server Architecture)
* **Test Runner:** Pytest (Configured with dynamic fixtures and HTML reporting)
* **Load Testing:** Apache JMeter 5.6.3 (locally executable, CI integration in progress)
* **Mocking:** `requests-mock` with dynamic JSON callbacks for stateful API simulation
* **CI/CD:** GitHub Actions (Ubuntu-latest)

---

## 🌟 Key Engineering Features

### 1. Dynamic Prompt Validation (Functional)
The framework utilizes a custom **Dynamic Mocking Engine** using requests-mock with conditional response handling located in `tests/conftest.py`. This simulates a backend AI agent, allowing for robust testing of:
* **Input Edge Cases:** Validation of empty strings, `None` types, and multi-token overflows.
* **Character Handling:** Resilience testing for emojis, SQL injection strings, and non-Latin scripts.
* **Error States:** Verification of 400 (Bad Request) and 500 (Internal Server Error) handling.

### 2. Performance Guardrails (Load Testing)
Real-time AI communication cannot tolerate lag. This suite integrates **JMeter** directly into the deployment pipeline to:
* Simulate concurrent user bursts (e.g., 5-10 users with zero ramp-up).
* Monitor **Connect Latency** and **95th Percentile Response Times**.
* Configured JMeter for reliable headless execution in CI environments.

### 3. Pipeline Observability
The CI pipeline is designed for fast feedback and test visibility:

* Executes tests with immediate failure reporting to surface issues early.
* Includes timeout controls to prevent stalled or long-running executions.
* Exports Pytest HTML reports (and performance logs, if enabled) for post-run analysis.

---

## 🚀 Execution Guide

### CI/CD (Primary)
The preferred method of execution is via **GitHub Actions**. Every push triggers the full functional regression and performance suite. 
* Live logs and execution history can be viewed in the **Actions** tab of this repository.

### Local Development & Debugging
To reproduce specific test failures locally:
1.  **Initialize Environment:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Execute Functional and Performance Tests:**
    *(Requires local JMeter 5.6.3 installation)*
    ```bash
    pytest tests -v -s --html=reports/report.html --self-contained-html
    ```
---

## 📈 Roadmap
- [ ] **Data Persistence:** Integrate SQL queries to verify AI-generated metadata in SQLite.
- [ ] **Infrastructure-as-Code:** Containerize the runner using Docker for 100% environment parity.
