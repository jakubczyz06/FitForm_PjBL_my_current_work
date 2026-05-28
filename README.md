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
