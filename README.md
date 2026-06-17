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
