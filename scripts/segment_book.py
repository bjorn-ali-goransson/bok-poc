#!/usr/bin/env python3
"""
segment_book.py — Split a parsed book into translation-ready segments.

Generates three segmentation strategies for comparison:
  1. By page   — one segment per page
  2. By paragraph — split on newline/sentence boundaries
  3. By chunk  — fixed character-count chunks (~1500 chars)

Usage:
    python3 scripts/segment_book.py output/parsed/book_6488.json
"""

import json
import re
import sys
import os


def segment_by_page(book):
    """One segment per page — simplest approach."""
    segments = []
    meta = book["metadata"]

    for page in book["pages"]:
        text = page["text_plain"]
        if not text.strip():
            continue
        segments.append({
            "segment_id": f"book_{meta['book_id']}_v{page['volume']}_p{page['page_number']}",
            "book_id": meta["book_id"],
            "book_title": meta["title"],
            "volume": page["volume"],
            "page_number": page["page_number"],
            "source_text": text,
            "footnotes": page["footnotes"],
            "char_count": len(text),
        })

    return segments


def split_into_paragraphs(text):
    """Split Arabic text into paragraphs on double newlines, <br>, or long gaps."""
    # Split on common boundaries
    parts = re.split(r'\n\n+|<br\s*/?>|(?<=\.) (?=[^\d])', text)
    # Filter empty
    return [p.strip() for p in parts if p.strip()]


def segment_by_paragraph(book):
    """One segment per paragraph — finer granularity."""
    segments = []
    meta = book["metadata"]
    seg_idx = 0

    for page in book["pages"]:
        text = page["text_plain"]
        if not text.strip():
            continue

        paragraphs = split_into_paragraphs(text)
        if not paragraphs:
            continue

        for para in paragraphs:
            seg_idx += 1
            segments.append({
                "segment_id": f"book_{meta['book_id']}_para_{seg_idx:04d}",
                "book_id": meta["book_id"],
                "book_title": meta["title"],
                "volume": page["volume"],
                "page_number": page["page_number"],
                "source_text": para,
                "char_count": len(para),
            })

    return segments


def segment_by_chunk(book, target_chars=1500):
    """Fixed-size chunks — best for consistent API costs."""
    segments = []
    meta = book["metadata"]

    # Concatenate all text
    full_text = ""
    page_map = []  # track which page each char belongs to
    for page in book["pages"]:
        text = page["text_plain"]
        if not text.strip():
            continue
        start = len(full_text)
        full_text += text + "\n"
        page_map.append({
            "start": start,
            "end": len(full_text),
            "volume": page["volume"],
            "page_number": page["page_number"],
        })

    # Split into chunks at sentence boundaries
    chunk_idx = 0
    pos = 0
    while pos < len(full_text):
        end = min(pos + target_chars, len(full_text))

        # Try to break at a sentence boundary
        if end < len(full_text):
            # Look for period, question mark, or newline near the boundary
            search_window = full_text[max(pos + target_chars - 200, pos):end]
            last_break = -1
            for ch in ['. ', '.\n', '؟ ', '。', '\n']:
                idx = search_window.rfind(ch)
                if idx > last_break:
                    last_break = idx

            if last_break > 0:
                end = max(pos + target_chars - 200, pos) + last_break + 1

        chunk = full_text[pos:end].strip()
        if chunk:
            # Find which page this chunk starts on
            vol = None
            page_num = None
            for pm in page_map:
                if pm["start"] <= pos < pm["end"]:
                    vol = pm["volume"]
                    page_num = pm["page_number"]
                    break

            chunk_idx += 1
            segments.append({
                "segment_id": f"book_{meta['book_id']}_chunk_{chunk_idx:04d}",
                "book_id": meta["book_id"],
                "book_title": meta["title"],
                "volume": vol,
                "page_number_start": page_num,
                "source_text": chunk,
                "char_count": len(chunk),
            })

        pos = end

    return segments


def write_jsonl(segments, path):
    with open(path, 'w', encoding='utf-8') as f:
        for seg in segments:
            f.write(json.dumps(seg, ensure_ascii=False) + '\n')


def print_stats(name, segments):
    if not segments:
        print(f"  {name}: 0 segments")
        return
    chars = [s["char_count"] for s in segments]
    print(f"  {name}: {len(segments)} segments, "
          f"avg={sum(chars)//len(chars)} chars, "
          f"min={min(chars)}, max={max(chars)}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <parsed_book_json>")
        sys.exit(1)

    parsed_path = sys.argv[1]
    with open(parsed_path, 'r', encoding='utf-8') as f:
        book = json.load(f)

    book_id = book["metadata"]["book_id"]
    out_dir = os.path.join(os.path.dirname(os.path.dirname(parsed_path)), "segments")
    os.makedirs(out_dir, exist_ok=True)

    # Generate all three strategies
    by_page = segment_by_page(book)
    by_para = segment_by_paragraph(book)
    by_chunk = segment_by_chunk(book)

    write_jsonl(by_page, os.path.join(out_dir, f"book_{book_id}_by_page.jsonl"))
    write_jsonl(by_para, os.path.join(out_dir, f"book_{book_id}_by_paragraph.jsonl"))
    write_jsonl(by_chunk, os.path.join(out_dir, f"book_{book_id}_by_chunk.jsonl"))

    print(f"Segmented: {book['metadata']['title']}")
    print_stats("by_page", by_page)
    print_stats("by_paragraph", by_para)
    print_stats("by_chunk", by_chunk)
    print(f"Output: {out_dir}/")


if __name__ == "__main__":
    main()
