"""Extract content from OneNote-exported PDFs and build a structured SQLite database."""

import fitz
import sqlite3
import json
import os
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
PDF_DIR = Path(r"C:/Users/agoodger/Downloads/PDFs")
DB_PATH = BASE_DIR / "knowledge_base.db"
IMG_DIR = BASE_DIR / "kb_images"
DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
    re.IGNORECASE,
)
CASE_URL_RE = re.compile(r"https?://[^\s<>\"]*(?:salesforce\.com|hexagonmps\.lightning\.force\.com)[^\s<>\"]*")
FROM_LINE_RE = re.compile(r"^From\s*<", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>\"]+")
PEOPLE = [
    "Leigh Oldfield", "Dan Peacock", "Justin Beamish", "Renato Fonseca",
    "Carmen Seitan", "Steve Oldfield", "Stefan", "BEAMISH Justin",
]

TAG_RULES = [
    (re.compile(r"crash", re.I), "crashing"),
    (re.compile(r"install", re.I), "installation"),
    (re.compile(r"graphic.?card|GPU|nvidia|dxdiag", re.I), "graphics"),
    (re.compile(r"licen[cs]e|server code", re.I), "licensing"),
    (re.compile(r"font|\.ttf|\.otf", re.I), "fonts"),
    (re.compile(r"registry|regedit|HKEY", re.I), "registry"),
    (re.compile(r"nest", re.I), "nesting"),
    (re.compile(r"network", re.I), "networking"),
    (re.compile(r"\+Label|xlabel|label", re.I), "label"),
    (re.compile(r"solid|IGES|STL", re.I), "solids"),
    (re.compile(r"post|machining", re.I), "machining"),
    (re.compile(r"training|certificate", re.I), "training"),
    (re.compile(r"error|warning", re.I), "errors"),
    (re.compile(r"slow|performance", re.I), "performance"),
    (re.compile(r"import|export|DXF|DWG", re.I), "file-import-export"),
]


def generate_tags(text):
    tags = set()
    for pattern, tag in TAG_RULES:
        if pattern.search(text):
            tags.add(tag)
    # Compound rules
    t = text.lower()
    if "save" in t and ("crash" in t or "slow" in t):
        tags.add("saving-issues")
    if "windows" in t and ("update" in t or "repair" in t):
        tags.add("windows")
    return sorted(tags)


def find_people(text):
    found = []
    for person in PEOPLE:
        if person in text:
            found.append(person)
    return found


def extract_page_spans(page):
    """Extract all text spans with metadata from a page, in reading order."""
    spans_out = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            line_y = line["bbox"][1]
            for span in line["spans"]:
                text = span["text"]
                size = span["size"]
                bold = bool(span["flags"] & 16)
                spans_out.append({
                    "text": text,
                    "size": size,
                    "bold": bold,
                    "y": line_y,
                    "bbox": span["bbox"],
                })
    return spans_out


def extract_links_from_page(page):
    """Extract all URI links from a page."""
    links = []
    for link in page.get_links():
        if "uri" in link:
            links.append(link["uri"])
    return links


def build_lines_from_spans(spans):
    """Group spans into lines based on y-position proximity."""
    if not spans:
        return []
    lines = []
    current_line_spans = [spans[0]]
    for s in spans[1:]:
        if abs(s["y"] - current_line_spans[-1]["y"]) < 1.5:
            current_line_spans.append(s)
        else:
            lines.append(current_line_spans)
            current_line_spans = [s]
    lines.append(current_line_spans)
    return lines


def line_text(line_spans):
    return " ".join(s["text"] for s in line_spans).strip()


def line_max_size(line_spans):
    return max(s["size"] for s in line_spans)


def line_is_bold(line_spans):
    bold_chars = sum(len(s["text"]) for s in line_spans if s["bold"])
    total_chars = sum(len(s["text"]) for s in line_spans)
    return total_chars > 0 and bold_chars / total_chars > 0.5


