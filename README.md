# 3D Container Loading DSS

A Decision Support System for 3D container loading optimization using Genetic Algorithm with embedded Simulated Annealing, post-processing compaction pass, and interactive 3D visualization.

## Repository Structure

```
3D-CL-DSS/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry point & CORS configuration
│   │   ├── config.py                   # Central settings & tunable hyperparameters
│   │   ├── api/
│   │   │   └── __init__.py             # All REST API endpoints (runs, items, containers, packing lists)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── models.py               # Pydantic domain models, schemas, and enums
│   │   │   └── database.py             # SQLAlchemy models, SQLite engine, and session management
│   │   ├── services/
│   │   │   ├── __init__.py             # Service layer (RunService, ItemService, ContainerService, PackingListService)
│   │   │   └── mock_packer.py          # Deterministic mock packer (fallback engine & testing stub)
│   │   └── solver/
│   │       ├── __init__.py
│   │       ├── pipeline.py             # Top-level orchestration pipeline
│   │       ├── parsing.py              # CSV/JSON parsing, row expansion, gap inflation, FCL/LCL detection
│   │       ├── sorting.py              # Initial box sort & post-block re-sort
│   │       ├── block_generation.py     # Simple & general block consolidation
│   │       ├── placement.py            # Improved Placeable Point Strategy with corner-first seeding
│   │       ├── constraints.py          # All physical & operational constraints (weight, overlap, LIFO, stackability)
│   │       ├── ga.py                   # Genetic Algorithm with elitism & dynamic mutation
│   │       ├── sa.py                   # Simulated Annealing local refinement operator
│   │       ├── fitness.py              # Multi-objective fitness function with normalized CoG & penalty terms
│   │       ├── compaction.py           # Post-processing compaction pass (+x rear & min-y sliding, unplaced re-scan)
│   │       ├── geometry.py             # 3D bounding boxes, extreme points, contact ratios, CoG
│   │       └── output.py               # Explode blocks, metrics computation, layer building, sequence sorting
│   ├── tests/
│   │   ├── conftest.py                 # Pytest fixtures & isolated in-memory DB setup
│   │   ├── test_api_endpoints.py       # API route status codes & payload validation
│   │   ├── test_block_generation.py    # Block building & growth cap unit tests
│   │   ├── test_compaction.py          # Sliding & unplaced carton insertion tests
│   │   ├── test_configuration.py       # Settings & environment override tests
│   │   ├── test_csv_upload.py          # CSV upload parsing & schema coercion tests
│   │   ├── test_database.py            # Database CRUD & foreign key constraints
│   │   ├── test_geometry_projection.py # Extreme point generation & downward projection
│   │   ├── test_output_contract.py     # Coordinate conventions & sequence ordering tests
│   │   ├── test_parsing.py             # Input parsing, box expansion, gap inflation tests
│   │   ├── test_placement_performance.py # Placement benchmarking & runtime checks
│   │   ├── test_run_delete.py          # Run deletion & active run (409 Conflict) tests
│   │   └── test_validation.py          # Data boundary & constraint validation tests
│   ├── data/                           # Bundled sample CSVs & local SQLite database (app.db)
│   ├── test_full_pipeline.py           # End-to-end CLI pipeline test runner
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── main.tsx                    # React DOM entry point
│   │   ├── App.tsx                     # Application router & layout wrapping
│   │   ├── components/
│   │   │   ├── RunWizard.tsx           # Primary workflow wizard
│   │   │   ├── Step1_PackingList.tsx   # Packing list selection, upload & FCL/LCL badge
│   │   │   ├── Step2_Container.tsx     # Container selection & specification preview
│   │   │   ├── Step3_RunOptions.tsx    # Collapsible GA parameters (Population, Generations, Gap)
│   │   │   ├── ProgressView.tsx        # Indeterminate phase indicator & GA generation progress bar
│   │   │   ├── LoadingPlanViewer.tsx   # Three.js 3D container viewer with step-by-step loading sequence
│   │   │   ├── UnplacedCartons.tsx     # Unplaced carton breakdown grouped by failure reason
│   │   │   ├── RunHistory.tsx          # Past runs table with single & bulk delete actions
│   │   │   ├── RunDetail.tsx           # Detailed view for historical runs
│   │   │   ├── DataManagement.tsx      # Master data navigation hub (Items, Containers, Packing Lists)
│   │   │   ├── ItemMasterTable.tsx     # Item Master management table with CSV upload & bulk delete
│   │   │   ├── ContainerTable.tsx      # Container catalog management table with bulk delete
│   │   │   ├── PackingListsManagement.tsx # Packing lists manager with CSV upload & bulk delete
│   │   │   ├── PackingListDetail.tsx   # Packing list line-item inspector
│   │   │   ├── Toast.tsx               # Global notification toast store & component
│   │   │   ├── Layout.tsx              # App header, sidebar navigation, and icon set
│   │   │   ├── Layout.test.tsx         # Navigation & shell tests
│   │   │   ├── NewModal.test.tsx       # Quick-create modal tests
│   │   │   ├── RunHistory.test.tsx     # Run history table, deletion & status safeguard tests
│   │   │   ├── RunWizard.test.tsx      # Wizard step transition & option tests
│   │   │   └── UnplacedCartons.test.tsx  # Unplaced carton alert & reason grouping tests
│   │   ├── hooks/
│   │   │   ├── useRunWizard.ts         # Zustand store for run configuration & step state
│   │   │   ├── useApi.ts               # Re-exports of API service clients and types
│   │   │   └── useWebSocket.ts         # WebSocket client for real-time GA progress events
│   │   ├── services/
│   │   │   └── api.ts                  # Axios API clients for backend endpoints
│   │   ├── styles/
│   │   │   └── globals.css             # Tailwind CSS & global utility classes
│   │   ├── test/
│   │   │   └── setup.ts                # Vitest & Testing Library configuration
│   │   ├── types/
│   │   │   ├── api.ts                  # TypeScript models matching backend Pydantic schemas
│   │   │   └── ui.ts                   # UI-specific component state types
│   │   └── utils/
│   │       └── csv.ts                  # Client-side PapaParse helpers
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
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
API runs at `http://localhost:8000` | Swagger UI at `http://localhost:8000/docs`

