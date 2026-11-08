"""The text of a PDF as different parsers read it.

An ATS never sees the HTML: it reads the PDF with its own extractor, and extractors do
not agree. Some follow the order in which the page draws its text, others rebuild the
lines from the position of each letter. A template is readable when all of them get the
same story out of it.
"""

import io

from pdfminer.high_level import extract_text as pdfminer_text
from pypdf import PdfReader


def extracted_texts(pdf: bytes) -> dict[str, str]:
    """The text of every page, by extractor.

    - `pypdf`: the order in which the PDF draws its text.
    - `pypdf-layout`: lines rebuilt from positions, keeping the gaps between columns.
    - `pdfminer`: lines rebuilt from positions; it is the base of many resume parsers, and
      the one that splits a word with a wide `letter-spacing` into single letters.
    """
    pages = PdfReader(io.BytesIO(pdf)).pages
    return {
        "pypdf": "\n".join(page.extract_text() for page in pages),
        "pypdf-layout": "\n".join(page.extract_text(extraction_mode="layout") for page in pages),
        "pdfminer": pdfminer_text(io.BytesIO(pdf)),
    }
