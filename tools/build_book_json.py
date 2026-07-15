#!/usr/bin/env python3
"""Build the reader's book.json from the Extrinsic Titles draft chapters.

Usage:
    python3 tools/build_book_json.py /path/to/drafts

Reads the per-unit markdown drafts (ch00.md = Preface, ch01..ch44.md,
appA..appG.md). Each draft looks like:

    # Part IV — ...              (optional: only on the unit that opens a Part)
    # Chapter 9 — What Is an Extrinsic Title?
    _Draft v0.1, 3 Jul 2026, Claude Fable 5. ..._   (a provenance note — stripped)

    ## 9.1 Intrinsic versus extrinsic claims
    body ...
    ### *Poena conventionalis* ...  (rare: H3 -> subsection, only in the Preface)

and emits artifacts/book-reader/src/data/book.json in the reader's schema:

    Book       { title, subtitle, chapters[] }
    Chapter    { slug, title, label, badge, part?, sections[] }
    Section    { slug, title|null, paragraphs[], subsections? }
    Subsection { slug, title, paragraphs[] }

Provenance stripping mirrors the book's own compile: the italic `_Draft ..._`
note directly under each unit's H1 is drafting metadata, not book text, and
is dropped (the compiled PDF drops it too). Part dividers are read inline
from the drafts (the H1 that opens a Part), so no order is hard-coded here;
only the reading order of the files is.

Paragraphs are HTML strings (the reader renders them with
dangerouslySetInnerHTML). Text is HTML-escaped, then markdown emphasis
(***bold-italic***, **bold**, *italic*), hyperlinks [text](url), ordered and
unordered lists, blockquotes, and pipe tables are converted to tags.
Hyperlinks open in a new tab. (The Extrinsic Titles manuscript currently
carries no external links; the link path is kept so a future link-enrichment
pass flows through unchanged.)

Slugs follow the same scheme as the Capital Without Usury / Moral Economy
readers (chapter slug = slugified "label title"; section slug = chapter slug +
slugified section title; the unheaded opening of each unit gets "-intro";
subsection slug = section slug + slugified subsection title). Slugs are a
stable contract for deep links: once published, do not rename.
"""
import json
import pathlib
import re
import sys
import unicodedata

# Reading order of the draft files. Part divisions are read inline from the
# drafts themselves (the "# Part .../# Appendices" H1 that opens a unit).
UNITS = (
    ["ch00"]
    + [f"ch{n:02d}" for n in range(1, 45)]          # ch01 .. ch44
    + ["appA", "appB", "appC", "appD", "appE", "appF", "appG"]
)

TITLE = "Capital, Risk, and the Sin of Usury"
SUBTITLE = "The Forgotten History of the Extrinsic Titles"


# ── slugs & inline formatting ──────────────────────────────────────────────
def slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("*", "")                       # drop emphasis markers
    t = t.lower()
    t = t.replace("’", "").replace("'", "")   # drop apostrophes
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-")


def strip_emphasis(text: str) -> str:
    """Plain-text form of a heading (titles render as text, not HTML)."""
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    return t.strip()


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline_html(text: str) -> str:
    """Escape, then convert markdown links / bold-italic / bold / italics."""
    t = esc(text)
    # links first (open external links in a new tab)
    t = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        t,
    )
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", t, flags=re.S)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t, flags=re.S)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t, flags=re.S)
    return t


# ── block classification ───────────────────────────────────────────────────
OL_ITEM = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
UL_ITEM = re.compile(r"^\s*[-*]\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")


def split_cells(row: str):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]


