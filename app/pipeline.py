from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from functools import lru_cache
from typing import Any


AGENT_TERMS = {
    "worker": {
        "employee", "employees", "worker", "workers", "member", "members",
        "bargaining unit employee", "staff", "personnel", "incumbent",
    },
    "firm": {
        "employer", "company", "corporation", "organization", "department",
        "agency", "hospital", "board",
    },
    "manager": {
        "manager", "management", "supervisor", "foreman", "director",
        "administrator", "superintendent",
    },
    "union": {
        "union", "local", "association", "bargaining agent", "representative",
        "shop steward", "steward",
    },
}

STRICT_MODALS = {"shall", "will", "must", "should", "ought"}
PERMISSIVE_MODALS = {"may", "can", "could"}
RIGHT_ACTIVE = {
    "receive", "gain", "earn", "obtain", "retain", "choose", "elect",
    "request", "appeal", "use", "take", "return",
}
RIGHT_PASSIVE = {
    "entitled", "given", "offered", "reimbursed", "paid", "granted",
    "provided", "compensated", "guaranteed", "hired", "trained", "supplied",
    "protected", "allowed", "covered", "informed", "notified", "selected",
    "awarded",
}
OBLIGATION_PHRASES = {
    "required", "expected", "compelled", "obliged", "obligated", "have to",
    "has to", "ought to",
}
PROHIBITION_PHRASES = {"prohibited", "forbidden", "banned", "barred", "restricted", "proscribed"}
PERMISSION_PHRASES = {"allowed", "permitted", "authorized"}

TOPIC_KEYWORDS = {
    "family_issues": {
        "family", "parental", "maternity", "paternity", "bereavement", "child",
        "adoption", "dependent", "domestic", "pregnancy",
    },
    "health_and_wellbeing": {
        "health", "medical", "dental", "vision", "insurance", "safety", "injury",
        "sick", "disability", "wellness", "harassment", "protective", "hospital",
    },
    "payments": {
        "pay", "paid", "wage", "salary", "compensation", "premium", "bonus",
        "allowance", "reimburse", "overtime", "rate", "pension", "benefit",
    },
    "scheduling": {
        "schedule", "shift", "hours", "break", "rest period", "weekend", "rotation",
        "call-in", "workweek", "flexible", "time off",
    },
    "seniority": {
        "seniority", "service", "promotion", "transfer", "layoff", "recall",
        "posting", "vacancy", "probation",
    },
    "vacations": {
        "vacation", "holiday", "annual leave", "personal leave", "leave day",
        "paid leave",
    },
    "work_termination": {
        "termination", "terminate", "discharge", "dismiss", "discipline", "grievance",
        "arbitration", "just cause", "suspension", "severance",
    },
}

PROVINCES = [
    "Alberta", "British Columbia", "Manitoba", "New Brunswick", "Newfoundland and Labrador",
    "Nova Scotia", "Ontario", "Prince Edward Island", "Quebec", "Saskatchewan",
    "Northwest Territories", "Nunavut", "Yukon",
]

INDUSTRY_RULES = [
    ("Health care", "62", {"hospital", "health care", "nursing", "medical centre", "medical center"}),
    ("Educational services", "61", {"school", "university", "college", "education"}),
    ("Public administration", "91", {"municipality", "city of", "government", "public service"}),
    ("Manufacturing", "31-33", {"manufacturing", "factory", "plant", "automotive", "steel"}),
    ("Transportation and warehousing", "48-49", {"transit", "transport", "railway", "airline", "warehouse"}),
    ("Construction", "23", {"construction", "contractor", "building trades"}),
    ("Retail trade", "44-45", {"retail", "store", "supermarket"}),
]


@lru_cache(maxsize=1)
def _nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception:
        return None


