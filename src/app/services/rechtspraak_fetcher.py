import time
from dataclasses import dataclass, field
from typing import TypedDict

import requests
from lxml import etree

# Namespaces
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
DOC_NS = {
    "dcterms": "http://purl.org/dc/terms/",
    "psi": "http://psi.rechtspraak.nl/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rs": "http://www.rechtspraak.nl/schema/rechtspraak-1.0",
}

# URLs
BASE_URL = "https://data.rechtspraak.nl/uitspraken/zoeken"
DOC_URL = "https://data.rechtspraak.nl/uitspraken/content"

# Field sets
FEED_FIELDS = {"ecli", "link"}
DOC_FIELDS = {
    "creator",
    "date",
    "issued",
    "subject",
    "procedure",
    "type",
    "inhoudsindicatie",
    "uitspraak",
}
ALL_FIELDS = FEED_FIELDS | DOC_FIELDS

# Default subject filter
SUBJECT_ARBEIDSRECHT = "http://psi.rechtspraak.nl/rechtsgebied#civielRecht_arbeidsrecht"


class CaseRecord(TypedDict, total=False):
    # Feed fields
    ecli: str | None
    link: str | None
    # Document fields
    creator: str | None
    date: str | None
    issued: str | None
    subject: str | None
    procedure: str | None
    type: str | None
    inhoudsindicatie: str | None
    uitspraak: str | None


def fetch_cases(
    *,
    fields: set[str] | None = None,
    subject: str = SUBJECT_ARBEIDSRECHT,
    page_size: int = 1000,
    delay: float = 0.2,
    max_results: int | None = None,
) -> list[CaseRecord]:
    """
    Fetch cases from Rechtspraak API.

    Args:
        fields: Set of field names to fetch. None = all fields.
        subject: Legal subject filter URL
        page_size: Results per request (max 1000)
        delay: Polite delay between requests in seconds
        max_results: Max cases to fetch (None = unlimited)

    Returns:
        List of case records as dicts
    """
    fields = fields or ALL_FIELDS
    need_docs = bool(fields & DOC_FIELDS)
    # Always need ecli for doc fetching
    fetch_fields = fields | {"ecli"} if need_docs else fields

    cases: list[CaseRecord] = []
    offset = 0

    # Phase 1: Paginate through Atom feed
    while True:
        if max_results is not None and len(cases) >= max_results:
            break

        params = {
            "subject": subject,
            "return": "DOC",
            "max": page_size,
            "from": offset,
            "sort": "ASC",
        }

        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        feed = etree.fromstring(response.content)
        entries = feed.xpath("//a:entry", namespaces=ATOM_NS)

        if not entries:
            break

        for entry in entries:
            record = _parse_feed_entry(entry, fetch_fields)
            if record.get("ecli"):
                cases.append(record)

        offset += page_size
        time.sleep(delay)

    # Trim to max_results
    if max_results is not None:
        cases = cases[:max_results]

    # Phase 2: Fetch document fields if needed
    if need_docs:
        for case in cases:
            ecli = case.get("ecli")
            if ecli:
                doc_data = _fetch_doc_fields(ecli, fields, delay)
                case.update(doc_data)

    # Remove ecli if not originally requested
    if "ecli" not in fields:
        for case in cases:
            case.pop("ecli", None)

    return cases


def _parse_feed_entry(entry: etree._Element, fields: set[str]) -> CaseRecord:
    """Parse an Atom feed entry into a CaseRecord."""
    record: CaseRecord = {}

    if "ecli" in fields:
        val = entry.xpath("string(a:id)", namespaces=ATOM_NS)
        record["ecli"] = val.strip() if val and val.strip() else None

    if "link" in fields:
        val = entry.xpath("a:link/@href", namespaces=ATOM_NS)
        record["link"] = val[0] if val else None

    return record


def _fetch_doc_fields(ecli: str, fields: set[str], delay: float) -> CaseRecord:
    """Fetch document fields from the content endpoint."""
    response = requests.get(DOC_URL, params={"id": ecli}, timeout=30)
    response.raise_for_status()

    root = etree.fromstring(response.content)
    desc = root.find(".//rdf:Description", DOC_NS)

    result: CaseRecord = {}

    if desc is not None:
        if "creator" in fields:
            val = desc.findtext("dcterms:creator", namespaces=DOC_NS)
            result["creator"] = val.strip() if val and val.strip() else None

        if "date" in fields:
            val = desc.findtext("dcterms:date", namespaces=DOC_NS)
            result["date"] = val.strip() if val and val.strip() else None

        if "issued" in fields:
            val = desc.findtext("dcterms:issued", namespaces=DOC_NS)
            result["issued"] = val.strip() if val and val.strip() else None

        if "subject" in fields:
            val = desc.findtext("dcterms:subject", namespaces=DOC_NS)
            result["subject"] = val.strip() if val and val.strip() else None

        if "procedure" in fields:
            val = desc.findtext("psi:procedure", namespaces=DOC_NS)
            result["procedure"] = val.strip() if val and val.strip() else None

        if "type" in fields:
            val = desc.findtext("dcterms:type", namespaces=DOC_NS)
            result["type"] = val.strip() if val and val.strip() else None

    if "inhoudsindicatie" in fields:
        elem = root.find(".//rs:inhoudsindicatie", DOC_NS)
        if elem is not None:
            text = etree.tostring(elem, encoding="unicode", method="text")
            result["inhoudsindicatie"] = text.strip() if text and text.strip() else None
        else:
            result["inhoudsindicatie"] = None

    if "uitspraak" in fields:
        elem = root.find(".//rs:uitspraak", DOC_NS)
        if elem is not None:
            text = etree.tostring(elem, encoding="unicode", method="text")
            result["uitspraak"] = text.strip() if text and text.strip() else None
        else:
            result["uitspraak"] = None

    time.sleep(delay)
    return result