NOT_HEADERS_RE = re.compile(
    r"^(Hi |Hello |Dear |Regards|Kind Regards|Best regards|Hope this|"
    r"Pwd:|try\s|Click on |Select |Then |If you |In the |"
    r"Created By:|Last Modified By:|"
    r"\d+\.\s*$|[a-z])",  # starts with lowercase or is just a number
)
KNOWN_PEOPLE_RE = re.compile(
    r"^(Leigh Oldfield|Dan Peacock|Justin Beamish|Renato Fonseca|"
    r"Carmen Seitan|Steve Oldfield|Nick Miles|Sathya Senadheera|"
    r"Mike Smith|Stefan|BEAMISH Justin|OLDFIELD Leigh|PEACOCK Dan|"
    r"FONSECA Renato)$",
    re.IGNORECASE,
)


def is_section_header(line_spans, page_median_size, footer_re=None):
    """Determine if a line is likely a section/article header."""
    text = line_text(line_spans)
    if not text or len(text) < 3:
        return False
    if footer_re and footer_re.match(text):
        return False
    if text.startswith("From <") or text.startswith("From\n"):
        return False
    if text.startswith("http"):
        return False
    # Filter out lines that are clearly content, not headers
    if NOT_HEADERS_RE.match(text):
        return False
    if KNOWN_PEOPLE_RE.match(text.strip()):
        return False
    # Don't treat lines containing passwords/credentials as headers
    if "Pwd:" in text or "pwd:" in text or "Vero" in text:
        return False

    max_size = line_max_size(line_spans)
    bold = line_is_bold(line_spans)

    # Significantly larger font = header
    if max_size > page_median_size * 1.15 and len(text) < 100:
        return True
    # Bold text that's short enough to be a title
    if bold and len(text) < 80 and max_size >= page_median_size * 0.95:
        return True
    return False


