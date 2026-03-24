# Alphacam Knowledge Base - Handover Document

**Date:** 24 March 2026
**Author:** Adam Goodger

---

## Overview

A searchable knowledge base system built from OneNote notebooks exported as PDFs. Designed to help support engineers quickly find solutions when handling Alphacam customer cases.

## Folder Structure

### Development folder

```
Carmens/
  knowledge_base.db        # SQLite database with FTS5 full-text search
  db_server.py             # Python HTTP server (API + static file serving)
  extract_and_build_db.py  # PDF extraction and database builder script
  build_package.py         # Builds a distributable package to Desktop
  launch.bat               # Starts server and opens browser
  install.bat              # One-time installer (checks Python, creates shortcut)
  install_guide.html       # Visual installation flowchart
  ui/
    index.html             # Single-page web UI (no dependencies)
  kb_images/               # 549 extracted images (rendered at 3x DPI)
  pdfs/                    # Source PDFs (served for "Open PDF" links)
```

### Distribution package (built by `build_package.py`)

```
AlphacamKB/
  install.bat              # Run once on target PC
  launch.bat               # Double-click to start (Desktop shortcut points here)
  db_server.py             # Python HTTP server
  knowledge_base.db        # Pre-built database
  install_guide.html       # Installation flowchart
  ui/                      # Web interface
  kb_images/               # Extracted images
  pdfs/                    # Source PDFs
```

## How to Run (Development)

1. Open a terminal in this folder
2. Run: `python db_server.py`
3. Open: http://localhost:8080
4. Server runs on port 8080 by default (edit `PORT` in `db_server.py` to change)

## How to Install on Another PC

1. Run `python build_package.py` to create the `AlphacamKB` folder on your Desktop
2. Copy the `AlphacamKB` folder to the target PC
3. On the target PC, double-click `install.bat` (installs Desktop shortcut)
4. Double-click the "Alphacam Knowledge Base" shortcut to launch

See `install_guide.html` for a visual flowchart.

### Requirements

- Python 3.10+ (must be added to PATH during installation)
- PyMuPDF (`pip install pymupdf`) - only needed for re-running extraction
- No other dependencies - the server and UI use Python stdlib and vanilla JS

## Current State

- **Source PDFs:** 22 OneNote notebooks exported as PDFs
- **Articles extracted:** 466 structured entries across 22 categories
- **Images extracted:** 549 (rendered at 216 DPI for clarity)
- **Tags:** 17 auto-generated categories (installation, registry, graphics, crashing, licensing, fonts, nesting, etc.)
- **Case references:** 155 articles link to Salesforce cases (clickable in UI)

### Categories

| Category | Articles |
|---|---|
| General things | 79 |
| Licences | 68 |
| Error messages | 67 |
| Posts | 65 |
| Machining | 40 |
| Nesting | 40 |
| VBA and Add-ins | 16 |
| File Import | 14 |
| Automation Manager | 12 |
| 3D-Solids | 11 |
| Reports | 10 |
| DESIGNER | 8 |
| CABINET VISION | 7 |
| Cases | 6 |
| SQL | 4 |
| Warning messages | 4 |
| Alpha edit | 3 |
| CDM | 3 |
| Lathe | 3 |
| Work Planes | 3 |
| Jira | 2 |
| To add in Training Materials | 1 |

## UI Features

- Full-text search with prefix matching (type partial words)
- Search term highlighting in both results list and article detail view
- Sidebar with category filters and tag cloud
- Image lightbox (click any image to expand full-screen)
- "Open PDF" button to view the original source PDF at the relevant page
- Salesforce case reference links open directly in the browser
- Dark mode toggle (persisted in browser)
- Keyboard shortcuts: Ctrl+K to focus search, arrow keys to navigate, Enter to open, Escape to close
- Copy article to clipboard button
- Responsive layout for smaller screens

## Adding More Notebooks

The extraction script batch-processes all PDFs in a folder:

1. Export each OneNote section as a PDF
2. Place the PDFs in `C:\Users\agoodger\Downloads\PDFs` (or update `PDF_DIR` in `extract_and_build_db.py`)
3. Run: `python extract_and_build_db.py`
4. Each PDF becomes a separate category in the database, filterable in the sidebar
5. Run `python build_package.py` to rebuild the distribution package

**Note:** Re-running extraction rebuilds the entire database from scratch. Images are rendered at 3x DPI (216 DPI) for readability.

## Auto-Tagging Rules

Articles are automatically tagged based on keyword detection:

| Keyword pattern | Tag |
|---|---|
| crash | crashing |
| install | installation |
| graphic card, GPU, nvidia, dxdiag | graphics |
| licence, license, server code | licensing |
| font, .ttf, .otf | fonts |
| registry, regedit, HKEY | registry |
| nest | nesting |
| network | networking |
| +Label, xlabel, label | label |
| solid, IGES, STL | solids |
| post, machining | machining |
| training, certificate | training |
| error, warning | errors |
| slow, performance | performance |
| import, export, DXF, DWG | file-import-export |
| save + (crash or slow) | saving-issues |
| Windows + (update or repair) | windows |

New rules can be added in the `TAG_RULES` list in `extract_and_build_db.py`.

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/search?q=<query>&category=<cat>&tag=<tag>` | Full-text search with optional filters |
| `GET /api/articles?page=1&limit=20` | Paginated article list |
| `GET /api/articles/<id>` | Single article with full detail |
| `GET /api/categories` | List categories with article counts |
| `GET /api/tags` | List tags with article counts |
| `GET /api/images/<filename>` | Serve extracted images |
| `GET /api/pdfs/<filename>` | Serve source PDFs (inline with page anchor) |

## Portability

The folder is fully portable. All paths are relative to `db_server.py`. Rename or move the folder anywhere and it will work. The only absolute path is `PDF_DIR` in `extract_and_build_db.py`, which points to the source PDF location for re-extraction.
