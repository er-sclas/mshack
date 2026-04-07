# MSHack — Traffic Simulation & Predictive Analytics

A traffic simulation and predictive analytics system for the Chepauk area in Chennai, India. Built for the **Mohamed Sathak Hackathon**.

Features:
- **SUMO-based traffic simulation** for University of Madras, M.A. Chidambaram Stadium, and nearby junctions
- **Dynamic event injection** (accidents, road works)
- **Real-time data streaming** to Google Firestore
- **ML-based traffic prediction** using temporal models
- **Professional React dashboard** with ECharts visualizations
- **Scenario profiles** for normal days, match days, and exam days

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

## Getting Started

### Simulation

```bash
cd simulation
pip install -r requirements.txt
python generate_network.py
python run_simulation.py
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
