from app.schemas.paper import PaperCreate

class CrossRefMappingError(Exception):
    """When CrossRef is missing needed data"""


def crossref_to_paper_create(data: dict) -> PaperCreate:
    #Converts CrossRef 'message' object into PaperCreate
    titles = data.get("title") or []
    if not titles or not titles[0].strip():
        raise CrossRefMappingError("CrossRef record has no title")
    title = titles[0].strip()

    authors = []
    for author in data.get("author", []):
        given = author.get("given", "").strip()
        family = author.get("family", "").strip()
        full_name = f"{given} {family}".strip()
        if full_name:
            authors.append(full_name)
    
    container_titles = data.get("container-title") or []
    venue = container_titles[0].strip() if container_titles else None
    if not venue:
        event = data.get("event") or {}
        venue = event.get("name")
    
    year = _extract_year(data)

    return PaperCreate(title=title, authors=authors, venue=venue, year=year)

def _extract_year(data: dict) -> int | None:
    for key in ("published", "published-print", "published-online", "issued"):
        date_info = data.get(key)
        if date_info and date_info.get("date-parts"):
            parts = date_info["date-parts"][0]
            if parts and parts[0]:
                return int(parts[0])
    return None