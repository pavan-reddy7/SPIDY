# src/rag_parsers.py
"""
Document parsers for SPIDY Personal RAG.

Extracts plain text from supported file formats:
- TXT  — direct read
- MD   — strip markdown formatting, extract text
- PDF  — via pypdf (pure Python)
- DOCX — via python-docx
- XLSX — via openpyxl

Design:
- Every parser returns a plain text string.
- All parsers enforce a max file-size limit (10 MB).
- Errors are raised as ValueError with descriptive messages.
"""

import os
import re

# Maximum file size to parse (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Supported extensions → parser function name
SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx", ".xlsx"}


def get_supported_extensions() -> set[str]:
    """Return the set of file extensions we can parse."""
    return SUPPORTED_EXTENSIONS.copy()


def is_supported(filepath: str) -> bool:
    """Check if a file's extension is supported for parsing."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def parse_file(filepath: str) -> str:
    """
    Extract plain text from a supported file.

    Raises ValueError if the file is too large, unsupported, or unreadable.
    Returns the extracted text as a single string.
    """
    if not os.path.isfile(filepath):
        raise ValueError(f"File not found: {filepath}")

    file_size = os.path.getsize(filepath)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large ({file_size / (1024 * 1024):.1f} MB). "
            f"Maximum is {MAX_FILE_SIZE / (1024 * 1024):.0f} MB."
        )

    if file_size == 0:
        return ""

    ext = os.path.splitext(filepath)[1].lower()

    parsers = {
        ".txt": _parse_text,
        ".md": _parse_markdown,
        ".markdown": _parse_markdown,
        ".pdf": _parse_pdf,
        ".docx": _parse_docx,
        ".xlsx": _parse_xlsx,
    }

    parser = parsers.get(ext)
    if parser is None:
        raise ValueError(
            f"Unsupported file format: {ext}\n"
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    return parser(filepath)


# ------------------------------------------------------------------ #
#  Individual Parsers                                                  #
# ------------------------------------------------------------------ #

def _parse_text(filepath: str) -> str:
    """Parse a plain text file."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(f"Could not decode text file: {filepath}")


def _parse_markdown(filepath: str) -> str:
    """
    Parse a Markdown file by stripping formatting.
    Returns clean text suitable for embedding.
    """
    raw = _parse_text(filepath)
    # Strip common markdown formatting
    text = raw

    # Remove code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Remove inline code (`...`)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove images ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Convert links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove heading markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove blockquote markers
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _parse_pdf(filepath: str) -> str:
    """Parse a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError(
            "PDF support requires the 'pypdf' package. "
            "Install it with: pip install pypdf"
        )

    try:
        reader = PdfReader(filepath)
    except Exception as e:
        raise ValueError(f"Could not read PDF: {e}")

    pages_text = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        except Exception:
            # Skip unreadable pages
            continue

    if not pages_text:
        raise ValueError("No readable text found in PDF.")

    return "\n\n".join(pages_text)


def _parse_docx(filepath: str) -> str:
    """Parse a DOCX file using python-docx."""
    try:
        import docx
    except ImportError:
        raise ValueError(
            "DOCX support requires the 'python-docx' package. "
            "Install it with: pip install python-docx"
        )

    try:
        doc = docx.Document(filepath)
    except Exception as e:
        raise ValueError(f"Could not read DOCX: {e}")

    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))

    if not paragraphs:
        raise ValueError("No readable text found in DOCX.")

    return "\n\n".join(paragraphs)


def _parse_xlsx(filepath: str) -> str:
    """Parse an XLSX file using openpyxl."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ValueError(
            "XLSX support requires the 'openpyxl' package. "
            "Install it with: pip install openpyxl"
        )

    try:
        wb = load_workbook(filepath, read_only=True, data_only=True)
    except Exception as e:
        raise ValueError(f"Could not read XLSX: {e}")

    sheets_text = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            header = f"[Sheet: {sheet_name}]"
            sheets_text.append(header + "\n" + "\n".join(rows))

    wb.close()

    if not sheets_text:
        raise ValueError("No readable data found in XLSX.")

    return "\n\n".join(sheets_text)
