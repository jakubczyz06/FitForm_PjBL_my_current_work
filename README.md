# FitForm ETL Pipeline (Backend Core) 🚀🏋️‍♂️

## Overview
This repository contains the independent backend core and automated ETL (Extract, Transform, Load) pipeline built for **FitForm** – a fitness tracking application developed as part of a Project-Based Learning (PjBL) academic course. 

While the frontend and full application integrations are pending team development, this project standalone showcases a production-ready data ingestion pipeline. It reads user-uploaded zip archives, normalizes high-variance human-input physical metrics using **Pandas** and **NumPy**, and synchronizes the state with a cloud **PostgreSQL** database using highly efficient **SQLAlchemy Upsert (DML)** operations.

## 🛠 Tech Stack
* **Language:** Python 3.x
* **Data Processing:** Pandas, NumPy
* **Database & ORM:** PostgreSQL, SQLAlchemy (PostgreSQL Dialect)
* **Text & Encoding:** Unidecode (Linguistic normalization)
* **Environment Management:** Python-dotenv

---

## 📐 Architecture & Pipeline Breakdown

The architecture is built as a sequential multi-stage pipeline, managed by a central orchestrator script (`fitform_etl_run.py`), which executes two primary data streams:

```text
[ Raw ZIP Archives ]
        │
        ├──> 1. User Synchronization (fitform_etl_users.py) 
        │       └──> Normalizes personal attributes -> Syncs to 'users' table
        │
        └──> 2. Daily Metrics Ingestion (fitform_etl_daily_logs.py)
                └──> Cleans physical stats & logs -> Syncs to 'daily_logs' table
```

---

## 💻 Pipeline Ingestion Deep Dive

### 1. User Synchronization (`fitform_etl_users.py`)
* **Extract:** Scans and unzips binary stream packages from user directories.
* **Transform:** Strips linguistic anomalies and accents from user gender values using `unidecode`. Computes statistical modes to clean messy inputs and automatically maps individual records to unique systemic names (`User{id}`).
* **Load:** Pushes sanitized structural dictionary representations to the database.

### 2. Daily Metrics Processing (`fitform_etl_daily_logs.py`)
* **Relational Mapping:** Dynamically extracts existing database maps to validate active entity relations before processing transactional data.
* **Aggressive Data Cleansing:**
  * Processes numeric string anomalies (e.g., stripping arbitrary white spaces, resolving European comma vs. dot decimal issues) using high-speed Regex operations.
  * Normalizes truthy/falsy representations (e.g., translating linguistic strings like "tak"/"nie" into binary `1`/`0` states).
  * Implements threshold validation filters to catch impossible data ranges (e.g., filtering out biological body weight values below 30kg or above 635kg).
* **State Management & Deduplication:** Clears out broken calendar events and applies time-series deduplication over a **Compound Key** (`['user_id', 'data_wpisu']`), preserving only the latest delta log.

---

## 🔒 Advanced Engineering Design Patterns

### 🧠 Production-Grade Upsert (Idempotency)
To avoid standard database exceptions during concurrent batch loads, the pipeline completely discards dangerous `if_exists='append'` behavior. Instead, it utilizes custom SQLAlchemy execution hooks tapping directly into PostgreSQL's native `on_conflict_do_update` engine syntax. This achieves perfect **idempotency** – scripts can be run repeatedly without duplicating logs or bloating indices.

### 📊 Disjoint System Observability
Both pipeline processes feature independent structural tracking handlers (`users_etl.log` and `daily_logs_etl.log`). Pipeline logs separate core structural transformations, system connections, and errors with microsecond precision timeframes, ensuring easy debugging and infrastructure tracing.

### 📂 File State Archiving
Upon a fully committed load sequence, the internal orchestrator automatically handles filesystem storage cleanup, safely relocating raw `.zip` telemetry archives into a persistent local file system directory structure (`/archiwum`) to guarantee no data is processed twice.

---

## 📁 Repository Structure
* `fitform_etl_run.py` — The core pipeline orchestrator and entry point.
* `fitform_etl_users.py` — Extracts, cleanses, and synchronizes system user accounts.
* `fitform_etl_daily_logs.py` — Heavily processes complex macro, training, and weight logs.