def compute_median_size(all_spans):
    sizes = [s["size"] for s in all_spans if s["text"].strip()]
    if not sizes:
        return 4.0
    sizes.sort()
    return sizes[len(sizes) // 2]


def split_into_articles(pages_data, footer_re=None):
    """Split extracted page data into individual articles."""
    articles = []
    current_title = None
    current_lines = []
    current_page = 1

    for page_info in pages_data:
        pno = page_info["page_num"]
        spans = page_info["spans"]
        median_size = compute_median_size(spans)
        lines = build_lines_from_spans(spans)

        for line_spans in lines:
            text = line_text(line_spans)
            if not text:
                continue
            # Strip footer
            if footer_re and footer_re.match(text):
                continue

            if is_section_header(line_spans, median_size, footer_re):
                # Save previous article
                if current_title or current_lines:
                    articles.append({
                        "title": current_title or "Untitled",
                        "lines": current_lines,
                        "source_page": current_page,
                    })
                current_title = text
                current_lines = []
                current_page = pno
            else:
                current_lines.append(text)

    # Last article
    if current_title or current_lines:
        articles.append({
            "title": current_title or "Untitled",
            "lines": current_lines,
            "source_page": current_page,
        })

    # Post-process: merge tiny articles into their neighbors
    merged = []
    for art in articles:
        content_len = sum(len(l) for l in art["lines"])
        title = art["title"]
        # If article has no/tiny content and title looks like a continuation, merge with previous
        if merged and content_len < 30 and (
            title == "Untitled"
            or len(title) < 15
            or title[0].islower()
            or KNOWN_PEOPLE_RE.match(title.strip())
        ):
            merged[-1]["lines"].append(title)
            merged[-1]["lines"].extend(art["lines"])
        # If title is way too long (>100 chars), it's probably content, merge with previous
        elif merged and len(title) > 100:
            merged[-1]["lines"].append(title)
            merged[-1]["lines"].extend(art["lines"])
        else:
            merged.append(art)

    # Second pass: merge articles with empty content into next article as context
    final = []
    i = 0
    while i < len(merged):
        art = merged[i]
        content_len = sum(len(l) for l in art["lines"])
        if content_len == 0 and i + 1 < len(merged):
            # Prepend this title as context to next article
            next_art = merged[i + 1]
            next_art["lines"].insert(0, art["title"])
            i += 1
            continue
        final.append(art)
        i += 1

    return final


DPI_SCALE = 3  # Render at 3x (216 DPI) for sharp images


def extract_images(doc, prefix=""):
    """Extract all images from the PDF by rendering page regions at high DPI."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    page_images = {}
    seen_xrefs = set()
    mat = fitz.Matrix(DPI_SCALE, DPI_SCALE)

    for pno in range(doc.page_count):
        page = doc[pno]
        img_list = page.get_images(full=True)
        page_imgs = []
        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                # Find the image bounding box on the page
                img_rects = page.get_image_rects(xref)
                if img_rects:
                    # Render the page region at high DPI
                    clip = img_rects[0]
                    pix = page.get_pixmap(matrix=mat, clip=clip)
                else:
                    # Fallback: extract raw image
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                # Skip tiny images (likely icons/artifacts)
                if pix.width < 10 or pix.height < 10:
                    continue
                fname = f"{prefix}page{pno+1}_img{img_idx+1}.png"
                fpath = IMG_DIR / fname
                pix.save(str(fpath))
                page_imgs.append(fname)
            except Exception:
                pass
        if page_imgs:
            page_images[pno + 1] = page_imgs

    return page_images


def build_article_record(article, page_links, page_images, article_id, category, source_pdf=""):
    title = article["title"]
    content = "\n".join(article["lines"])
    full_text = f"{title}\n{content}"

    # Extract all URLs from the text
    urls_in_text = URL_RE.findall(full_text)
    # Also get links from the page annotations
    pno = article["source_page"]
    all_urls = list(set(urls_in_text + page_links.get(pno, [])))

    case_refs = [u for u in all_urls if CASE_URL_RE.match(u)]
    non_case_links = [u for u in all_urls if not CASE_URL_RE.match(u)]

    images = page_images.get(pno, [])
    tags = generate_tags(full_text)
    people = find_people(full_text)

    dates = DATE_RE.findall(full_text)
    created_date = dates[0] if dates else None

    search_text = f"{title} {content} {' '.join(tags)}".lower()

    # Clean up "From <...>" reference lines from content for cleaner storage
    cleaned_lines = []
    skip_next = False
    for line in article["lines"]:
        if FROM_LINE_RE.match(line):
            skip_next = True
            continue
        if skip_next and (line.startswith("http") or line in (">", ">")):
            continue
        skip_next = False
        cleaned_lines.append(line)
    content_clean = "\n".join(cleaned_lines).strip()

    return {
        "id": article_id,
        "title": title,
        "content": content_clean,
        "category": category,
        "tags": ", ".join(tags),
        "links": json.dumps(non_case_links),
        "case_references": json.dumps(case_refs),
        "images": json.dumps(images),
        "source_page": pno,
        "created_date": created_date,
        "people_mentioned": ", ".join(people),
        "search_text": search_text,
        "source_pdf": source_pdf,
    }


def create_database(records):
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("""
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT,
            category TEXT,
            tags TEXT,
            links TEXT,
            case_references TEXT,
            images TEXT,
            source_page INTEGER,
            created_date TEXT,
            people_mentioned TEXT,
            search_text TEXT,
            source_pdf TEXT
        )
    """)

    for rec in records:
        c.execute("""
            INSERT INTO articles (id, title, content, category, tags, links,
                case_references, images, source_page, created_date,
                people_mentioned, search_text, source_pdf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec["id"], rec["title"], rec["content"], rec["category"],
            rec["tags"], rec["links"], rec["case_references"], rec["images"],
            rec["source_page"], rec["created_date"], rec["people_mentioned"],
            rec["search_text"], rec["source_pdf"],
        ))

    # FTS5 virtual table
    c.execute("""
        CREATE VIRTUAL TABLE articles_fts USING fts5(
            title, content, tags, search_text,
            content='articles',
            content_rowid='id'
        )
    """)

    c.execute("""
        INSERT INTO articles_fts (rowid, title, content, tags, search_text)
        SELECT id, title, content, tags, search_text FROM articles
    """)

    # Indexes
    c.execute("CREATE INDEX idx_category ON articles(category)")
    c.execute("CREATE INDEX idx_tags ON articles(tags)")
    c.execute("CREATE INDEX idx_source_page ON articles(source_page)")

    conn.commit()
    conn.close()