def normalize_space(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\u00a0]+", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_metadata(text: str) -> dict[str, Any]:
    head = text[:9000]
    lower = head.lower()
    metadata: dict[str, Any] = {
        "company": None, "union": None, "location": None, "province_or_territory": None,
        "city": None, "sector_or_industry_grouping": None, "naics_industry_code": None,
        "public_private_sector_status": None, "number_of_employees_covered": None,
        "signing_date": None, "effective_date": None, "expiry_date": None,
        "contract_year": None, "contract_duration": None,
    }
    evidence: dict[str, str] = {}

    between = re.search(
        r"(?is)\bbetween\s+(.{2,160}?)\s+(?:and|&)\s+(.{2,180}?)(?:\n|effective|covering|$)", head
    )
    if between:
        metadata["company"] = normalize_space(between.group(1)).strip(" ,-:")
        metadata["union"] = normalize_space(between.group(2)).strip(" ,-:")
        evidence["company"] = evidence["union"] = normalize_space(between.group(0))[:360]

    for province in PROVINCES:
        if province.lower() in lower:
            metadata["province_or_territory"] = province
            evidence["province_or_territory"] = province
            break

    city_match = re.search(r"(?im)\b(?:city of|located in|at)\s+([A-Z][A-Za-z .'-]{2,45}),?\s+(?:" + "|".join(map(re.escape, PROVINCES)) + r")\b", head)
    if city_match:
        metadata["city"] = city_match.group(1).strip()
        metadata["location"] = f"{metadata['city']}, {metadata['province_or_territory']}"
        evidence["city"] = normalize_space(city_match.group(0))

    employee_match = re.search(r"(?i)\b(?:covering|covers|representing|approximately)\s+([\d,]+)\s+(?:employees|workers|members)\b", head)
    if employee_match:
        metadata["number_of_employees_covered"] = int(employee_match.group(1).replace(",", ""))
        evidence["number_of_employees_covered"] = employee_match.group(0)

    date_patterns = {
        "signing_date": r"(?i)\b(?:signed|signing date|dated)\s*(?:on|:)?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        "effective_date": r"(?i)\b(?:effective|commencing)\s*(?:on|date|:)?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        "expiry_date": r"(?i)\b(?:expires?|expiry|expiration|ending)\s*(?:on|date|:)?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})",
    }
    for field, pattern in date_patterns.items():
        match = re.search(pattern, head)
        if match:
            metadata[field] = match.group(1)
            evidence[field] = match.group(0)

    effective_year = re.search(r"\b(19|20)\d{2}\b", metadata["effective_date"] or "")
    if effective_year:
        metadata["contract_year"] = int(effective_year.group(0))
    if metadata["effective_date"] and metadata["expiry_date"]:
        formats = ("%B %d, %Y", "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y")
        parsed_dates = []
        for value in (metadata["effective_date"], metadata["expiry_date"]):
            parsed = next((datetime.strptime(value, fmt) for fmt in formats if _date_matches(value, fmt)), None)
            parsed_dates.append(parsed)
        if all(parsed_dates):
            metadata["contract_duration"] = round((parsed_dates[1] - parsed_dates[0]).days / 365.25, 2)
            evidence["contract_duration"] = "Calculated from effective and expiry dates"

    for label, code, words in INDUSTRY_RULES:
        hit = next((word for word in words if word in lower), None)
        if hit:
            metadata["sector_or_industry_grouping"] = label
            metadata["naics_industry_code"] = code
            evidence["sector_or_industry_grouping"] = hit
            evidence["naics_industry_code"] = f"Broad NAICS inferred from '{hit}'"
            break

    public_terms = {"city of", "government", "ministry", "public school", "municipality", "crown corporation"}
    if any(term in lower for term in public_terms):
        metadata["public_private_sector_status"] = "public"
        evidence["public_private_sector_status"] = "Public-sector organization wording detected"
    elif metadata["company"]:
        metadata["public_private_sector_status"] = "private"
        evidence["public_private_sector_status"] = "Tentative: named company and no public-sector wording detected"

    metadata["evidence"] = evidence
    metadata["warning"] = "Machine-extracted metadata is provisional and should be reviewed."
    return metadata


def _date_matches(value: str, date_format: str) -> bool:
    try:
        datetime.strptime(value, date_format)
        return True
    except ValueError:
        return False


def remove_non_core(text: str) -> dict[str, Any]:
    lines = normalize_space(text).splitlines()
    removed: list[str] = []
    kept: list[str] = []
    removing = False
    heading = re.compile(r"(?i)^\s*(appendix|appendices|exhibit|schedule|wage schedule|salary schedule|table of contents|signature page)\b")
    article = re.compile(r"(?i)^\s*(article|section)\s+[\divxlc.-]+\b")
    for line in lines:
        compact = line.strip()
        if heading.match(compact):
            removing = True
        elif removing and article.match(compact):
            removing = False
        (removed if removing else kept).append(line)
    return {
        "cleaned_text": normalize_space("\n".join(kept)),
        "removed_text": normalize_space("\n".join(removed)),
        "removed_line_count": len([x for x in removed if x.strip()]),
        "method_note": "Conservative heading-based removal; review removed material before continuing.",
    }


