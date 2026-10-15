import hashlib
import html
import re


def plain(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()


def normalize_doi(value):
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", str(value or "").strip(), flags=re.I)
    return value.lower().strip()


def normalize_record(raw):
    doi = normalize_doi(raw.get("doi"))
    pmcid = str(raw.get("pmcid") or "").upper()
    if not re.fullmatch(r"PMC\d+", pmcid):
        pmcid = ""
    source = str(raw.get("source", ""))
    source_id = str(raw.get("id", ""))
    identity = pmcid or doi or f"{source}:{source_id}"
    return {"id": hashlib.sha256(identity.encode()).hexdigest()[:16],
            "doi": doi, "pmcid": pmcid, "source": source, "sourceId": source_id,
            "title": plain(raw.get("title")), "abstract": plain(raw.get("abstractText")),
            "authors": plain(raw.get("authorString")), "year": str(raw.get("pubYear", "")),
            "journal": plain(raw.get("journalInfo", {}).get("journal", {}).get("title", "")),
            "license": plain(raw.get("license")) or "unknown",
            "isOpenAccess": raw.get("isOpenAccess") == "Y", "mergedCount": 1}


def deduplicate(records):
    """Union every shared identifier, including transitive DOI ↔ PMCID bridges."""
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, p in enumerate(records):
        keys = []
        if p["doi"]:
            keys.append("doi:" + p["doi"])
        if p["pmcid"]:
            keys.append(p["pmcid"])
        if p["source"] and p["sourceId"]:
            keys.append(p["source"] + ":" + p["sourceId"])
        for key in keys:
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    groups = {}
    for i, p in enumerate(records):
        groups.setdefault(find(i), []).append(p)
    out = []
    for group in groups.values():
        best = dict(max(group, key=lambda p: (bool(p["pmcid"]), len(p["abstract"]))))
        for field in ("doi", "pmcid", "abstract", "authors", "journal"):
            if not best[field]:
                best[field] = next((p[field] for p in group if p[field]), "")
        # Do not promote unknown/conflicting rights to a permission based on another record.
        best["mergedCount"] = len(group)
        out.append(best)
    return out


def query_terms(query):
    query = re.sub(r"\b[A-Za-z_][A-Za-z_0-9]*:", " ", query)
    tokens = re.findall(r"[^\W_]+(?:[-.][^\W_]+)*", query.casefold(), flags=re.UNICODE)
    stop = {"and", "or", "not", "the", "a", "an", "of", "for", "in", "with", "to", "from", "by"}
    return list(dict.fromkeys(t for t in tokens if t not in stop))[:32]


def hits(text, terms):
    text = text.casefold()
    return [t for t in terms if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text)]


def rank(records, query):
    terms = query_terms(query)
    for p in records:
        title, abstract = hits(p["title"], terms), hits(p["abstract"], terms)
        denom = len(terms) or 1
        title_score = 60 * len(title) / denom
        abstract_score = 40 * len(abstract) / denom
        p["relevance"] = {"score": round(title_score + abstract_score), "titlePoints": round(title_score, 1),
                          "abstractPoints": round(abstract_score, 1), "titleMatches": title,
                          "abstractMatches": abstract, "terms": terms, "method": "lexical-v1"}
    return sorted(records, key=lambda p: (-p["relevance"]["score"], p["title"]))