#### Frontend
```bash
cd frontend
npm install
npm run dev
```
App runs at `http://localhost:5173` (proxies API requests to `http://localhost:8000`)

---

### Option 2: Docker Compose (Recommended)
```bash
docker-compose up --build
```
- Backend API: `http://localhost:8000`
- Frontend UI: `http://localhost:5173`

---

## Running Tests

### Backend (Pytest)
```bash
cd backend
# Run all 120+ backend unit, integration, and performance tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_compaction.py -v          # Post-processing compaction pass
pytest tests/test_run_delete.py -v          # Run deletion & conflict safeguards
pytest tests/test_output_contract.py -v     # Output contract & coordinate integrity
pytest tests/test_validation.py -v          # Business rules & constraint validation
pytest tests/test_api_endpoints.py -v       # FastAPI route behavior
```

### Frontend (Vitest & TypeScript)
```bash
cd frontend
# TypeScript static type check
npx tsc --noEmit

# Run unit tests
npm test

# Run tests in watch mode
npx vitest
```

---

## Architecture & Solver Pipeline

### Solver Pipeline
1. **Parse & Join**: Read packing list, resolve attributes against item master, expand carton quantities into individual items, inflate X/Y dimensions by `TOLERANCE_GAP_CM`, and detect shipment type (FCL vs LCL).
2. **Initial Sort**: Order boxes by customer delivery sequence (LCL), stacking group, volume descending, and weight descending.
3. **Block Generation**: Combine identical and similar cartons into composite blocks capped at `MAX_BLOCK_FRACTION` (0.2 for search, 0.4 for reporting) to prevent rigid walls and keep search space flexible.
4. **Genetic Algorithm**: Evolve posture assignments across blocks and boxes; decode placements via the **Improved Placeable Point Strategy** with corner-first seeding and contact-ratio scoring.
5. **Simulated Annealing**: Periodically refine the elite individual through local random re-posturing every `SA_INTERVAL_GENERATIONS`.
6. **Compaction Pass**: Post-processing optimization that slides placed boxes towards the rear wall (+X) and left side wall (min-Y), regenerates candidate extreme points in the freed space, and re-scans unplaced cartons (smallest-volume-first) to recover wasted volume.
7. **Output & Sequencing**: Explode composite blocks back into individual cartons, calculate physical load metrics, partition into longitudinal layers, and sort placements into loading order (`customer_sequence, -x, z, y` — rear-to-door, floor-to-ceiling, left-to-right).

### Understanding Fill Rate: GA Search Basis vs. Reported Physical Metric

It is critical to distinguish between the two volume figures used in the system:
- **GA Search Fitness Volume (`fitness.py`)**: The genetic algorithm computes placed volume using **inflated box dimensions** (`actual + TOLERANCE_GAP_CM` on length and width). This reflects the reserved space including physical clearance margins inside the container.
- **Displayed Fill Rate (`output.py`)**: The metric displayed on the UI and stored in the database measures the **true physical volume of placed cartons** divided by the total container internal volume:
  $$\text{fill\_rate} = \frac{\sum (\text{actual\_length} \times \text{actual\_width} \times \text{actual\_height})}{\text{container\_internal\_volume}}$$
  Because the inflated search footprint reserves space around every box, the GA internal fitness will show a volume percentage slightly higher (typically 3–4 percentage points) than the final reported physical fill rate.
