import tempfile
from pathlib import Path
from mne.database import Base, configure_database, engine

def fresh_database():
    directory=tempfile.TemporaryDirectory(); path=Path(directory.name)/"accounts.sqlite3"
    configure_database(f"sqlite:///{path}")
    from mne.database import engine as active_engine
    Base.metadata.create_all(active_engine)
    return directory
