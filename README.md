# WasteWay 🗑️🚛
**Agentic AI for Garbage Truck Scheduling in Modern Cities**

A college prototype multi-agent system that dynamically schedules garbage trucks
based on real-time bin capacities and handles field crises autonomously.

---

## Project Structure

```
Wasteway/
├── backend/
│   ├── main.py                  # FastAPI entrypoint
│   ├── requirements.txt
│   ├── .env.example             # Copy to .env and fill in values
│   └── app/
│       ├── core/
│       │   ├── config.py        # Pydantic settings
│       │   └── database.py      # SQLAlchemy engine & session
│       ├── models/
│       │   ├── admin.py
│       │   ├── driver.py
│       │   ├── truck.py
│       │   ├── trash_bin.py
│       │   ├── route_task.py
│       │   └── crisis_event.py
│       └── routers/
│           ├── trucks.py        # CRUD /api/v1/trucks
│           └── trash_bins.py    # CRUD /api/v1/bins
├── simulator/
│   ├── seed.py                  # One-time DB seed
│   └── simulate.py              # Mock bin/breakdown simulator
└── frontend/                    # (Phase 3 – React dashboard)
```

---

## Phase 1 – Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ running locally
- Redis 7+ running locally (used from Phase 2)

### 1. Create the database
```sql
CREATE DATABASE wasteway_db;
```

### 2. Install Python dependencies
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

### 4. Seed the database
```bash
# From the project root (Wasteway/)
python simulator/seed.py
```

### 5. Start the API server
```bash
cd backend
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 6. Run the simulator
```bash
# In a separate terminal, from the project root
python simulator/simulate.py --interval 5 --breakdown-prob 0.05
```

---

## API Endpoints (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/trucks/` | List all trucks |
| POST | `/api/v1/trucks/` | Create a truck |
| GET | `/api/v1/trucks/{id}` | Get truck by ID |
| PATCH | `/api/v1/trucks/{id}` | Update truck |
| DELETE | `/api/v1/trucks/{id}` | Delete truck |
| GET | `/api/v1/bins/` | List all bins |
| POST | `/api/v1/bins/` | Create a bin |
| GET | `/api/v1/bins/{id}` | Get bin by ID |
| PATCH | `/api/v1/bins/{id}` | Update bin |
| DELETE | `/api/v1/bins/{id}` | Delete bin |
| GET | `/api/v1/bins/overflowing` | Bins ≥ 75% capacity |

---

## Roadmap

- [x] **Phase 1** – Backend setup, DB schema, CRUD API, simulator
- [ ] **Phase 2** – AI Agents (Dynamic Routing + Crisis Management) with LangGraph
- [ ] **Phase 3** – React Admin Dashboard with real-time updates