def fetch_document(ecli: str) -> etree._Element:
    """Fetch raw XML document for an ECLI."""
    response = requests.get(DOC_URL, params={"id": ecli}, timeout=30)
    response.raise_for_status()
    return etree.fromstring(response.content)


def get_paragraphs(doc: etree._Element) -> list[str]:
    """Extract paragraphs from a document."""
    paras = doc.xpath("//rs:para", namespaces=DOC_NS)
    return [etree.tostring(p, encoding="unicode", method="text").strip() for p in paras if p.text or len(p)]


def get_sections(doc: etree._Element) -> list[str]:
    """Extract parablock sections from a document."""
    blocks = doc.xpath("//rs:parablock", namespaces=DOC_NS)
    return [etree.tostring(b, encoding="unicode", method="text").strip() for b in blocks if b.text or len(b)]


# --- Structured uitspraak extraction ---

@dataclass
class StructuredParagraph:
    nr: str | None
    text: str


@dataclass
class StructuredSection:
    nr: str | None
    title: str | None
    paragraphs: list[StructuredParagraph] = field(default_factory=list)


@dataclass
class StructuredUitspraak:
    sections: list[StructuredSection] = field(default_factory=list)


def parse_uitspraak_structured(doc: etree._Element) -> StructuredUitspraak:
    """
    Parse uitspraak XML into structured sections and paragraphs.

    Returns an Uitspraak with sections, each containing numbered paragraphs.
    """
    uitspraak_elem = doc.find(".//rs:uitspraak", DOC_NS)
    if uitspraak_elem is None:
        return StructuredUitspraak()

    result = StructuredUitspraak()

    # Find all sections
    for section_elem in uitspraak_elem.findall(".//rs:section", DOC_NS):
        section = _parse_section(section_elem)
        result.sections.append(section)

    # If no sections found, treat the whole uitspraak as one section
    if not result.sections:
        section = StructuredSection(nr=None, title=None)
        section.paragraphs = _extract_paragraphs(uitspraak_elem)
        if section.paragraphs:
            result.sections.append(section)

    return result


def _parse_section(section_elem: etree._Element) -> StructuredSection:
    """Parse a single section element."""
    # Get section title and number
    title_elem = section_elem.find("rs:title", DOC_NS)
    nr = None
    title = None

    if title_elem is not None:
        nr_elem = title_elem.find("rs:nr", DOC_NS)
        if nr_elem is not None and nr_elem.text:
            nr = nr_elem.text.strip()
        # Title text is everything after the nr
        title_text = etree.tostring(title_elem, encoding="unicode", method="text").strip()
        # Remove the nr prefix if present
        if nr and title_text.startswith(nr):
            title = title_text[len(nr):].strip()
        else:
            title = title_text

    section = StructuredSection(nr=nr, title=title)
    section.paragraphs = _extract_paragraphs(section_elem)
    return section


def _extract_paragraphs(parent: etree._Element) -> list[StructuredParagraph]:
    """Extract paragraphs from paragroups and parablocks."""
    paragraphs = []

    # Process paragroups (numbered paragraph groups like 2.1, 2.2)
    for paragroup in parent.findall(".//rs:paragroup", DOC_NS):
        nr_elem = paragroup.find("rs:nr", DOC_NS)
        nr = nr_elem.text.strip() if nr_elem is not None and nr_elem.text else None

        # Collect all text from paras in this group
        texts = []
        for para in paragroup.findall(".//rs:para", DOC_NS):
            text = etree.tostring(para, encoding="unicode", method="text").strip()
            if text:
                texts.append(text)

        if texts:
            paragraphs.append(StructuredParagraph(nr=nr, text="\n".join(texts)))

    # If no paragroups, fall back to direct paras
    if not paragraphs:
        for para in parent.findall(".//rs:para", DOC_NS):
            text = etree.tostring(para, encoding="unicode", method="text").strip()
            if text:
                paragraphs.append(StructuredParagraph(nr=None, text=text))

    return paragraphs

def ensure_min_paragraph_length(
    paragraphs: list[StructuredParagraph],
    min_length: int,
    max_length: int | None = None,
) -> list[StructuredParagraph]:
    """
    Merge consecutive paragraphs until each meets min_length.
    
    When merging:
    - Numbers are joined with "+" (e.g., "2.1+2.2")
    - Texts are joined with newlines
    
    Paragraphs exceeding max_length after merging are dropped.
    """
    result = []
    i = 0
    
    while i < len(paragraphs):
        current_nr = paragraphs[i].nr
        current_text = paragraphs[i].text
        
        # Try to merge until we reach min_length
        while len(current_text) < min_length and i + 1 < len(paragraphs):
            next_para = paragraphs[i + 1]
            merged_text = current_text + "\n" + next_para.text
            
            if max_length and len(merged_text) > max_length:
                break  # Can't merge without exceeding max
            
            current_text = merged_text
            # Merge numbers: "2.1" + "2.2" -> "2.1+2.2"
            if current_nr and next_para.nr:
                current_nr = f"{current_nr}+{next_para.nr}"
            elif next_para.nr:
                current_nr = next_para.nr
            i += 1
        
        # Only keep if within bounds
        if len(current_text) >= min_length and (max_length is None or len(current_text) <= max_length):
            result.append(StructuredParagraph(nr=current_nr, text=current_text))
        
        i += 1
    
    return result
