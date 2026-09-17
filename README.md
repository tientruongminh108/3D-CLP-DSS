# 3D Container Loading DSS

A Decision Support System for 3D container loading optimization using Genetic Algorithm with embedded Simulated Annealing.

## Repository Structure

```
3D-CL-DSS/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Tunable parameters
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── runs.py             # POST /runs, GET /runs/{id}, GET /runs
│   │   │   ├── items.py            # CRUD /items
│   │   │   ├── containers.py       # CRUD /containers
│   │   │   └── packing_lists.py    # Upload/validate packing lists
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # Pydantic models for API
│   │   │   ├── database.py         # SQLite/SQLAlchemy setup
│   │   │   └── exceptions.py       # Custom exceptions
│   │   ├── solver/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py         # Top-level entry point (Section 3)
│   │   │   ├── parsing.py          # Parse/join/expand (Step 1)
│   │   │   ├── sorting.py          # Initial sort (Step 2, Section 5.5)
│   │   │   ├── block_generation.py # Block generation (Section 5.1)
│   │   │   ├── placement.py        # Improved Placeable Point Strategy (Section 5.2)
│   │   │   ├── constraints.py      # All 7 constraints (Section 4.4)
│   │   │   ├── ga.py               # Genetic Algorithm (Section 5.3)
│   │   │   ├── sa.py               # Simulated Annealing (Section 5.3.4)
│   │   │   ├── fitness.py          # Fitness function (Section 5.3.2)
│   │   │   ├── geometry.py         # 3D geometry primitives
│   │   │   └── output.py           # Explode blocks, render output (Section 6)
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── item_service.py
│   │       ├── container_service.py
│   │       └── run_service.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_parsing.py
│   │   ├── test_sorting.py
│   │   ├── test_block_generation.py
│   │   ├── test_placement.py
│   │   ├── test_constraints.py
│   │   ├── test_ga.py
│   │   ├── test_fifo.py
│   │   └── test_integration.py
│   ├── data/
│   │   ├── item_master.csv
│   │   ├── container_spec.csv
│   │   └── packing_list_samples/
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── RunWizard.tsx           # Primary flow (Section 2.1)
│   │   │   ├── Step1_PackingList.tsx   # Packing list + FCL/LCL badge
│   │   │   ├── Step2_Container.tsx     # Container selection
│   │   │   ├── Step3_RunOptions.tsx    # Collapsible GA parameters
│   │   │   ├── ProgressView.tsx        # Indeterminate + generation bar
│   │   │   ├── LoadingPlanViewer.tsx   # Overview + Layer Walkthrough
│   │   │   ├── UnplacedCartons.tsx     # Grouped by reason (Section 2.5)
│   │   │   ├── NewItemModal.tsx        # + New affordance (Section 2.4)
│   │   │   ├── NewContainerModal.tsx
│   │   │   ├── RunHistory.tsx          # Top-level destination
│   │   │   ├── DataManagement.tsx      # Item Master + Containers
│   │   │   ├── ItemMasterTable.tsx
│   │   │   └── ContainerTable.tsx
│   │   ├── hooks/
│   │   │   ├── useRunWizard.ts
│   │   │   ├── useApi.ts
│   │   │   └── useWebSocket.ts
│   │   ├── types/
│   │   │   ├── api.ts
│   │   │   ├── solver.ts
│   │   │   └── ui.ts
│   │   ├── utils/
│   │   │   ├── csv.ts
│   │   │   └── validation.ts
│   │   └── styles/
│   │       ├── globals.css
│   │       └── wizard.css
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── index.html
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) Docker & Docker Compose

---

### Option 1: Local Development

#### Backend
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API runs at `http://localhost:8000` | Docs at `http://localhost:8000/docs`

#### Frontend
```bash
cd frontend
npm install
npm run dev
```
App runs at `http://localhost:5173` (proxies API to `http://localhost:8000`)

---

### Option 2: Docker Compose (Recommended)
```bash
docker-compose up --build
```
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

---

## Running Tests

### Backend
```bash
cd backend
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_validation.py -v          # Section 1: Input validation
pytest tests/test_output_contract.py -v     # Section 2: Output contract
pytest tests/test_configuration.py -v       # Section 3: Configuration
pytest tests/test_api_endpoints.py -v       # Section 4: API endpoints
pytest tests/test_database.py -v            # Section 5: Database schema
pytest tests/test_parsing.py -v             # Parser unit tests
pytest tests/test_block_generation.py -v    # Block generation unit tests
```

