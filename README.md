# Extrinsic Titles: Book Reader

Online reader for **Capital, Risk, and the Sin of Usury: The Forgotten History of the Extrinsic Titles** (working manuscript, 52 units: Preface, Chapters 1–44 across Parts I–XIII, Appendices A–G).

**Live site:** https://melanierieback.github.io/extrinsic-titles/

The reader is the same Vite + React + Tailwind app as the [Moral Economy reader](https://github.com/melanierieback/Moral-Economy-Book) (live at https://melanierieback.github.io/Moral-Economy-Book/) and the [Capital Without Usury reader](https://github.com/melanierieback/Capital-Without-Usury) (live at https://melanierieback.github.io/Capital-Without-Usury/), loaded with the Extrinsic Titles text. It is fully static: all content is bundled at build time from `artifacts/book-reader/src/data/book.json`; nothing is fetched at runtime.

## How it deploys

Every push to `main` runs `.github/workflows/deploy.yml`, which builds the reader with `BASE_PATH=/extrinsic-titles/` and publishes `artifacts/book-reader/dist/public` to GitHub Pages. No manual steps. **This repo is the reader's source of truth.**

Build locally:

```bash
corepack enable && corepack install --global pnpm@10
pnpm install --filter @workspace/book-reader...
BASE_PATH=/extrinsic-titles/ pnpm --filter @workspace/book-reader build   # output: artifacts/book-reader/dist/public
PORT=5000 pnpm --filter @workspace/book-reader serve                      # preview the build
```

(Note: `pnpm-workspace.yaml` pins platform binaries to linux-x64, so installs are meant for CI and Linux cloud sessions, not macOS.)

## Deep links (stable contract)

Routing is hash-based. `#<chapter-slug>` opens a unit; `#<section-slug>` opens a unit at a section; `#<subsection-slug>` opens it at a subsection. Examples:

- `…/extrinsic-titles/#chapter-9-what-is-an-extrinsic-title`
- `…/extrinsic-titles/#chapter-36-the-four-titles-compared`

Slugs are derived from the unit label plus title (chapter slugs) and the section heading (section slugs, prefixed by their chapter slug; the unheaded opening of each unit is `<chapter-slug>-intro`; subsections append their heading to the section slug). **Treat slugs as permanent once published.** External sites and any planned Contract Analyzer deep links depend on them; do not rename chapters or section headings in `book.json` without updating every inbound link.

## Updating the book text

The manuscript lives outside this repo, in the `Book Rewrites/Extrinsic Titles/drafts/` folder (`ch00.md` = Preface, `ch01`–`ch44`, `appA`–`appG`). To refresh the reader after the drafts change:

```bash
python3 tools/build_book_json.py "/path/to/Book Rewrites/Extrinsic Titles/drafts"
git commit -am "Refresh book text" && git push   # Pages redeploys automatically
```

The converter reads the per-unit drafts in reading order, reads the Part dividers inline from the drafts (the `# Part …` / `# Appendices` H1 that opens a Part), strips each draft's italic `_Draft …_` provenance note (drafting metadata the compiled PDF also drops), splits `##` headings into sections and `###` headings into subsections, and converts markdown emphasis, hyperlinks, ordered and unordered lists, blockquotes, and pipe tables into the HTML the reader renders. The generated text is byte-for-byte equivalent to the final compiled PDF (verified paragraph-by-paragraph; the only differences are the PDF's typographic ligatures).

**External hyperlinks: TODO.** The manuscript currently carries no external links, so the reader has none yet. The converter already preserves markdown `[text](url)` links (opening in a new tab), so a future link-enrichment pass on the drafts flows through unchanged, no code change needed.

## Cover art

`attached_assets/extrinsic-titles-cover.png` is the cover (1086 x 1448 px, installed 15 Jul 2026): a gold-on-navy scales-of-justice emblem (coins weighed against a flame) with the title set on top in glowing gold serif, in the NEC house style. It is built in two layers so the lettering stays crisp rather than AI-garbled:

- `attached_assets/extrinsic-titles-cover-art.png` is the raw, text-free illustration (from the ChatGPT prompt in `COVER_PROMPT.md`).
- `tools/title_cover.py` typesets the title, subtitle, and "A Working Manuscript" tag onto that art and writes `extrinsic-titles-cover.png`.

To change the art: replace `extrinsic-titles-cover-art.png` (portrait, about 1086 x 1448 px), then run `python3 tools/title_cover.py` and `python3 tools/make_placeholder_art.py --og-only` (refreshes `opengraph.jpg`), commit, and push. To change the title wording, edit the constants at the top of `tools/title_cover.py`. No app code change is needed. `tools/make_placeholder_art.py` (the original typographic placeholder, still the Open Graph card builder) is kept for reference.

## Repo layout

```
artifacts/book-reader/          the Vite + React reader (src/data/book.json = the text)
attached_assets/                cover art, NEC logo, hero background
tools/build_book_json.py        drafts -> book.json converter
tools/make_placeholder_art.py   placeholder cover + opengraph card generator
.github/workflows/              Pages deploy on push to main
```

Design notes for the reader's NEC visual identity are in `artifacts/book-reader/DESIGN.md`. The reader stores reading position and theme under the localStorage keys `et-last-chapter` and `et-dark-mode` (namespaced so they do not collide with the sibling readers on the same `melanierieback.github.io` domain).
