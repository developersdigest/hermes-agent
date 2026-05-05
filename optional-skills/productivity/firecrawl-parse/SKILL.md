---
name: firecrawl-parse
description: Parse local PDF, DOCX, DOC, ODT, RTF, XLSX, XLS, HTML, HTM, and XHTML files with Firecrawl parse, saving clean markdown or JSON outputs to disk; Prefer Hermes web_extract for public document URLs and local ocr-and-documents for offline-only extraction. Use when the user asks to parse, read, convert, summarize, or ask questions about a local document or file path.
version: 1.0.0
author: Firecrawl
license: MIT
prerequisites:
  commands: [firecrawl]
metadata:
  hermes:
    tags: [Firecrawl, Documents, PDF, DOCX, XLSX, Markdown, Data Extraction]
    related_skills: [ocr-and-documents]
    category: productivity
    requires_toolsets: [terminal]
---

# firecrawl parse

Use the Firecrawl CLI's `parse` command to upload a local document to Firecrawl parse and save clean, LLM-ready output to disk.

## When to Use

- The source is a local file, uploaded document, or private file path rather than a public URL
- User asks to parse, read, convert, summarize, or ask questions about a PDF, Word document, spreadsheet, or HTML file
- You want Firecrawl-hosted parsing instead of installing local PDF/OCR dependencies

Use another path when:

- Prefer Hermes `web_extract` for public document URLs and local `ocr-and-documents` for offline-only extraction.
- The source is a public URL: use Hermes `web_extract` first, or `firecrawl scrape "<url>"` if operating directly through the Firecrawl CLI
- The user needs offline-only processing: use `ocr-and-documents`
- The document is larger than 50 MB: split/compress it first or use a local extraction workflow

## Setup

Verify the CLI and auth before parsing:

```bash
firecrawl --status
firecrawl --help | rg "parse"
```

If `firecrawl` is missing or `parse` is not listed, install or upgrade to the latest CLI:

```bash
npm install -g firecrawl-cli@latest
```

Then authenticate either through browser login or an API key:

```bash
firecrawl login --browser
# or
firecrawl login --api-key "fc-YOUR-API-KEY"
```

`FIRECRAWL_API_KEY` and `FIRECRAWL_API_URL` also work for scripted or self-hosted setups.

## Quick Start

Always save parsed output under `.firecrawl/`. Parsed documents can be hundreds of KB, so do not stream large results directly into the conversation.

```bash
mkdir -p .firecrawl

# File to markdown
firecrawl parse "./paper.pdf" -o .firecrawl/paper.md

# AI summary
firecrawl parse "./paper.pdf" --summary -o .firecrawl/paper-summary.md

# Ask a question about the document
firecrawl parse "./paper.pdf" --query "What are the main conclusions?" \
  -o .firecrawl/paper-answer.md
```

Read outputs incrementally:

```bash
wc -l .firecrawl/paper.md
head -80 .firecrawl/paper.md
rg -n "keyword|amount|conclusion" .firecrawl/paper.md
```

## Output Formats

Default output is markdown. Use `--format` for other formats:

```bash
firecrawl parse "./report.pdf" --format markdown,links --json --pretty \
  -o .firecrawl/report.json

firecrawl parse "./page.html" --format html -o .firecrawl/page.html
```

Available formats include `markdown`, `html`, `rawHtml`, `links`, `images`, `summary`, `json`, and `attributes`. Single-format outputs return raw content; multiple formats return JSON.

## Options

| Option | Description |
| --- | --- |
| `-f, --format <formats>` | Output one or more formats, comma-separated |
| `-H, --html` | Shortcut for `--format html` |
| `-S, --summary` | Shortcut for `--format summary` |
| `-Q, --query <prompt>` | Ask a question about the parsed content |
| `--only-main-content` | Include only main content |
| `--include-tags <tags>` | Comma-separated HTML tags to include |
| `--exclude-tags <tags>` | Comma-separated HTML tags to exclude |
| `--timeout <ms>` | Timeout for the parse job |
| `--json` | Emit JSON output |
| `--pretty` | Pretty-print JSON output |
| `-o, --output <path>` | Output file path; prefer `.firecrawl/` |

## Rules

- Quote paths with spaces: `firecrawl parse "./My Doc.pdf" -o .firecrawl/my-doc.md`
- Check `.firecrawl/` before re-parsing the same file
- Add `.firecrawl/` to `.gitignore` if the project does not already ignore it
- Never print API keys, multipart payloads, or full parsed documents into chat
- Check credit usage before batch parsing: `firecrawl credit-usage`

## Limits

- Supported file types: `.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.xlsx`, `.xls`, `.html`, `.htm`, `.xhtml`
- Max upload size: 50 MB per file
- Credit usage is roughly one credit per PDF page; HTML is one flat credit

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `firecrawl: command not found` | Run `npm install -g firecrawl-cli@latest`, then reopen the shell |
| `error: unknown command 'parse'` | Upgrade the CLI with `npm install -g firecrawl-cli@latest`, then verify `firecrawl --help | rg "parse"` |
| Not authenticated | Run `firecrawl login --browser` or set `FIRECRAWL_API_KEY` |
| Output too large | Save to `.firecrawl/`, then use `head`, `sed`, or `rg` to inspect chunks |
| Public URL provided | Use `web_extract` or `firecrawl scrape "<url>"` instead |
| Needs offline/private processing only | Use the `ocr-and-documents` skill |