def table_html(rows):
    header = split_cells(rows[0])
    body = [split_cells(r) for r in rows[2:]]     # rows[1] is the |---| separator
    out = ["<table><thead><tr>"]
    out += [f"<th>{inline_html(c)}</th>" for c in header]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline_html(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def block_to_paragraphs(lines):
    """Turn one blank-line-separated block into a list of HTML block strings."""
    # pipe table (header + separator + rows)
    if len(lines) >= 2 and TABLE_ROW.match(lines[0]) and TABLE_SEP.match(lines[1]):
        return [table_html(lines)]
    # blockquote (all lines start with '>')
    if all(ln.lstrip().startswith(">") for ln in lines):
        parts = []
        for ln in lines:
            body = ln.lstrip()[1:].lstrip()
            hard_break = ln.rstrip("\n").endswith("  ")   # markdown hard break
            parts.append(inline_html(body.rstrip()) + ("<br>" if hard_break else ""))
        return ["<blockquote>" + "\n".join(parts) + "</blockquote>"]
    # ordered list (all lines are "N. ...")
    if all(OL_ITEM.match(ln) for ln in lines):
        start = OL_ITEM.match(lines[0]).group(1)
        items = "".join("<li>" + inline_html(OL_ITEM.match(ln).group(2)) + "</li>"
                        for ln in lines)
        start_attr = f' start="{start}"' if start != "1" else ""
        return [f"<ol{start_attr}>" + items + "</ol>"]
    # unordered list (all lines are "- ..." / "* ...")
    if all(UL_ITEM.match(ln) for ln in lines):
        items = "".join("<li>" + inline_html(UL_ITEM.match(ln).group(1)) + "</li>"
                        for ln in lines)
        return ["<ul>" + items + "</ul>"]
    # ordinary prose: each source line is its own paragraph
    return [inline_html(ln) for ln in lines]


# ── unit parsing ───────────────────────────────────────────────────────────
def badge_for(label: str) -> str:
    m = re.match(r"^Chapter (\d+)$", label)
    if m:
        return m.group(1)
    if label == "Preface":
        return "PRE"
    if label == "Conclusion":
        return "END"
    if label.startswith("Appendix"):
        return label.split()[-1]
    return "·"


def is_provenance(line: str) -> bool:
    """The italic drafting note under each H1. Format varies (`_Draft v0.1 …`,
    `_ch15 draft v0.1 …`, `_Draft v0.3 (recovery-verified) …`) but every one
    is an italic line carrying the "Fable 5" drafting signature."""
    s = line.strip()
    if not s.startswith("_"):
        return False
    return ("Fable 5" in s) or bool(re.match(r"_[Dd]raft\b", s))


def strip_provenance(body):
    """Drop the italic _Draft ..._ note (and its trailing blank) at the top."""
    out = list(body)
    i = 0
    while i < len(out) and not out[i].strip():
        i += 1
    if i < len(out) and is_provenance(out[i]):
        j = i
        while j < len(out) and not out[j].rstrip().endswith("_"):
            j += 1
        del out[i:j + 1]
    return out


def parse_unit(code: str, raw: str):
    """Return (part_title_or_None, chapter_dict)."""
    lines = raw.replace("\r\n", "\n").split("\n")

    # 1) collect the leading H1s: a Part/Appendices divider (optional) + unit H1
    part_title = None
    unit_h1 = None
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# ") and not ln.startswith("## "):
            h1 = ln[2:].strip()
            if h1.startswith("Part ") or h1 == "Appendices":
                part_title = h1
                continue
            unit_h1 = h1
            body_start = i + 1
            break
    if unit_h1 is None:
        raise ValueError(f"{code}: no unit H1 found")

    # 2) split "Label — Title"; badge + slug
    if " — " in unit_h1:
        label, short_title = (s.strip() for s in unit_h1.split(" — ", 1))
    else:
        label = short_title = unit_h1.strip()
    badge = badge_for(label)
    chapter_slug = slugify(f"{label} {short_title}")

    body = strip_provenance(lines[body_start:])

    # 3) walk the body: H2 -> section, H3 -> subsection, blanks -> block breaks
    sections = []
    cur = {"title": None, "blocks": [], "block": [], "subs": []}
    cur_sub = None

    def flush_block():
        target = cur_sub if cur_sub is not None else cur
        if cur["block"]:
            target["blocks"].append(cur["block"])
            cur["block"] = []

    def paras(blocks):
        out = []
        for b in blocks:
            out.extend(block_to_paragraphs(b))
        return out

    def flush_subsection():
        nonlocal cur_sub
        if cur_sub is not None:
            flush_block()
            cur["subs"].append({"slug": cur_sub["slug"], "title": cur_sub["title"],
                                "paragraphs": paras(cur_sub["blocks"])})
            cur_sub = None

    def flush_section():
        nonlocal cur
        flush_block()
        flush_subsection()
        paragraphs = paras(cur["blocks"])
        if paragraphs or cur["subs"] or cur["title"] is not None:
            slug = (f"{chapter_slug}-intro" if cur["title"] is None
                    else f"{chapter_slug}-{slugify(cur['title'])}")
            sec = {"slug": slug, "title": cur["title"], "paragraphs": paragraphs}
            if cur["subs"]:
                sec["subsections"] = cur["subs"]
            sections.append(sec)
        cur = {"title": None, "blocks": [], "block": [], "subs": []}

    for ln in body:
        if ln.startswith("## ") and not ln.startswith("### "):
            flush_section()
            cur["title"] = strip_emphasis(ln[3:].strip())
            continue
        if ln.startswith("### "):
            flush_block()
            flush_subsection()
            sub_title = strip_emphasis(ln[4:].strip())
            sec_slug = (f"{chapter_slug}-{slugify(cur['title'])}"
                        if cur["title"] else f"{chapter_slug}-intro")
            cur_sub = {"slug": f"{sec_slug}-{slugify(sub_title)}",
                       "title": sub_title, "blocks": []}
            continue
        if ln.startswith("# "):
            raise ValueError(f"{code}: unexpected extra H1 in body: {ln!r}")
        if not ln.strip():
            flush_block()
            continue
        cur["block"].append(ln)
    flush_section()

    # 4) de-duplicate repeated slugs within the unit
    seen = {}
    for s in sections:
        base = s["slug"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            s["slug"] = f"{base}-{seen[base]}"

    chapter = {"slug": chapter_slug, "title": short_title,
               "label": label, "badge": badge, "sections": sections}
    # part_title (if any) is the divider that OPENS at this unit; main() carries
    # it forward to the following units until the next divider.
    return part_title, chapter


def main():
    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "drafts")
    out = pathlib.Path(__file__).resolve().parent.parent / "artifacts/book-reader/src/data/book.json"

    chapters = []
    current_part = None
    for code in UNITS:
        raw = (src / f"{code}.md").read_text(encoding="utf-8")
        inline_part, chapter = parse_unit(code, raw)
        if inline_part:
            current_part = inline_part
        if current_part:
            chapter["part"] = current_part
        chapters.append(chapter)

    # global slug uniqueness (chapters + sections + subsections)
    all_slugs = []
    for c in chapters:
        all_slugs.append(c["slug"])
        for s in c["sections"]:
            all_slugs.append(s["slug"])
            for sub in s.get("subsections", []):
                all_slugs.append(sub["slug"])
    dupes = sorted({s for s in all_slugs if all_slugs.count(s) > 1})
    if dupes:
        raise ValueError(f"duplicate slugs: {dupes}")

    # guard: no provenance leaked into the rendered text (sections + subsections)
    def has_prov(p):
        return "Fable 5" in p or "Draft v0." in p

    leaked = []
    for c in chapters:
        for s in c["sections"]:
            if any(has_prov(p) for p in s["paragraphs"]):
                leaked.append(s["slug"])
            for sub in s.get("subsections", []):
                if any(has_prov(p) for p in sub["paragraphs"]):
                    leaked.append(sub["slug"])
    if leaked:
        raise ValueError(f"provenance leaked into: {leaked}")

    book = {"title": TITLE, "subtitle": SUBTITLE, "chapters": chapters}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_sec = sum(len(c["sections"]) for c in chapters)
    n_sub = sum(len(s.get("subsections", [])) for c in chapters for s in c["sections"])
    n_par = sum(len(s["paragraphs"]) for c in chapters for s in c["sections"])
    n_par += sum(len(sub["paragraphs"]) for c in chapters for s in c["sections"]
                 for sub in s.get("subsections", []))
    allhtml = json.dumps(book)
    print(f"units: {len(chapters)}  sections: {n_sec}  subsections: {n_sub}  "
          f"paragraphs: {n_par}")
    print(f"tables: {allhtml.count('<table>')}  blockquotes: {allhtml.count('<blockquote>')}"
          f"  ol: {allhtml.count('<ol')}  ul: {allhtml.count('<ul>')}  "
          f"links: {allhtml.count('<a href=')}")
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
