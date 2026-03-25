#!/usr/bin/env python3
"""
parse_book.py — Parse raw Shamela book data into structured JSON.

Reads a raw JSON dump (from HuggingFace dataset or mdb-export) and produces
a structured book.json with metadata, chapters, and pages.

Usage:
    python3 scripts/parse_book.py output/raw/book_6488_raw.json
"""

import json
import re
import sys
import os


def strip_html(text):
    """Remove HTML tags and decode common entities."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    return text.strip()


def clean_none(val):
    """Handle the string 'None' that pyarrow serialization produces."""
    if val is None or val == "None" or val == "":
        return None
    return val


def parse_book(raw_path):
    with open(raw_path, 'r', encoding='utf-8') as f:
        rows = json.load(f)

    if not rows:
        print("ERROR: No rows found in input file.")
        sys.exit(1)

    first = rows[0]
    book_id = first['book_id']

    # Build metadata from first row
    metadata = {
        "book_id": book_id,
        "title": clean_none(first.get("book_title")) or "",
        "category": clean_none(first.get("category")) or "",
        "category_id": clean_none(first.get("category_id")),
        "edition": clean_none(first.get("edition")) or "",
        "publisher": clean_none(first.get("publisher")) or "",
    }

    # Build pages
    pages = []
    has_footnotes = False

    for row in rows:
        text_raw = clean_none(row.get("text")) or ""
        text_plain = strip_html(text_raw)
        footnote = clean_none(row.get("foot_note")) or ""

        if footnote:
            has_footnotes = True

        page = {
            "serial_number": row.get("serial_number"),
            "volume": clean_none(row.get("volume_number")),
            "page_number": clean_none(row.get("page_number")),
            "text_raw": text_raw,
            "text_plain": text_plain,
            "footnotes": strip_html(footnote) if footnote else None,
            "char_count": len(text_plain),
        }
        pages.append(page)

    # Summary stats
    total_chars = sum(p["char_count"] for p in pages)
    avg_chars = total_chars // len(pages) if pages else 0
    volumes = set(p["volume"] for p in pages if p["volume"])

    metadata["total_pages"] = len(pages)
    metadata["total_volumes"] = len(volumes) if volumes else 1
    metadata["total_chars"] = total_chars
    metadata["avg_chars_per_page"] = avg_chars
    metadata["has_footnotes"] = has_footnotes

    book = {
        "metadata": metadata,
        "pages": pages,
    }

    return book


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <raw_json_path>")
        sys.exit(1)

    raw_path = sys.argv[1]
    book = parse_book(raw_path)
    book_id = book["metadata"]["book_id"]

    out_dir = os.path.join(os.path.dirname(os.path.dirname(raw_path)), "parsed")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"book_{book_id}.json")

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(book, f, ensure_ascii=False, indent=2)

    m = book["metadata"]
    print(f"Parsed book: {m['title']}")
    print(f"  ID: {m['book_id']}")
    print(f"  Pages: {m['total_pages']}")
    print(f"  Volumes: {m['total_volumes']}")
    print(f"  Total chars: {m['total_chars']:,}")
    print(f"  Avg chars/page: {m['avg_chars_per_page']}")
    print(f"  Has footnotes: {m['has_footnotes']}")
    print(f"  Output: {out_path}")


if __name__ == "__main__":
    main()
