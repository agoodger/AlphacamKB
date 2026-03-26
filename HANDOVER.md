# Alphacam Knowledge Base - Handover Document

**Date:** 26 March 2026
**Author:** Adam Goodger

---

## Overview

A searchable knowledge base system built from OneNote notebooks exported as PDFs. Designed to help support engineers quickly find solutions when handling Alphacam customer cases. Can be run as a standalone tool or as a shared team database.

## Branches

- **main** - Standalone single-user version
- **shared-database** - Team version with audit logging, user tracking, recycle bin, and admin controls

## Folder Structure

### Development folder

```
AlphacamKB/
  knowledge_base.db        # SQLite database with FTS5 full-text search
  db_server.py             # Python HTTP server (API + static file serving)
  extract_and_build_db.py  # PDF extraction and database builder script
  build_package.py         # Builds distributable package to ~/AlphacamKB_dist/
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

1. Run `python build_package.py` to create the package in `~/AlphacamKB_dist/AlphacamKB`
2. Copy the `AlphacamKB` folder to the target PC
3. On the target PC, double-click `install.bat` (detects Desktop location including OneDrive, creates shortcut)
4. Double-click the "Alphacam Knowledge Base" shortcut to launch

See `install_guide.html` for a visual flowchart.

## Running as a Shared Team Database

1. Pick a Windows machine that's always on (server, VM, or desktop)
2. Copy the `AlphacamKB` folder there and run `python db_server.py`
3. Open firewall port 8080 on the host
4. Team members open `http://<hostname-or-ip>:8080` in their browser
5. All users share the same database - edits visible to everyone immediately

The server uses SQLite WAL mode and busy timeouts for safe concurrent access.

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
- Hexagon branding (official logo, teal/cyan/green colour scheme)

### Article Editor (shared-database branch)

- Create new articles and edit existing ones via a modal editor
- Title, category (combobox with existing categories), date, and content fields
- Tag input with chips (type and press Enter) plus auto-suggest from content
- Drag-and-drop image upload with preview grid
- External links and Salesforce case reference management
- Edit and Delete buttons on the article detail panel

### User Tracking & Audit Trail (shared-database branch)

- Users prompted for their name on first visit (stored in browser localStorage)
- Every create, edit, delete, and restore action logged with user, timestamp, and article snapshot
- "Created by" / "Last edited by" shown on article detail
- Activity History section at the bottom of each article

### Recycle Bin (shared-database branch)

- Deleted articles moved to recycle bin (soft delete), not permanently removed
- Recycle Bin accessible from the sidebar, shows who deleted each article and when
- Restore button puts articles back into the active knowledge base (no password needed)
- Permanent delete and Empty Recycle Bin require the admin password
- Admin password is set in `ADMIN_PASSWORD` at the top of `db_server.py` (default: `AlphacamKB2026`)

## Adding More Notebooks

The extraction script batch-processes all PDFs in a folder:

1. Export each OneNote section as a PDF
2. Place the PDFs in `C:\Users\agoodger\Downloads\PDFs` (or update `PDF_DIR` in `extract_and_build_db.py`)
3. Run: `python extract_and_build_db.py`
4. Each PDF becomes a separate category in the database, filterable in the sidebar
5. Run `python build_package.py` to rebuild the distribution package

**Note:** Re-running extraction rebuilds the entire database from scratch. Images are rendered at 3x DPI (216 DPI) for readability.

## Auto-Tagging Rules

Articles are automatically tagged based on keyword detection. These rules are used both during PDF extraction and in the editor's "Auto-suggest tags" button:

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

New rules can be added in the `TAG_RULES` list in `extract_and_build_db.py` and the matching `TAG_RULES` array in `ui/index.html`.

## API Endpoints

### Read Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/search?q=<query>&category=<cat>&tag=<tag>` | Full-text search with optional filters |
| `GET /api/articles?page=1&limit=20` | Paginated article list |
| `GET /api/articles/<id>` | Single article with full detail |
| `GET /api/categories` | List categories with article counts |
| `GET /api/tags` | List tags with article counts |
| `GET /api/images/<filename>` | Serve extracted images |
| `GET /api/pdfs/<filename>` | Serve source PDFs (inline with page anchor) |
| `GET /api/articles/deleted` | List soft-deleted articles (recycle bin) |
| `GET /api/articles/<id>/history` | Audit trail for an article |

### Write Endpoints

All write endpoints read the `X-User` header to identify the user.

| Endpoint | Description |
|---|---|
| `POST /api/articles` | Create a new article |
| `PUT /api/articles/<id>` | Update an existing article |
| `DELETE /api/articles/<id>` | Soft-delete (move to recycle bin) |
| `POST /api/articles/<id>/restore` | Restore from recycle bin |
| `POST /api/images/upload` | Upload images (base64 JSON body) |
| `DELETE /api/articles/<id>/permanent` | Permanently delete (requires `X-Admin-Password` header) |
| `POST /api/articles/deleted/empty` | Empty recycle bin (requires `X-Admin-Password` header) |

## Database Schema

### articles table

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PRIMARY KEY | Auto-increment |
| title | TEXT | Article title |
| content | TEXT | Full article text |
| category | TEXT | Category name (one per article) |
| tags | TEXT | Comma-separated tag list |
| links | TEXT | JSON array of URLs |
| case_references | TEXT | JSON array of Salesforce URLs |
| images | TEXT | JSON array of image filenames |
| source_page | INTEGER | Page number in source PDF |
| created_date | TEXT | Date extracted from article content |
| people_mentioned | TEXT | Comma-separated names |
| search_text | TEXT | Denormalised search field (internal) |
| source_pdf | TEXT | Original PDF filename |
| created_by | TEXT | Username who created (shared-database) |
| updated_at | TEXT | ISO timestamp of last edit (shared-database) |
| updated_by | TEXT | Username who last edited (shared-database) |
| deleted_at | TEXT | ISO timestamp of soft delete, NULL if active (shared-database) |
| deleted_by | TEXT | Username who deleted (shared-database) |

### audit_log table (shared-database branch)

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PRIMARY KEY | Auto-increment |
| article_id | INTEGER | References articles.id |
| action | TEXT | create, edit, delete, restore, permanent_delete |
| user | TEXT | Username who performed the action |
| timestamp | TEXT | ISO 8601 timestamp |
| snapshot | TEXT | JSON snapshot of article at time of action |

## Portability

The folder is fully portable. All paths are relative to `db_server.py`. Rename or move the folder anywhere and it will work. The only absolute path is `PDF_DIR` in `extract_and_build_db.py`, which points to the source PDF location for re-extraction.

The distribution package is built to `~/AlphacamKB_dist/AlphacamKB` (outside OneDrive) to avoid file locking issues.
