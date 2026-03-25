# Shamela .bok Parsing POC Plan

## Background: What is a .bok file?

A `.bok` file is a **Microsoft Access (MDB/JetDB) database** used by the Maktaba Shamela
(المكتبة الشاملة) Islamic library software. Each `.bok` file contains one book with its
full text, table of contents, metadata, and footnotes.

### Known internal tables

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `b_nass` | Page text content | `id`, `nass` (text body), `page`, `part` (volume), `hashi` (footnotes) |
| `t_title` | Table of contents | `id`, `tit` (heading text), `lvl` (nesting level), `sub` |
| `Main` | Book metadata | `BkId`, `Bk` (title), `Betaka` (description), `Auth` (author), `AuthInf` |

**Note:** Schema varies slightly between Shamela versions and individual books.
The POC must inspect the actual schema of the sample file.

### Tools for reading .bok on Linux

- `mdbtools` — CLI utilities to list tables, dump schema, and export CSV from MDB files
- `pypyodbc` + MDB ODBC driver — Python DB-API access
- Existing open-source projects: `mie00/shamela`, `ojuba-org/thawab-lite` on GitHub

---

## SECTION 1 — Proposed POC Workflow

```
Input: one sample .bok file
```

**Step 1 — Inspect raw structure**
```bash
cp sample.bok sample.mdb
mdb-tables sample.mdb          # list all tables
mdb-schema sample.mdb          # dump full schema with column types
mdb-export sample.mdb b_nass | head -50   # preview text rows
mdb-export sample.mdb t_title             # dump TOC
mdb-export sample.mdb Main                # dump metadata
```
Save all raw output to `output/raw/` for manual inspection.

**Step 2 — Parse into structured JSON (Python script)**
```
parse_bok.py sample.bok → output/parsed/book.json
```
The script will:
1. Open the .bok file via `subprocess` calls to `mdb-export` (simplest, no ODBC config needed)
2. Read `Main` table → extract metadata
3. Read `t_title` table → build chapter list
4. Read `b_nass` table → extract all pages with text, page number, volume, footnotes
5. Join pages to their chapter headings by matching `id` ranges
6. Strip or preserve HTML tags in `nass` field (many books use inline HTML)
7. Write a single JSON file

**Step 3 — Generate translation-ready segments**
```
segment_book.py output/parsed/book.json → output/segments/
```
Split the parsed book into translation units. The POC will generate **three variants** for comparison:
- `segments_by_page.jsonl` — one segment per page
- `segments_by_paragraph.jsonl` — split `nass` on `<br>` or `\n` boundaries
- `segments_by_chunk.jsonl` — fixed token-count chunks (~500 tokens each)

**Step 4 — Inspect and compare**
Manually review the three segmentation approaches to decide which produces the
best translation units (coherent context, reasonable length for GPT).

---

## SECTION 2 — Example Output Structure

### Book metadata (`book.json` top-level)
```json
{
  "book_id": 12345,
  "title": "كتاب التوحيد",
  "author": "محمد بن عبد الوهاب",
  "author_info": "...",
  "description": "...",
  "total_pages": 230,
  "total_volumes": 1,
  "chapters": [ ... ],
  "pages": [ ... ]
}
```

### One chapter entry
```json
{
  "id": 5,
  "title": "باب فضل التوحيد وما يكفر من الذنوب",
  "level": 1,
  "parent_id": null
}
```

### One page entry
```json
{
  "id": 42,
  "volume": 1,
  "page_number": 38,
  "chapter_id": 5,
  "text_raw": "<p>وعن أبي هريرة رضي الله عنه...</p>",
  "text_plain": "وعن أبي هريرة رضي الله عنه...",
  "footnotes": "رواه البخاري ومسلم"
}
```

### One translation segment (`segments_by_page.jsonl`)
```json
{
  "segment_id": "book_12345_p42",
  "book_id": 12345,
  "volume": 1,
  "page_number": 38,
  "chapter_title": "باب فضل التوحيد وما يكفر من الذنوب",
  "source_text": "وعن أبي هريرة رضي الله عنه...",
  "footnotes": "رواه البخاري ومسلم",
  "char_count": 412
}
```

---

## SECTION 3 — Minimal Folder Layout

```
bok-poc/
├── input/
│   └── sample.bok              # one sample book (gitignored, stored in cloud)
├── scripts/
│   ├── inspect_bok.sh          # Step 1: raw mdbtools inspection
│   ├── parse_bok.py            # Step 2: .bok → structured JSON
│   └── segment_book.py         # Step 3: JSON → translation segments
├── output/
│   ├── raw/                    # mdb-export CSV dumps, schema dump
│   ├── parsed/
│   │   └── book.json           # full structured book
│   └── segments/
│       ├── segments_by_page.jsonl
│       ├── segments_by_paragraph.jsonl
│       └── segments_by_chunk.jsonl
├── POC_PLAN.md                 # this file
├── requirements.txt            # pypyodbc (optional), etc.
└── .gitignore                  # ignore input/*.bok, output/
```

---

## SECTION 4 — Unknowns the POC Will Resolve

| # | Question | How the POC answers it |
|---|----------|----------------------|
| 1 | Is `mdb-export` reliable enough, or do we need ODBC? | Run it on the sample file and check for encoding issues or missing data |
| 2 | What encoding is the Arabic text in? | Inspect raw CSV output — likely Windows-1256 or UTF-8 |
| 3 | Does `nass` contain HTML, plain text, or mixed? | Dump a few rows and visually inspect |
| 4 | How are footnotes stored — inline in `nass` or in `hashi` column? | Check if `hashi` column exists and has data |
| 5 | How do page IDs map to chapter IDs in `t_title`? | Cross-reference `b_nass.id` ranges with `t_title.id` |
| 6 | Are all tables present in every .bok file? | `mdb-tables` will reveal this immediately |
| 7 | What is the right translation unit size for GPT? | Compare the three segmentation strategies on real text |
| 8 | Does the text have diacritics (tashkeel) that affect translation? | Inspect sample pages |
| 9 | Are there embedded images or non-text content? | Schema and data inspection will reveal this |
| 10 | How large is a typical parsed book in JSON? | Measure output file size |

---

## SECTION 5 — Recommended Next Step After Running the POC

After inspecting the output from one sample book:

1. **Decide on segmentation strategy** — Pick page-level, paragraph-level, or chunk-level
   based on which produces coherent, consistently-sized translation units.

2. **Test one GPT translation call** — Send 5-10 segments to the OpenAI API with a
   simple system prompt. Evaluate translation quality and token usage. This answers:
   - Cost per page/book
   - Whether footnotes should be translated separately or inline
   - Whether chapter titles need special handling

3. **Validate on a second book** — Pick a book with different characteristics (multi-volume,
   heavy footnotes, or poetry) to confirm the parser handles schema variations.

4. **Only then** design the full pipeline (batch processing, cloud storage layout,
   static site generation).
