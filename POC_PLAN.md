# Shamela .bok Parsing POC Plan

## Background: What is a .bok file?

A `.bok` file is a **Microsoft Access (MDB/JetDB) database** used by the legacy Maktaba
Shamela (المكتبة الشاملة) desktop software. Each `.bok` file contains one book with its
full text, table of contents, metadata, and footnotes.

### Legacy format (.bok / MDB) — Shamela v3 and earlier

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `b<BkId>` | Page text content | `id`, `nass` (text body), `page`, `part` (volume), `hashi` (footnotes) |
| `t<BkId>` | Table of contents | `id`, `tit` (heading text), `lvl` (nesting level), `sub` |
| `main` | Book metadata | `bkid`, `bk` (title), `betaka` (description), `auth` (author), `authinf` |

Tools: `mdbtools` on Linux, `pypyodbc`, `access_parser` (pure Python).

### Modern format (.db / SQLite) — Shamela v4

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `page` | Page structure | `id`, `part`, `page`, `number`, `services` (text — often empty, stored in Elasticsearch) |
| `title` | Chapter hierarchy | `id`, `page`, `parent` |

**Important discovery:** Shamela v4 stores page text in **Elasticsearch/Lucene indices**,
not in the SQLite databases. The `.db` files only contain structure (page numbers, title
hierarchy). This means v4 databases cannot be used standalone for text extraction.

### Data source used for this POC

Since legacy `.bok` files are hard to obtain programmatically (Cloudflare protection,
archive.org blocked), this POC uses the **HuggingFace dataset
`MoMonir/shamela_books_text_full`** which contains pre-extracted text from 7,500+ Shamela
books in parquet format.

The dataset structure per row:
`serial_number, category_id, category, book_title, book_id, edition, publisher,
page_number, volume_number, text, foot_note`

---

## SECTION 1 — POC Workflow (Implemented)

```
Input: HuggingFace parquet shard → raw JSON → parsed JSON → translation segments
```

**Step 1 — Extract raw data**
Download one parquet shard (~76MB), filter to a single book, save as `output/raw/book_<id>_raw.json`.

**Step 2 — Parse into structured JSON**
```
python3 scripts/parse_book.py output/raw/book_14031_raw.json
→ output/parsed/book_14031.json
```
The script:
1. Reads raw JSON rows
2. Extracts metadata (title, category, edition, publisher)
3. Builds page list with text, page numbers, volume, footnotes
4. Strips HTML tags, handles None/string-None from parquet serialization
5. Computes statistics (total chars, avg chars/page, footnote presence)

**Step 3 — Generate translation-ready segments**
```
python3 scripts/segment_book.py output/parsed/book_14031.json
→ output/segments/book_14031_by_page.jsonl
→ output/segments/book_14031_by_paragraph.jsonl
→ output/segments/book_14031_by_chunk.jsonl
```
Three segmentation strategies for comparison:
- **by_page** — one segment per page (simplest, preserves page references)
- **by_paragraph** — split on `\n` boundaries (finer, but very variable size)
- **by_chunk** — fixed ~1500 char chunks with sentence-boundary alignment (most consistent)

**Step 4 — Inspect and compare**
Review the three approaches to decide which produces the best translation units.

---

## SECTION 2 — Actual Output Structure (from real data)

### Book metadata
```json
{
  "book_id": "14031",
  "title": "آثار حجج التوحيد في مؤاخذة العبيد",
  "category": "العقيدة",
  "category_id": "1",
  "edition": "الأولى، 1416 هـ - 1995 م",
  "publisher": "دار الكتاب والسنة، كراتشي - باكستان",
  "total_pages": 219,
  "total_volumes": 1,
  "total_chars": 264835,
  "avg_chars_per_page": 1209,
  "has_footnotes": true
}
```

### One page entry
```json
{
  "serial_number": "72564",
  "volume": "1",
  "page_number": "8",
  "text_raw": "ولوازمها، والتي حرم عليها مجاوزة محلها...",
  "text_plain": "ولوازمها، والتي حرم عليها مجاوزة محلها...",
  "footnotes": "(1) أخرجه الإمام أحمد في مسنده (2/ 161، 191) والإمام مسلم في صحيحه...",
  "char_count": 1209
}
```

