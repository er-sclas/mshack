# Chepauk Traffic Simulation & Predictive Analytics POC

A proof-of-concept traffic simulation system for the Chepauk area in Chennai, India, featuring:
- **SUMO-based traffic simulation** for University of Madras, M.A. Chidambaram Stadium, and nearby junctions
- **Dynamic event injection** (accidents, road works)
- **Real-time data streaming** to Google Firestore
- **ML-based traffic prediction** using temporal models
- **Professional React dashboard** with ECharts visualizations

## Project Structure

```
├── simulation/          # SUMO network and simulation scripts
│   ├── config/          # Scenario configuration files
│   ├── generate_network.py
│   ├── run_simulation.py
│   ├── chepauk.net.xml
│   ├── chepauk.rou.xml
│   ├── chepauk.poly.xml
│   └── chepauk.sumocfg
├── backend/             # FastAPI backend service
│   ├── ml_model/        # ML inference components
│   ├── main.py
│   ├── firestore_client.py
│   └── requirements.txt
├── frontend/            # React dashboard
│   ├── src/
│   └── package.json
└── README.md
```

## Prerequisites

### 1. SUMO (Simulation of Urban MObility)
Install SUMO version 1.18+ from https://sumo.dlr.de/docs/Downloads.php

**macOS:**
```bash
brew install sumo
```

**Ubuntu/Debian:**
```bash
sudo add-apt-repository ppa:sumo/stable
sudo apt-get update
sudo apt-get install sumo sumo-tools sumo-doc
```

**Windows:**
Download installer from SUMO website.

Set environment variable:
```bash
export SUMO_HOME=/path/to/sumo
```

### 2. Python 3.10+
```bash
python --version  # Should be 3.10+
```

### 3. Node.js 18+
```bash
node --version  # Should be 18+
```

### 4. Google Cloud / Firestore Setup

1. Create a Firebase project at https://console.firebase.google.com
2. Enable Firestore Database (Native mode)
3. Generate a service account key:
   - Go to Project Settings → Service Accounts
   - Click "Generate new private key"
   - Save as `serviceAccountKey.json`
4. Get web app config:
   - Go to Project Settings → General → Your apps
   - Add a web app if none exists
   - Copy the firebaseConfig object

## Setup Instructions

### Step 1: Generate SUMO Network

```bash
cd simulation

# Install Python dependencies for network generation
pip install osmium requests

# Generate the network (downloads OSM data and converts to SUMO format)
python generate_network.py

# Verify files were created
ls -la chepauk.net.xml chepauk.rou.xml chepauk.poly.xml
```

### Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set:
# - GOOGLE_APPLICATION_CREDENTIALS path to your serviceAccountKey.json
# - FIRESTORE_PROJECT_ID your Firebase project ID

# Start the backend
uvicorn main:app --reload --port 8000
```

### Step 3: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure Firebase
# Edit src/firebase.ts and replace placeholder values with your Firebase config

# Start development server
npm run dev
```

### Step 4: Run a Simulation

```bash
cd simulation

# Activate backend venv
source ../backend/venv/bin/activate

# Run simulation with default scenario
python run_simulation.py

# Run with custom scenario
python run_simulation.py --config config/match_day_accident.json
```

## Usage

1. Open the frontend at http://localhost:5173
2. Navigate to "Scenarios" to create a new simulation scenario
3. Configure accident/road work events and demand profile
4. Click "Run Simulation" to start
5. View real-time results on the Dashboard
6. Compare multiple runs on the Comparison page

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/run-simulation` | Start a new simulation run |
| GET | `/runs/{runId}` | Get run metadata and summary |
| GET | `/runs/{runId}/timeseries` | Get time-series data |
| POST | `/predict` | Get ML traffic predictions |
| GET | `/scenarios` | List all scenarios |
| GET | `/edges` | List available edges with labels |

## Configuration

### Scenario Parameters

```json
{
  "name": "Match Day with Stadium Accident",
  "demandProfile": "match_day",
  "accident": {
    "enabled": true,
    "edgeId": "stadium_exit_1",
    "startTime": 3600,
    "duration": 1800,
    "severity": "major"
  },
  "roadWorks": {
    "enabled": false
  },
  "simulationDuration": 7200
}
```

### Demand Profiles

- `normal_day`: Regular university and through traffic
- `match_day`: High stadium traffic with pre/post match surges
- `exam_day`: Elevated university traffic

## Development

### Training the ML Model

```bash
cd backend
python ml_model/train_model.py --data-source firestore --epochs 100
```

### Extending the Model

The ML architecture is designed to be swappable. To use a Graph Neural Network:

1. Implement your GNN in `backend/ml_model/gnn_model.py`
2. Update `backend/ml_model/model.py` to import and use the new model
3. Retrain with the same training script

## Troubleshooting

### SUMO not found
Ensure `SUMO_HOME` is set and SUMO binaries are in PATH.

### Firestore connection errors
- Verify `GOOGLE_APPLICATION_CREDENTIALS` points to valid service account JSON
- Check that Firestore is enabled in your Firebase project

### Network generation fails
- Ensure you have internet connection for OSM data download
- Try with a smaller bounding box if download times out

## License

MIT License - see LICENSE file for details.