- **Theoretical Fill-Rate Ceiling**: A run's fill rate can never exceed the total carton volume present in the packing list divided by the container volume:
  $$\text{Ceiling} = \frac{\sum_{\text{all cartons in PL}} \text{actual\_volume}}{\text{container\_internal\_volume}}$$
  For example, if a 152-carton packing list has a combined volume of $61.37\text{ m}^3$ and is packed into a 40HC container ($76.41\text{ m}^3$), the absolute maximum achievable fill rate is **80.32%**, even if 100% of cartons are placed.

### Constraints Enforced
1. **Weight Capacity**: Total cargo weight must not exceed the container payload limit.
2. **Orientation (`This_Way_Up`)**: Upright cartons are restricted to rotation around the vertical axis (`postures: {1, 2}`).
3. **Non-Overlap**: Strict 3D bounding box disjointness with tolerance padding.
4. **Stackability**:
   - **Physical Support Ratio**: At least `SUPPORT_RATIO` (0.6, allowing up to 40% overhang) of the base area must be supported by boxes directly underneath.
   - **Load-Bearing Compatibility**: Sturdy furniture (Group 1) can support lighter furniture (Group 2); Group 2 cannot support any items.
5. **Numeric Load-Bearing Limit**: Cumulative downward weight on any carton cannot exceed its declared `Max_Load_Bearing_kg`.
6. **Center of Gravity (CoG)**: Overall load center of mass must lie within tolerance bands ($\pm 5\%$ length/width, $+10\%$ height).
7. **Tolerance Gap**: 2.0 cm horizontal clearance baked into box dimensions at expansion.
8. **LIFO Delivery Order (LCL)**: Cargo for earlier delivery stops cannot be blocked by cargo for later delivery stops.

---

## API Endpoints