def split_sections(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    heading_pattern = re.compile(
        r"(?i)^\s*((?:article|section|part)\s+[\divxlc.-]+(?:\s*[-:–—]?\s*.*)?|\d+(?:\.\d+)*\s+[A-Z][^.!?]{2,100})\s*$"
    )
    sections: list[dict[str, Any]] = []
    title = "Preamble"
    body: list[str] = []
    for line in lines:
        match = heading_pattern.match(line.strip())
        if match:
            if any(x.strip() for x in body):
                sections.append({"section_id": len(sections) + 1, "heading": title, "text": normalize_space("\n".join(body))})
            title = match.group(1).strip()
            body = []
        else:
            body.append(line)
    if any(x.strip() for x in body) or not sections:
        sections.append({"section_id": len(sections) + 1, "heading": title, "text": normalize_space("\n".join(body))})
    return sections


def split_sentences(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nlp = _nlp()
    rows: list[dict[str, Any]] = []
    for section in sections:
        if nlp:
            sentences = [sent.text.strip() for sent in nlp(section["text"]).sents if sent.text.strip()]
            engine = "spaCy en_core_web_sm"
        else:
            sentences = [x.strip() for x in re.split(r"(?<=[.!?;])\s+(?=[A-Z(])|\n+", section["text"]) if x.strip()]
            engine = "regex fallback"
        for sentence in sentences:
            rows.append({
                "sentence_id": len(rows) + 1,
                "section_id": section["section_id"],
                "section_heading": section["heading"],
                "text": sentence,
                "tokenizer": engine,
            })
    return rows


def _heuristic_parse(text: str) -> tuple[str | None, str | None, str | None]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if len(words) < 3:
        return None, None, None
    modal_index = next((i for i, w in enumerate(words) if w.lower() in STRICT_MODALS | PERMISSIVE_MODALS), None)
    if modal_index is not None and modal_index > 0 and modal_index + 1 < len(words):
        subject = " ".join(words[max(0, modal_index - 4):modal_index])
        verb_i = modal_index + 1
        while verb_i < len(words) and words[verb_i].lower() in {"not", "be", "have", "been"}:
            verb_i += 1
        if verb_i < len(words):
            return subject, words[verb_i], " ".join(words[verb_i + 1:]) or None
    # A conservative fallback for common contract constructions without a modal.
    for i, word in enumerate(words[1:-1], start=1):
        if word.lower() in RIGHT_ACTIVE | RIGHT_PASSIVE | OBLIGATION_PHRASES | PERMISSION_PHRASES:
            return " ".join(words[:i]), word, " ".join(words[i + 1:])
    return None, None, None


def parse_sentences(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nlp = _nlp()
    parsed: list[dict[str, Any]] = []
    for row in sentences:
        subject = verb = obj = None
        dependencies: list[dict[str, str]] = []
        if nlp:
            doc = nlp(row["text"])
            dependencies = [{"text": t.text, "lemma": t.lemma_, "dep": t.dep_, "head": t.head.text} for t in doc]
            root = next((t for t in doc if t.dep_ == "ROOT"), None)
            subject_token = next((t for t in doc if t.dep_ in {"nsubj", "nsubjpass", "csubj"}), None)
            object_token = next((t for t in doc if t.dep_ in {"dobj", "obj", "attr", "oprd", "pobj", "dative"}), None)
            if root:
                verb = root.lemma_.lower()
            if subject_token:
                subject = " ".join(t.text for t in subject_token.subtree)
            if object_token:
                obj = " ".join(t.text for t in object_token.subtree)
        if not all((subject, verb, obj)):
            h_subject, h_verb, h_obj = _heuristic_parse(row["text"])
            subject = subject or h_subject
            verb = verb or h_verb
            obj = obj or h_obj
        parsed.append({
            **row, "subject": subject, "verb": verb, "object": obj,
            "dependencies": dependencies,
            "parser": "spaCy en_core_web_sm" if nlp else "heuristic fallback",
        })
    return parsed


def keep_svo(parsed: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted, rejected = [], []
    for row in parsed:
        if row["subject"] and row["verb"] and row["object"]:
            accepted.append({**row, "svo_status": "accepted"})
        else:
            missing = [name for name in ("subject", "verb", "object") if not row[name]]
            rejected.append({**row, "svo_status": "rejected", "rejection_reason": "Missing " + ", ".join(missing)})
    return accepted, rejected


def classify_agent(subject: str | None) -> tuple[str, str]:
    value = (subject or "").lower()
    for agent, terms in AGENT_TERMS.items():
        hit = next((term for term in terms if re.search(rf"\b{re.escape(term)}s?\b", value)), None)
        if hit:
            return agent, f"Subject contains agent term '{hit}'"
    return "unknown", "No agent dictionary term matched the extracted subject"


def add_agents(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for clause in clauses:
        agent, reason = classify_agent(clause["subject"])
        rows.append({**clause, "agent": agent, "agent_rule": reason})
    return rows


def identify_verb_structure(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for clause in clauses:
        text = clause["text"].lower()
        modal_match = re.search(r"\b(shall|will|must|should|ought|may|can|could)\b", text)
        modal = modal_match.group(1) if modal_match else None
        negated = bool(re.search(r"\b(?:not|never|no)\b", text))
        passive = bool(re.search(r"\b(?:shall|will|must|should|may|can|could)\s+(?:not\s+)?be\s+\w+(?:ed|en)\b", text))
        special = None
        for label, phrases in (
            ("rights_verb", RIGHT_ACTIVE | RIGHT_PASSIVE),
            ("obligation_verb", OBLIGATION_PHRASES),
            ("prohibition_verb", PROHIBITION_PHRASES),
            ("permission_verb", PERMISSION_PHRASES),
        ):
            hit = next((phrase for phrase in phrases if re.search(rf"\b{re.escape(phrase)}\b", text)), None)
            if hit:
                special = {"category": label, "term": hit}
                break
        rows.append({
            **clause, "modal": modal,
            "modal_type": "restrictive" if modal in STRICT_MODALS else "permissive" if modal in PERMISSIVE_MODALS else None,
            "negated": negated, "voice": "passive" if passive else "active",
            "special_verb": special,
        })
    return rows


def classify_clause_type(clause: dict[str, Any]) -> tuple[str, str]:
    modal_type = clause["modal_type"]
    negated = clause["negated"]
    voice = clause["voice"]
    special = clause["special_verb"] or {}
    category = special.get("category")
    verb = (clause["verb"] or "").lower()

    if category == "obligation_verb" and negated:
        return "right", "Negative modal plus obligation verb: subject is protected from a requirement"
    if category == "prohibition_verb" or (modal_type in {"restrictive", "permissive"} and negated):
        return "prohibition", "Constraint verb or negated modal"
    if category == "permission_verb" or (modal_type == "permissive" and not negated):
        return "permission", "Permission verb or positive permissive modal"
    if category == "rights_verb" or verb in RIGHT_ACTIVE | RIGHT_PASSIVE:
        return "right", "Active/passive rights verb"
    if modal_type == "restrictive" and not negated:
        return "obligation", "Positive restrictive modal plus active verb"
    return "other", "No legal-type rule matched"


def add_clause_types(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for clause in clauses:
        clause_type, rule = classify_clause_type(clause)
        rows.append({**clause, "clause_type": clause_type, "classification_rule": rule})
    return rows


def assign_topic(clause: dict[str, Any]) -> tuple[str, str]:
    text = f"{clause['section_heading']} {clause['text']}".lower()
    # Highly specific contractual concepts should outrank broad words such as
    # "paid" or "leave" when both appear in the same clause.
    specific = (
        ("vacations", {"vacation", "annual leave", "holiday"}),
        ("work_termination", {"termination", "discharge", "dismiss", "just cause", "severance"}),
        ("seniority", {"seniority", "layoff", "recall", "vacancy"}),
        ("family_issues", {"parental", "maternity", "paternity", "adoption", "bereavement"}),
    )
    for topic, words in specific:
        hits = sorted(word for word in words if word in text)
        if hits:
            return topic, "Matched specific topic term: " + ", ".join(hits)
    scores = {topic: sum(1 for keyword in words if keyword in text) for topic, words in TOPIC_KEYWORDS.items()}
    topic, score = max(scores.items(), key=lambda pair: pair[1])
    if score == 0:
        return "unclassified", "No broad-topic keyword matched"
    hits = sorted(word for word in TOPIC_KEYWORDS[topic] if word in text)
    return topic, "Matched: " + ", ".join(hits)


def add_topics(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for clause in clauses:
        if clause["agent"] == "worker" and clause["clause_type"] == "right":
            topic, reason = assign_topic(clause)
        else:
            topic, reason = None, "Not a worker-rights clause"
        rows.append({**clause, "worker_right_topic": topic, "topic_rule": reason})
    return rows


def aggregate(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    number = len(clauses)
    pair_counts = Counter((row["agent"], row["clause_type"]) for row in clauses)
    type_counts = Counter(row["clause_type"] for row in clauses)
    topic_counts = Counter(
        row.get("worker_right_topic") for row in clauses
        if row.get("worker_right_topic")
    )
    worker_rights = pair_counts[("worker", "right")]

    def share(count: int) -> float:
        return round(count / number, 6) if number else 0.0

    agent_variables = {}
    for agent in ("worker", "firm", "union", "manager"):
        for legal_type in ("rights", "obligations", "permissions", "prohibitions"):
            singular = legal_type[:-1] if legal_type != "rights" else "right"
            agent_variables[f"{agent}_{legal_type}"] = pair_counts[(agent, singular)]

    broad_topics = list(TOPIC_KEYWORDS)
    return {
        "contract_level_measures": {
            "number_of_clauses": number,
            "number_of_worker_rights": worker_rights,
            "share_of_worker_rights": share(worker_rights),
            "share_of_worker_obligations": share(pair_counts[("worker", "obligation")]),
            "share_of_firm_obligations": share(pair_counts[("firm", "obligation")]),
            "share_of_permissions": share(type_counts["permission"]),
            "share_of_prohibitions": share(type_counts["prohibition"]),
            "worker_rights_topic_share": {
                topic: round(topic_counts[topic] / worker_rights, 6) if worker_rights else 0.0
                for topic in broad_topics
            },
        },
        "agent_variables": agent_variables,
        "worker_right_topic_variables": {topic: topic_counts[topic] for topic in broad_topics},
        "unclassified_worker_rights": topic_counts["unclassified"],
    }


def run_pipeline(source_text: str, target_step: int) -> dict[str, Any]:
    if not source_text.strip():
        raise ValueError("Paste contract text before running the pipeline.")
    target_step = max(1, min(11, target_step))
    result: dict[str, Any] = {
        "target_step": target_step,
        "source_text": normalize_space(source_text),
        "metadata": extract_metadata(source_text),
        "engine": "spaCy en_core_web_sm" if _nlp() else "heuristic fallback (install spaCy model for full parsing)",
    }
    if target_step == 1:
        return result
    result["cleaning"] = remove_non_core(source_text)
    if target_step == 2:
        return result
    result["sections"] = split_sections(result["cleaning"]["cleaned_text"])
    if target_step == 3:
        return result
    result["sentences"] = split_sentences(result["sections"])
    if target_step == 4:
        return result
    result["parsed_sentences"] = parse_sentences(result["sentences"])
    if target_step == 5:
        return result
    accepted, rejected = keep_svo(result["parsed_sentences"])
    result["clauses"] = accepted
    result["rejected_sentences"] = rejected
    if target_step == 6:
        return result
    result["clauses"] = add_agents(result["clauses"])
    if target_step == 7:
        return result
    result["clauses"] = identify_verb_structure(result["clauses"])
    if target_step == 8:
        return result
    result["clauses"] = add_clause_types(result["clauses"])
    if target_step == 9:
        return result
    result["measures"] = aggregate(result["clauses"])
    if target_step == 10:
        return result
    result["clauses"] = add_topics(result["clauses"])
    result["measures"] = aggregate(result["clauses"])
    result["methodology_note"] = (
        "Broad-topic assignment is an auditable MVP approximation. The original paper fitted 30 k-means "
        "clusters over its complete corpus and manually mapped them into seven broad topics; its fitted "
        "centroids and manual crosswalk are not available here."
    )
    return result
