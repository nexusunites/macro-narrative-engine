# Installation

## Windows

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Run engine:

```powershell
python main.py
```

Run with explicit Drive synchronization:

```powershell
python scripts\sync_data.py pull
python scripts\run_mne.py
```

Run dashboard:

```powershell
python dashboard.py
```

Open:

```text
http://localhost:8000
```

## macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Configure a fast local active datastore and an optional shared backup:

```bash
export MNE_DATA_DIR="$HOME/MNE-data"
export MNE_SYNC_DIR="$HOME/Library/CloudStorage/GoogleDrive-macronarrativeengine@gmail.com/My Drive/MNE-data"
```

MNE never edits your shell profile. See the README for migration, manual sync, wrapper, Windows environment-variable, and safe cross-device workflow details.