### One translation segment (by_page)
```json
{
  "segment_id": "book_14031_v1_p8",
  "book_id": "14031",
  "book_title": "آثار حجج التوحيد في مؤاخذة العبيد",
  "volume": "1",
  "page_number": "8",
  "source_text": "ولوازمها، والتي حرم عليها مجاوزة محلها...",
  "footnotes": "(1) أخرجه الإمام أحمد في مسنده...",
  "char_count": 1209
}
```

---

## SECTION 3 — Folder Layout (Implemented)

```
bok-poc/
├── input/                      # sample databases (gitignored)
│   ├── 1000.db                 # Shamela v4 SQLite (structure only, no text)
│   └── 11430.db                # Shamela v4 SQLite (structure only, no text)
├── scripts/
│   ├── parse_book.py           # raw JSON → structured book JSON
│   └── segment_book.py         # book JSON → translation segments (3 strategies)
├── output/
│   ├── raw/                    # per-book raw JSON from HuggingFace
│   │   ├── book_6488_raw.json  # 30 pages, no footnotes
│   │   ├── book_8585_raw.json  # 147 pages
│   │   └── book_14031_raw.json # 219 pages, footnotes on every page
│   ├── parsed/
│   │   ├── book_6488.json
│   │   ├── book_8585.json
│   │   └── book_14031.json
│   └── segments/
│       ├── book_*_by_page.jsonl
│       ├── book_*_by_paragraph.jsonl
│       └── book_*_by_chunk.jsonl
├── POC_PLAN.md
└── .gitignore
```

---

## SECTION 4 — Findings and Remaining Unknowns

### Resolved by this POC

| # | Question | Answer |
|---|----------|--------|
| 1 | What format does Shamela v4 use? | SQLite databases, but text is in Elasticsearch — not self-contained |
| 2 | Can we get structured text without the Shamela app? | Yes, via HuggingFace dataset `MoMonir/shamela_books_text_full` (7,500+ books) |
| 3 | What fields exist per page? | serial_number, volume, page_number, text, foot_note |
| 4 | How are footnotes stored? | Separate `foot_note` field per page (not inline) |
| 5 | Is the text plain or HTML? | Mostly plain text with occasional `\n` for paragraph breaks |
| 6 | What is the average page size? | ~800-1200 chars (varies by book) |
| 7 | Are there chapter headings? | Not in the HuggingFace dataset — would need v4 title tables or legacy .bok |

### Still unknown

| # | Question | How to resolve |
|---|----------|---------------|
| 1 | Can we access legacy .bok files at scale? | Download Shamela v3 ISO from archive.org (when accessible) |
| 2 | Does the HuggingFace dataset cover all books we need? | Cross-reference with master.db catalog (7,542 books in v4) |
| 3 | What is the optimal translation unit for GPT? | Test 5-10 segments from each strategy with actual API calls |
| 4 | How should footnotes be handled in translation? | Test inline vs separate translation |
| 5 | Are there multi-volume books that need special handling? | Find and test a multi-volume book |
| 6 | Do special Unicode chars (﷽, ﵀, etc.) need preprocessing? | See mapping rules in `ragaeeb/shamela` constants |

---

## SECTION 5 — Recommended Next Steps

1. **Test GPT translation** — Send 5-10 page segments and 5-10 chunk segments to the
   OpenAI API. Compare quality and cost. This determines:
   - Cost per book (~265K chars ≈ ~66K tokens for book_14031)
   - Whether footnotes should be translated inline or separately
   - Whether page-level or chunk-level produces better translations

2. **Handle special characters** — Implement the character mapping rules from
   `ragaeeb/shamela` (e.g. ﷽ → بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ) as a
   preprocessing step before translation.

3. **Add chapter structure** — Either parse legacy .bok files for `t_title` data, or
   use the v4 `title` table to add chapter headings to the output.

4. **Validate at scale** — Run the pipeline on 10+ books of varying sizes and categories
   to confirm robustness.

5. **Only then** design the full production pipeline (batch translation, cloud storage
   layout, static site generation).