### Frontend
```bash
cd frontend
# TypeScript check + Vite build
npm run build

# Run unit/integration tests (Vitest)
npm test

# Run tests with UI
npm run test:ui
```

### End-to-End (Playwright)
```bash
cd e2e
npm install
npx playwright install
npx playwright test
```

### All Tests (Docker)
```bash
# Backend tests in container
docker-compose exec backend pytest tests/ -v

# Frontend build check
docker-compose exec frontend npm run build
```

## Architecture Overview

### Solver Pipeline (Section 3)
1. **Parse & Join** - Read CSV, validate, join packing list with item master, expand cartons, detect FCL/LCL
2. **Initial Sort** - Order boxes by customer sequence (LCL), stacking group, volume, weight
3. **Block Generation** - Combine identical/similar boxes into blocks (max 40% container dimension)
4. **Genetic Algorithm** - Search posture assignments, decode via Placeable Point Strategy
5. **Simulated Annealing** - Embedded local refinement every N generations
5. **Output** - Explode blocks back to boxes, render 3D visualization + pick list

### Constraints (Section 4.4)
1. Weight capacity
2. Orientation (This_Way_Up)
3. Non-overlap
4. Stackability (support ratio 0.8 + load-bearing category)
5. Load-bearing capacity (numeric)
6. Center of gravity (fitness penalty)
7. Tolerance gap (2cm default, baked into dimensions)

### FCL/LCL Detection (Section 4.5)
- Automatic from distinct `Customer_Code` count in packing list
- LIFO: earlier customer's cargo must be at smaller x (near door)
- Row order in packing list = delivery sequence

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/runs | Create and execute a new run |
| GET | /api/runs/{id} | Get run result |
| GET | /api/runs | List run history |
| POST | /api/items | Create item |
| GET | /api/items | List items |
| PUT | /api/items/{id} | Update item |
| DELETE | /api/items/{id} | Delete item |
| POST | /api/containers | Create container |
| GET | /api/containers | List containers |
| PUT | /api/containers/{id} | Update container |
| DELETE | /api/containers/{id} | Delete container |
| POST | /api/packing-lists/validate | Validate CSV without running |

## Frontend Flow (frontend_guide.md)

**Landing page = Run Wizard** (not a dashboard)
- Step 1: Packing List (existing/upload/paste) → inline resolved preview + FCL/LCL badge
- Step 2: Container (dropdown + New)
- Step 3: Run Options (collapsed, defaults: pop=30, gen=40, gap=2cm)
- Run button (disabled until Steps 1-2 valid)
- Progress view (in-place transition)
- Loading Plan Viewer (Overview + Layer Walkthrough)
- Unplaced cartons grouped by reason (no_space / lifo_blocked)

**Navigation:**
- New Run (primary, landing)
- Run History
- Data Management → Item Master, Containers

## Configuration (Section 7)

Key tunable parameters in `backend/app/config.py`:
- `POPULATION_SIZE`: 30
- `GENERATIONS`: 40
- `TOLERANCE_GAP_CM`: 2.0
- `SUPPORT_RATIO`: 0.8
- `MAX_BLOCK_FRACTION`: 0.4
- `MIN_BLOCK_FILL_RATIO`: 0.98
- `ELITE_COUNT`: 2
- `MUTATION_RATE_BASE`: 0.1
- `SA_INITIAL_TEMP`: 1.0
- `SA_COOLING_RATE`: 0.95
- `COG_TOLERANCE_XY`: 0.15
- `COG_TOLERANCE_Z`: 0.20
- `UNPLACED_RANK_WEIGHT`: 10000 (ensures completeness > fill rate)

## Data Formats

### container_spec.csv
```csv
Container_Type,Internal_Length_cm,Internal_Width_cm,Internal_Height_cm,Max_Weight_kg
40HC,1203.2,235.2,270.0,28000
```

### item_master.csv
```csv
Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up,Stacking_Group,Max_Load_Bearing_kg
DT-8411,Dining Table,110,70,15,45.5,True,1,200
```

### packing_list.csv
```csv
Item_ID,PO_No,Customer_Code,Description,Qty_Pcs,Qty_Cartons
DT-8411,PO-1001,CUST-A,Dining Table,4,4
CH-2205,PO-1001,CUST-A,Chair,8,8
```

## Development

### Running Tests
```bash
cd backend
pytest tests/ -v
```

### Linting
```bash
cd backend
ruff check .
cd ../frontend
npm run lint
```

## License

Internal tool - not for distribution.