def make_slug(name):
    """Turn a PDF stem into a safe filename prefix."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") + "_"


def process_one_pdf(pdf_path, start_id):
    """Process a single PDF, return list of article records and image count."""
    category = pdf_path.stem
    footer_re = re.compile(rf"^{re.escape(category)} Page \d+$")
    slug = make_slug(category)

    print(f"\n{'='*60}")
    print(f"Processing: {pdf_path.name}  (category: {category})")
    doc = fitz.open(str(pdf_path))
    print(f"  Pages: {doc.page_count}")

    # Extract spans and links per page
    pages_data = []
    page_links = {}
    for pno in range(doc.page_count):
        page = doc[pno]
        spans = extract_page_spans(page)
        pages_data.append({"page_num": pno + 1, "spans": spans})
        links = extract_links_from_page(page)
        if links:
            page_links[pno + 1] = links

    # Extract images
    page_images = extract_images(doc, prefix=slug)
    img_count = sum(len(v) for v in page_images.values())
    print(f"  Images extracted: {img_count}")

    # Split into articles
    articles = split_into_articles(pages_data, footer_re)
    print(f"  Articles found: {len(articles)}")

    # Build records
    records = []
    for i, article in enumerate(articles):
        rec = build_article_record(article, page_links, page_images,
                                   start_id + i, category,
                                   source_pdf=pdf_path.name)
        records.append(rec)

    doc.close()
    return records, img_count


def main():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {PDF_DIR}")
        return

    print(f"Found {len(pdf_files)} PDFs in {PDF_DIR}")
    for p in pdf_files:
        print(f"  - {p.name}")

    all_records = []
    total_images = 0
    next_id = 1

    for pdf_path in pdf_files:
        try:
            records, img_count = process_one_pdf(pdf_path, next_id)
            all_records.extend(records)
            total_images += img_count
            next_id += len(records)
        except Exception as e:
            print(f"  ERROR processing {pdf_path.name}: {e}")

    # Create database
    print(f"\n{'='*60}")
    print(f"Creating SQLite database with {len(all_records)} articles...")
    create_database(all_records)
    print(f"Database created: {DB_PATH}")

    # Print stats
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    with_tags = c.execute("SELECT COUNT(*) FROM articles WHERE tags != ''").fetchone()[0]
    with_cases = c.execute("SELECT COUNT(*) FROM articles WHERE case_references != '[]'").fetchone()[0]
    with_dates = c.execute("SELECT COUNT(*) FROM articles WHERE created_date IS NOT NULL").fetchone()[0]
    with_people = c.execute("SELECT COUNT(*) FROM articles WHERE people_mentioned != ''").fetchone()[0]
    with_images = c.execute("SELECT COUNT(*) FROM articles WHERE images != '[]'").fetchone()[0]

    print(f"\n--- Database Stats ---")
    print(f"Total articles:        {total}")
    print(f"Articles with tags:    {with_tags}")
    print(f"Articles with cases:   {with_cases}")
    print(f"Articles with dates:   {with_dates}")
    print(f"Articles with people:  {with_people}")
    print(f"Articles with images:  {with_images}")
    print(f"Total images saved:    {total_images}")

    # Per-category breakdown
    print(f"\n--- Articles per Category ---")
    rows = c.execute(
        "SELECT category, COUNT(*) as cnt FROM articles GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    for row in rows:
        print(f"  {row[0]}: {row[1]}")

    # Show some sample articles
    print(f"\n--- Sample Articles ---")
    rows = c.execute(
        "SELECT id, title, category, tags, source_page FROM articles LIMIT 15"
    ).fetchall()
    for row in rows:
        print(f"  [{row[0]}] {row[2]} p{row[4]}: {row[1][:55]}  tags=[{row[3]}]")

    # Test FTS
    for term in ("font", "crash", "licence", "nesting", "error"):
        rows = c.execute("""
            SELECT a.id, a.title, a.category
            FROM articles_fts fts
            JOIN articles a ON a.id = fts.rowid
            WHERE articles_fts MATCH ?
            LIMIT 3
        """, (term,)).fetchall()
        if rows:
            print(f"\n--- FTS '{term}' ({len(rows)} hits) ---")
            for row in rows:
                print(f"  [{row[0]}] {row[2]}: {row[1][:55]}")

    conn.close()


if __name__ == "__main__":
    main()
