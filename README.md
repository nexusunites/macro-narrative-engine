# Macro Narrative Engine

## Project Documentation

- [Architecture](ARCHITECTURE.md)
- [Project Status](docs/project_status.md)
- [Roadmap](docs/roadmap.md)

## Runtime Data Storage

MNE uses GitHub for source code and a separate runtime data directory for generated history:

- headlines
- JSON results
- text reports

By default, MNE writes runtime data to:

```text
~/Google Drive/MNE-data
```

You can override this with the `MNE_DATA_DIR` environment variable. This is recommended because Google Drive folder paths vary across Mac and Windows.

### Mac

```bash
export MNE_DATA_DIR="/Users/YOURNAME/Library/CloudStorage/GoogleDrive-YOUREMAIL/My Drive/MNE-data"
```

Then restart the terminal or add the export line to your shell profile.

### Windows PowerShell

```powershell
setx MNE_DATA_DIR "G:\My Drive\MNE-data"
```

Then restart the terminal.

At startup, MNE prints the active data directory so you can confirm which runtime location is being used.

Generated filenames use a readable `YYYY-MM-DD_HHMMSS` timestamp. Run result JSON
also stores its filename stem as `run_id`. If a result, headline, or report name
already exists for that second, MNE adds a numeric suffix instead of overwriting
the existing file.

Daily snapshots aggregate same-day runs and retain their run IDs and timestamps.
Writing the same run again is idempotent: an existing raw-run entry is replaced by
matching `run_id`, or by timestamp for older runs without an ID.