All endpoints are prefixed with `/api` (configured in `Settings.API_V1_PREFIX`):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/runs` | Create and execute a new optimization run |
| `POST` | `/api/runs/quick` | Execute run with inline packing list and container specification |
| `GET` | `/api/runs` | List past run summaries |
| `GET` | `/api/runs/{run_id}` | Retrieve complete run result (status, metrics, placements, unplaced) |
| `GET` | `/api/runs/{run_id}/pick-list` | Download plain-text loading sequence pick list |
| `DELETE`| `/api/runs/{run_id}` | Delete a run (returns `409 Conflict` if run is currently active) |
| `GET` | `/api/items` | List items in Item Master |
| `POST` | `/api/items` | Create a new item |
| `GET` | `/api/items/{item_id}` | Get item details |
| `PUT` | `/api/items/{item_id}` | Update item specification |
| `DELETE`| `/api/items/{item_id}` | Delete item |
| `POST` | `/api/items/upload-csv` | Bulk upload / update items from CSV |
| `GET` | `/api/containers` | List container types |
| `POST` | `/api/containers` | Create a container type |
| `GET` | `/api/containers/{id}` | Get container details |
| `PUT` | `/api/containers/{id}` | Update container specification |
| `DELETE`| `/api/containers/{id}` | Delete container |
| `POST` | `/api/containers/upload-csv` | Bulk upload containers from CSV |
| `GET` | `/api/packing-lists` | List saved packing lists |
| `POST` | `/api/packing-lists` | Create packing list record |
| `GET` | `/api/packing-lists/{id}` | Get packing list details and line items |
| `PUT` | `/api/packing-lists/{id}` | Update packing list |
| `DELETE`| `/api/packing-lists/{id}` | Delete packing list |
| `POST` | `/api/packing-lists/upload-csv` | Upload and preview CSV without saving |
| `POST` | `/api/packing-lists/upload-csv-and-save` | Upload CSV and save to database |
| `POST` | `/api/packing-lists/validate` | Validate packing list schema and item references |

---

## Frontend Flow & UI

- **Landing Page (Run Wizard)**:
  - **Step 1: Packing List**: Select from saved packing lists or upload/paste CSV; shows instant resolved item count, volume, weight, and FCL/LCL badge.
  - **Step 2: Container**: Select from container specifications (e.g. 40HC, 20GP) or create a custom container.
  - **Step 3: Run Options**: Collapsible configuration defaulting to `population_size=30`, `generations=40`, `tolerance_gap_cm=2.0`.
- **In-Progress Execution**:
  - Transition in-place to real-time status tracker (indeterminate parsing/blocks phase, followed by GA generation progress bar via WebSocket/polling).
- **Loading Plan Viewer**:
  - Three.js 3D container rendering with orbit, pan, and zoom controls.
  - **Sequential Loading Controls**: Step through the loading plan carton by carton with Play/Pause, Step Prev/Next, Reset, Show All, and a seek slider. Boxes render in strict rear-to-door, floor-to-ceiling loading order.
  - Stat cards: Fill Rate (actual volume basis), Weight Used, Weight Utilization, Placed Count, Unplaced Count.
  - CoG marker in 3D scene indicating center of mass balance.
- **Unplaced Cartons Breakdown**:
  - Displays any unplaced cartons grouped by failure reason (`no_space` vs `lifo_blocked`).
- **Run History**:
  - Filterable table of past runs showing Container, Shipment Type, Cartons Placed, Fill Rate, and Status.
  - Single-run deletion with confirmation dialog.
  - Multi-select checkboxes and bulk delete action bar.
  - Active runs (`status: running`) have deletion and selection disabled to prevent inconsistent state.
- **Data Management**:
  - Dedicated management tables for Item Master, Containers, and Packing Lists with CSV template downloads, CSV imports, and multi-select bulk delete.

---

## Configuration Reference

Key parameters defined in `backend/app/config.py`:

| Parameter | Backend Default | UI Default | Description |
|---|---|---|---|
| `POPULATION_SIZE` | `60` | `30` | Number of individuals in GA population |
| `GENERATIONS` | `100` | `40` | Maximum generations before termination |
| `TOLERANCE_GAP_CM` | `2.0` | `2.0` | Horizontal spacing clearance between boxes and walls |
| `SUPPORT_RATIO` | `0.6` | — | Minimum base area support fraction required to stack |
| `MAX_BLOCK_FRACTION` | `0.2` | — | Max block dimension fraction of container during search |
| `MAX_BLOCK_FRACTION_REPORT`| `0.4` | — | Max block dimension fraction for reporting |
| `MIN_BLOCK_FILL_RATIO` | `0.98` | — | Minimum solid volume fraction for general blocks |
| `SIMILAR_SIZE_TOLERANCE` | `0.1` | — | Relative size tolerance for similar-sized carton blocks |
| `ELITE_FRACTION` | `0.10` | — | Top fraction of population preserved across generations |
| `MUTATION_RATE_BASE` | `0.25` | — | Base mutation probability for posture genes |
| `MUTATION_RATE_MIN` | `0.10` | — | Minimum floor for dynamic mutation rate |
| `MUTATION_RATE_MAX` | `0.50` | — | Maximum ceiling for dynamic mutation rate |
| `CROSSOVER_PROBABILITY` | `0.7` | — | Multi-point crossover probability |
| `MIN_IMPROVEMENT` | `0.01` | — | Minimum fitness gain considered significant progress |
| `EARLY_STOP_PATIENCE` | `40` | — | Consecutive stagnant generations before early termination |
| `SA_INTERVAL_GENERATIONS`| `5` | — | Frequency of Simulated Annealing local search |
| `SA_INITIAL_TEMP` | `100.0` | — | Starting temperature for Simulated Annealing |
| `SA_MIN_TEMP` | `1.0` | — | Minimum stopping temperature for Simulated Annealing |
| `SA_COOLING_RATE` | `0.9` | — | Geometric cooling factor per SA iteration |
| `COG_TOLERANCE_XY` | `0.05` | — | Acceptable CoG deviation band ($\pm 5\%$ of length/width) |
| `COG_TOLERANCE_Z` | `0.10` | — | Acceptable vertical CoG band ($+10\%$ of height) |
| `UNPLACED_RANK_WEIGHT` | `2.0` | — | Penalty weight per unplaced carton (guarantees completeness > fill rate) |
| `FITNESS_VOLUME_WEIGHT`| `1.0` | — | Weight of placed volume fraction in fitness function |
| `FITNESS_COG_PENALTY_WEIGHT`| `0.3` | — | Penalty weight on normalized CoG deviation |

> **Note on Defaults**: When launched from the frontend wizard, `RunOptions` sends `population_size=30` and `generations=40` for responsive interactive response (~30–45s). When invoked directly via the backend API without options, the solver utilizes the config defaults of 60 individuals and 100 generations.

---

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

---

## Development & Code Quality

```bash
# Run backend tests
cd backend
pytest tests/ -v

# Run frontend tests & typecheck
cd ../frontend
npm test
npx tsc --noEmit
```

## License

Internal tool - not for public distribution.