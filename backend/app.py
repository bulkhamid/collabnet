"""
Flask backend for the Collaborator Finder web application.

This backend exposes REST endpoints that wrap the OpenAlex API to provide
topic and author search, collaborator network construction, and institution
metadata. The endpoints are designed to be consumed by the React front-end in
the `frontend` directory.
"""

from __future__ import annotations

import calendar
import math
import statistics
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

from openalex_offline import OFFLINE_DATA

app = Flask(__name__)
# Enable CORS so the React front-end can call this API from a different port.
CORS(app)

# Base URL for the OpenAlex API.
OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_MAILTO = "collab-finder@example.com"
TRENDING_WINDOW_MONTHS = 6
PARALLEL_MAX_WORKERS = 5


def fetch_openalex(endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """Call the OpenAlex API and return JSON data."""
    url = f"{OPENALEX_BASE_URL}{endpoint}"
    query_params: Dict[str, Any] = {}
    if params:
        query_params.update(params)
    if "mailto" not in query_params:
        query_params["mailto"] = OPENALEX_MAILTO
    try:
        headers = {
            "User-Agent": "CollaboratorFinder/1.0 (mailto:collab-finder@example.com)",
            "Accept": "application/json"
        }
        response = requests.get(url, params=query_params, timeout=15, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = getattr(exc, "response", None)
        extra = ""
        if detail is not None:
            extra = f" | status={detail.status_code} body={detail.text}"
        app.logger.error("OpenAlex request failed: %s%s", exc, extra)
        return None


def extract_institution(raw_inst: Optional[Dict]) -> Optional[Dict]:
    """Flatten institution data returned by OpenAlex."""
    if not raw_inst:
        return None
    return {
        "id": raw_inst.get("id"),
        "display_name": raw_inst.get("display_name"),
        "type": raw_inst.get("type"),
        "country_code": raw_inst.get("country_code")
    }


def extract_primary_institution(item: Optional[Dict[str, Any]]) -> Optional[Dict]:
    """Return the first institution from plural/singular OpenAlex fields."""
    if not item:
        return None

    institutions = item.get("last_known_institutions")
    if isinstance(institutions, list) and institutions:
        primary = institutions[0] or {}
        return extract_institution(primary)

    return extract_institution(item.get("last_known_institution"))


def fetch_author_endpoint(endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Fetch author data with retry logic for deprecated select fields."""
    data = fetch_openalex(endpoint, params)
    if data is not None or "select" not in params:
        return data

    # Remove the plural field if it triggered a 403.
    select_fields = [field.strip() for field in params.get("select", "").split(",") if field.strip()]
    if select_fields:
        if "last_known_institutions" in select_fields:
            fallback_fields = [field for field in select_fields if field != "last_known_institutions"]
            if "last_known_institution" not in fallback_fields:
                fallback_fields.append("last_known_institution")
            fallback_params = dict(params)
            fallback_params["select"] = ",".join(fallback_fields)
            data = fetch_openalex(endpoint, fallback_params)
            if data is not None:
                return data

    # Final attempt without any select filter.
    stripped_params = {key: value for key, value in params.items() if key != "select"}
    return fetch_openalex(endpoint, stripped_params)


def fetch_works_endpoint(endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Fetch works data; retry without select or with smaller page size on 403."""
    data = fetch_openalex(endpoint, params)
    if data is not None:
        return data

    # Remove select to avoid invalid parameter responses.
    if "select" in params:
        stripped = dict(params)
        stripped.pop("select", None)
        data = fetch_openalex(endpoint, stripped)
        if data is not None:
            return data
        params = stripped

    # Reduce per_page to stay within rate limits if we still fail.
    per_page = params.get("per_page")
    if per_page and per_page > 50:
        reduced = dict(params)
        reduced["per_page"] = 50
        data = fetch_openalex(endpoint, reduced)
        if data is not None:
            return data

    return data


def fetch_institution_endpoint(endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Fetch institution data with a smaller page size fallback."""
    data = fetch_openalex(endpoint, params)
    if data is not None:
        return data

    per_page = params.get("per_page")
    if per_page and per_page > 50:
        reduced = dict(params)
        reduced["per_page"] = 50
        return fetch_openalex(endpoint, reduced)

    return data


def subtract_months(reference: date, months: int) -> date:
    """Return a date that is `months` before `reference` while preserving day."""
    if months <= 0:
        return reference

    year = reference.year
    month = reference.month - months
    while month <= 0:
        month += 12
        year -= 1

    day = min(reference.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def trending_window_strings(months: int = TRENDING_WINDOW_MONTHS) -> Dict[str, str]:
    """Compute boundary dates for recent and previous trending windows."""
    today = date.today()
    recent_start = subtract_months(today, months)
    previous_start = subtract_months(recent_start, months)
    previous_end = recent_start - timedelta(days=1)

    return {
        "today": today.strftime("%Y-%m-%d"),
        "recent_start": recent_start.strftime("%Y-%m-%d"),
        "previous_start": previous_start.strftime("%Y-%m-%d"),
        "previous_end": previous_end.strftime("%Y-%m-%d")
    }


def short_openalex_id(identifier: Optional[str]) -> Optional[str]:
    """Return the short-form OpenAlex identifier (e.g., C123) from a URL."""
    if not identifier:
        return None
    if identifier.startswith("https://"):
        return identifier.rstrip("/").rsplit("/", 1)[-1]
    return identifier


def extract_group_counts(payload: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert an OpenAlex group_by response into a key->metadata mapping."""
    if not payload:
        return {}

    entries = payload.get("group_by")
    if not entries:
        entries = payload.get("results", [])

    grouped: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        key = entry.get("key")
        if not key:
            continue
        raw_count = entry.get("count", entry.get("works_count"))
        try:
            count_value = int(raw_count)
        except (TypeError, ValueError):
            continue
        grouped[key] = {
            "count": count_value,
            "display_name": entry.get("key_display_name")
        }
    return grouped


def parallel_fetch(
    identifiers: Iterable[str],
    worker: Callable[[str], Optional[Dict[str, Any]]],
    *,
    max_workers: int = PARALLEL_MAX_WORKERS
) -> Dict[str, Dict[str, Any]]:
    """Fetch multiple OpenAlex resources concurrently."""
    seen: set[str] = set()
    ordered_ids: List[str] = []
    for identifier in identifiers:
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        ordered_ids.append(identifier)

    if not ordered_ids:
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    worker_count = min(max_workers, len(ordered_ids))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(worker, identifier): identifier
            for identifier in ordered_ids
        }
        for future in as_completed(future_map):
            identifier = future_map[future]
            try:
                value = future.result()
            except Exception as exc:  # pragma: no cover - defensive logging
                app.logger.error("Parallel fetch failed for %s: %s", identifier, exc)
                continue
            if value is not None:
                results[identifier] = value
    return results


def fetch_concept_brief(concept_id: str) -> Optional[Dict[str, Any]]:
    """Fetch summary details for a concept."""
    short_id = short_openalex_id(concept_id)
    if not short_id:
        return None
    data = fetch_openalex(f"/concepts/{short_id}")
    if data is None:
        return None
    return {
        "id": data.get("id", concept_id),
        "display_name": data.get("display_name"),
        "description": data.get("description"),
        "works_count": data.get("works_count")
    }


def fetch_author_brief(author_id: str) -> Optional[Dict[str, Any]]:
    """Fetch summary details for an author."""
    short_id = short_openalex_id(author_id)
    if not short_id:
        return None
    data = fetch_author_endpoint(f"/authors/{short_id}", {})
    if data is None:
        return None
    return {
        "id": data.get("id", author_id),
        "display_name": data.get("display_name"),
        "works_count": data.get("works_count"),
        "cited_by_count": data.get("cited_by_count"),
        "last_known_institution": extract_primary_institution(data)
    }


def compute_trending_topics(limit: int) -> Optional[List[Dict[str, Any]]]:
    """Compute trending topics based on recent publication growth."""
    windows = trending_window_strings()
    recent_params = {
        "filter": (
            f"from_publication_date:{windows['recent_start']},"
            f"to_publication_date:{windows['today']}"
        ),
        "group_by": "concepts.id",
        "sort": "count:desc",
        "per_page": max(limit * 4, 50)
    }
    recent_payload = fetch_works_endpoint("/works", recent_params)
    if recent_payload is None:
        return None
    recent_counts = extract_group_counts(recent_payload)
    if not recent_counts:
        return []

    previous_params = {
        "filter": (
            f"from_publication_date:{windows['previous_start']},"
            f"to_publication_date:{windows['previous_end']}"
        ),
        "group_by": "concepts.id",
        "per_page": max(limit * 4, 50)
    }
    previous_payload = fetch_works_endpoint("/works", previous_params)
    previous_counts = extract_group_counts(previous_payload) if previous_payload else {}

    entries: List[Dict[str, Any]] = []
    for concept_id, info in recent_counts.items():
        recent_count = info.get("count", 0)
        previous_count = previous_counts.get(concept_id, {}).get("count", 0)
        if recent_count <= 0:
            continue
        growth = recent_count - previous_count
        denominator = previous_count if previous_count > 0 else max(recent_count, 1)
        growth_rate = (recent_count - previous_count) / denominator
        entries.append({
            "id": concept_id,
            "recent_count": recent_count,
            "previous_count": previous_count,
            "growth": growth,
            "growth_rate": growth_rate,
            "display_name": info.get("display_name")
        })

    if not entries:
        return []

    positive_entries = [entry for entry in entries if entry["growth"] > 0]
    ranked_entries = positive_entries or entries
    ranked_entries.sort(
        key=lambda entry: (
            entry["growth"],
            entry["growth_rate"],
            entry["recent_count"]
        ),
        reverse=True
    )

    detail_ids = [entry["id"] for entry in ranked_entries[:limit * 2]]
    details = parallel_fetch(detail_ids, fetch_concept_brief)

    trending_topics: List[Dict[str, Any]] = []
    for entry in ranked_entries:
        if len(trending_topics) >= limit:
            break
        detail = details.get(entry["id"])
        display_name = (
            detail.get("display_name")
            if detail
            else entry.get("display_name")
        )
        record = {
            "id": detail.get("id", entry["id"]) if detail else entry["id"],
            "display_name": display_name or entry["id"],
            "description": detail.get("description") if detail else None,
            "works_count": detail.get("works_count") if detail else entry["recent_count"],
            "recent_publications": entry["recent_count"],
            "growth": entry["growth"]
        }
        trending_topics.append(record)

    return trending_topics


def compute_trending_scientists(limit: int) -> Optional[List[Dict[str, Any]]]:
    """Compute trending authors based on recent output and citation impact."""
    windows = trending_window_strings()
    recent_params = {
        "filter": (
            f"from_publication_date:{windows['recent_start']},"
            f"to_publication_date:{windows['today']}"
        ),
        "group_by": "authorships.author.id",
        "sort": "count:desc",
        "per_page": max(limit * 5, 75)
    }
    recent_payload = fetch_works_endpoint("/works", recent_params)
    if recent_payload is None:
        return None
    recent_counts = extract_group_counts(recent_payload)
    if not recent_counts:
        return []

    previous_params = {
        "filter": (
            f"from_publication_date:{windows['previous_start']},"
            f"to_publication_date:{windows['previous_end']}"
        ),
        "group_by": "authorships.author.id",
        "per_page": max(limit * 5, 75)
    }
    previous_payload = fetch_works_endpoint("/works", previous_params)
    previous_counts = extract_group_counts(previous_payload) if previous_payload else {}

    entries: List[Dict[str, Any]] = []
    for author_id, info in recent_counts.items():
        recent_count = info.get("count", 0)
        if recent_count <= 0:
            continue
        previous_count = previous_counts.get(author_id, {}).get("count", 0)
        growth = recent_count - previous_count
        entries.append({
            "id": author_id,
            "recent_count": recent_count,
            "previous_count": previous_count,
            "growth": growth,
            "display_name": info.get("display_name")
        })

    if not entries:
        return []

    entries.sort(key=lambda entry: (entry["recent_count"], entry["growth"]), reverse=True)
    candidate_ids = [entry["id"] for entry in entries[:limit * 3]]
    author_details = parallel_fetch(candidate_ids, fetch_author_brief)

    scientists: List[Dict[str, Any]] = []
    for entry in entries:
        detail = author_details.get(entry["id"])
        if detail:
            display_name = detail.get("display_name") or entry.get("display_name") or entry["id"]
            works_count = detail.get("works_count")
            cited_by_count = detail.get("cited_by_count")
            institution = detail.get("last_known_institution")
        else:
            display_name = entry.get("display_name") or entry["id"]
            works_count = None
            cited_by_count = None
            institution = None

        scientists.append({
            "id": detail.get("id", entry["id"]) if detail else entry["id"],
            "display_name": display_name,
            "works_count": works_count if works_count is not None else entry["recent_count"],
            "cited_by_count": cited_by_count,
            "last_known_institution": institution,
            "recent_publications": entry["recent_count"],
            "growth": entry["growth"]
        })

    scientists.sort(
        key=lambda item: (
            item["recent_publications"],
            item["cited_by_count"] or 0,
            item["growth"]
        ),
        reverse=True
    )
    return scientists[:limit]


def fetch_author_works(author_id: str, *, per_page: int = 200) -> Optional[List[Dict[str, Any]]]:
    """Fetch a slice of works for an author."""
    short_id = short_openalex_id(author_id)
    author_filter = short_id or author_id
    per_page = max(1, min(per_page, 200))
    params = {
        "filter": f"authorships.author.id:{author_filter}",
        "per_page": per_page,
        "sort": "publication_year:desc",
        "select": "id,title,publication_year,concepts,authorships,cited_by_count"
    }
    payload = fetch_works_endpoint("/works", params)
    if payload is None:
        return None
    return payload.get("results", [])


def build_research_profile(brief: Dict[str, Any], works: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize author metadata, works, concepts, and coauthors for scoring."""
    author_id = brief.get("id")
    normalized_author_ids = {author_id, short_openalex_id(author_id)} if author_id else set()

    concept_counts: Dict[str, float] = {}
    concept_names: Dict[str, str] = {}
    coauthors: Dict[str, str] = {}
    coauthor_graph: Dict[str, set[str]] = {}
    works_summary: List[Dict[str, Any]] = []
    publication_years: List[int] = []

    for work in works:
        # Publication year extraction
        year_raw = work.get("publication_year")
        year: Optional[int] = None
        if isinstance(year_raw, int):
            year = year_raw
        elif isinstance(year_raw, str):
            try:
                year = int(year_raw)
            except ValueError:
                year = None
        if year is not None:
            publication_years.append(year)

        authors_in_work: List[Dict[str, str]] = []
        for authorship in work.get("authorships", []):
            author_meta = authorship.get("author") or {}
            collaborator_id = author_meta.get("id")
            if not collaborator_id:
                continue
            collaborator_name = author_meta.get("display_name") or collaborator_id
            authors_in_work.append({"id": collaborator_id, "name": collaborator_name})

        # Populate coauthor graph edges
        for i in range(len(authors_in_work)):
            for j in range(i + 1, len(authors_in_work)):
                src = authors_in_work[i]["id"]
                dst = authors_in_work[j]["id"]
                coauthor_graph.setdefault(src, set()).add(dst)
                coauthor_graph.setdefault(dst, set()).add(src)

        # Track direct coauthors
        for collaborator in authors_in_work:
            collaborator_id = collaborator["id"]
            if collaborator_id in normalized_author_ids:
                continue
            coauthors.setdefault(collaborator_id, collaborator["name"])

        work_concepts: List[Dict[str, str]] = []
        for concept in work.get("concepts", []):
            concept_id = concept.get("id")
            if not concept_id:
                continue
            concept_name = concept.get("display_name") or concept_id
            weight = concept.get("score") or concept.get("relevance_score") or 1.0
            concept_counts[concept_id] = concept_counts.get(concept_id, 0.0) + float(weight)
            concept_names[concept_id] = concept_name
            work_concepts.append({"id": concept_id, "name": concept_name})

        works_summary.append({
            "id": work.get("id"),
            "title": work.get("title"),
            "year": year,
            "concepts": work_concepts,
            "authors": authors_in_work,
            "cited_by_count": work.get("cited_by_count")
        })

    coauthor_graph.setdefault(author_id, set())

    median_year: Optional[int]
    if publication_years:
        median_year = int(round(statistics.median(publication_years)))
    else:
        median_year = None

    return {
        "id": author_id,
        "display_name": brief.get("display_name") or author_id,
        "works_count": brief.get("works_count"),
        "cited_by_count": brief.get("cited_by_count"),
        "institution": brief.get("last_known_institution"),
        "concept_counts": concept_counts,
        "concept_names": concept_names,
        "works": works_summary,
        "coauthors": coauthors,
        "coauthor_graph": coauthor_graph,
        "median_year": median_year
    }


def collect_research_profile(author_id: str, *, works_limit: int = 200) -> Optional[Dict[str, Any]]:
    """Gather the data needed to evaluate compatibility for an author."""
    brief = fetch_author_brief(author_id)
    works = fetch_author_works(author_id, per_page=works_limit) if brief is not None else None
    if brief is None or works is None:
        offline_brief = OFFLINE_DATA.author_profile(author_id)
        if offline_brief is None:
            return None
        offline_works = OFFLINE_DATA.author_works(author_id) or []
        return build_research_profile(offline_brief, offline_works)
    return build_research_profile(brief, works)


def cosine_similarity(vector_a: Dict[str, float], vector_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    if not vector_a or not vector_b:
        return 0.0
    dot_product = 0.0
    for key, value in vector_a.items():
        corresponding = vector_b.get(key)
        if corresponding is not None:
            dot_product += float(value) * float(corresponding)
    if dot_product == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(float(value) ** 2 for value in vector_a.values()))
    norm_b = math.sqrt(sum(float(value) ** 2 for value in vector_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def compute_topic_similarity_metric(
    user_profile: Dict[str, Any],
    target_profile: Dict[str, Any]
) -> Tuple[float, List[str], List[str]]:
    """Return cosine similarity and descriptive overlaps between concept vectors."""
    user_vector = user_profile.get("concept_counts", {})
    target_vector = target_profile.get("concept_counts", {})
    similarity = cosine_similarity(user_vector, target_vector)
    overlap_ids = set(user_vector.keys()) & set(target_vector.keys())

    overlaps: List[Tuple[str, str, float, float]] = []
    for concept_id in overlap_ids:
        concept_name = (
            user_profile.get("concept_names", {}).get(concept_id)
            or target_profile.get("concept_names", {}).get(concept_id)
            or concept_id
        )
        overlaps.append((
            concept_id,
            concept_name,
            float(user_vector.get(concept_id, 0.0)),
            float(target_vector.get(concept_id, 0.0))
        ))

    overlaps.sort(key=lambda item: (item[2] + item[3]), reverse=True)
    overlap_descriptions = [
        f"{name} (you {user_weight:.2f} · them {target_weight:.2f})"
        for _, name, user_weight, target_weight in overlaps[:5]
    ]
    ordered_overlap_ids = [concept_id for concept_id, *_ in overlaps]
    return similarity, overlap_descriptions, ordered_overlap_ids


def merge_coauthor_graphs(profiles: Iterable[Dict[str, Any]]) -> Dict[str, set[str]]:
    """Merge per-author coauthor graphs into a combined adjacency map."""
    combined: Dict[str, set[str]] = {}
    for profile in profiles:
        graph = profile.get("coauthor_graph") or {}
        for source, neighbors in graph.items():
            combined.setdefault(source, set()).update(neighbors)
    return combined


def shortest_path_length(
    graph: Dict[str, set[str]],
    start: Optional[str],
    goal: Optional[str],
    *,
    max_depth: int = 5
) -> Optional[int]:
    """Compute the shortest co-author path length between two authors."""
    if not start or not goal:
        return None
    if start == goal:
        return 0

    queue = deque([(start, 0)])
    visited = {start}

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor in graph.get(node, []):
            if neighbor == goal:
                return depth + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
    return None


def coauthor_distance_score(path_length: Optional[int]) -> float:
    """Map shortest path length to a normalized 0-100 compatibility score."""
    if path_length is None:
        return 0.0
    if path_length <= 1:
        return 100.0
    if path_length == 2:
        return 80.0
    if path_length == 3:
        return 55.0
    if path_length == 4:
        return 35.0
    return 15.0


def compute_institution_score(
    user_profile: Dict[str, Any],
    target_profile: Dict[str, Any]
) -> float:
    """Compare institutional alignment between user and target."""
    user_inst = user_profile.get("institution") or {}
    target_inst = target_profile.get("institution") or {}
    if not user_inst or not target_inst:
        return 0.0

    if user_inst.get("id") and target_inst.get("id") and user_inst["id"] == target_inst["id"]:
        return 100.0
    if user_inst.get("country_code") and user_inst.get("country_code") == target_inst.get("country_code"):
        return 80.0
    if user_inst.get("type") and user_inst.get("type") == target_inst.get("type"):
        return 60.0
    if user_inst.get("country_code") and target_inst.get("country_code"):
        return 40.0
    return 20.0 if user_inst and target_inst else 0.0


def compute_recency_score(
    user_profile: Dict[str, Any],
    target_profile: Dict[str, Any]
) -> Tuple[float, Optional[int], Optional[int]]:
    """Score how closely aligned the publication recency is."""
    user_median = user_profile.get("median_year")
    target_median = target_profile.get("median_year")
    if not user_median or not target_median:
        return 0.0, user_median, target_median
    difference = abs(int(user_median) - int(target_median))
    score = max(0.0, 100.0 - difference * 12.5)
    return score, int(user_median), int(target_median)


def build_aligned_publications(
    user_profile: Dict[str, Any],
    target_profile: Dict[str, Any],
    overlap_ids: Iterable[str]
) -> List[Dict[str, Any]]:
    """Select target works that align with the user's dominant concepts."""
    overlap_set = set(list(overlap_ids)[:10])
    if not overlap_set:
        return []

    publications: List[Dict[str, Any]] = []
    concept_lookup = {**target_profile.get("concept_names", {}), **user_profile.get("concept_names", {})}
    for work in target_profile.get("works", []):
        concepts = work.get("concepts") or []
        matched = [concept for concept in concepts if concept.get("id") in overlap_set]
        if not matched:
            continue
        publications.append({
            "title": work.get("title") or "Untitled work",
            "year": work.get("year"),
            "concepts": [concept_lookup.get(concept.get("id"), concept.get("name")) for concept in matched]
        })
    publications.sort(key=lambda item: (item["year"] or 0), reverse=True)
    return publications[:5]


def clamp_score(value: float) -> int:
    """Clamp a floating-point score into an integer [0, 100]."""
    return int(round(max(0.0, min(100.0, value))))


def compute_compatibility(
    user_profile: Dict[str, Any],
    target_profile: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate compatibility breakdown and supporting evidence."""
    topic_similarity, overlap_descriptions, overlap_ids = compute_topic_similarity_metric(
        user_profile, target_profile
    )
    topic_score = clamp_score(topic_similarity * 100)

    combined_graph = merge_coauthor_graphs([user_profile, target_profile])
    combined_graph.setdefault(user_profile.get("id"), set())
    combined_graph.setdefault(target_profile.get("id"), set())
    path_length = shortest_path_length(
        combined_graph,
        user_profile.get("id"),
        target_profile.get("id"),
        max_depth=6
    )
    coauthor_score = clamp_score(coauthor_distance_score(path_length))

    mutual_ids = set(user_profile.get("coauthors", {}).keys()) & set(target_profile.get("coauthors", {}).keys())
    mutual_coauthors = [
        user_profile["coauthors"].get(author_id)
        or target_profile["coauthors"].get(author_id)
        or author_id
        for author_id in mutual_ids
    ]
    mutual_coauthors.sort()

    institution_score = clamp_score(compute_institution_score(user_profile, target_profile))
    recency_score_value, user_median_year, target_median_year = compute_recency_score(
        user_profile, target_profile
    )
    recency_score = clamp_score(recency_score_value)

    overall_score = clamp_score(
        topic_score * 0.40
        + coauthor_score * 0.30
        + institution_score * 0.20
        + recency_score * 0.10
    )

    aligned_publications = build_aligned_publications(user_profile, target_profile, overlap_ids)

    breakdown = {
        "overall": overall_score,
        "topic_similarity": topic_score,
        "coauthor_distance": coauthor_score,
        "institution_proximity": institution_score,
        "recency_alignment": recency_score,
        "coauthor_path_length": path_length
    }
    evidence = {
        "overlapping_concepts": overlap_descriptions,
        "shared_coauthors": mutual_coauthors[:5],
        "aligned_publications": aligned_publications,
        "median_publication_years": {
            "user": user_median_year,
            "target": target_median_year
        }
    }
    return {"breakdown": breakdown, "evidence": evidence}


def empty_compatibility_payload() -> Dict[str, Any]:
    """Return a default compatibility payload with zeroed scores."""
    return {
        "breakdown": {
            "overall": 0,
            "topic_similarity": 0,
            "coauthor_distance": 0,
            "institution_proximity": 0,
            "recency_alignment": 0,
            "coauthor_path_length": None
        },
        "evidence": {
            "overlapping_concepts": [],
            "shared_coauthors": [],
            "aligned_publications": [],
            "median_publication_years": {
                "user": None,
                "target": None
            }
        }
    }


def extract_geo(raw_geo: Optional[Dict]) -> Dict:
    """Normalize geo payloads returned by OpenAlex."""
    raw_geo = raw_geo or {}
    return {
        "latitude": raw_geo.get("latitude"),
        "longitude": raw_geo.get("longitude"),
        "city": raw_geo.get("city"),
        "region": raw_geo.get("region"),
        "country_code": raw_geo.get("country_code")
    }


def build_coauthor_graph(
    works: Iterable[Dict],
    focus_author_id: Optional[str] = None
) -> Dict:
    """Construct a co-authorship graph from a list of works."""
    node_map: Dict[str, int] = {}
    nodes: List[Dict] = []
    link_weights: Counter[Tuple[str, str]] = Counter()
    degrees: Counter[str] = Counter()

    for work in works:
        auths = work.get("authorships", [])
        author_ids: List[str] = []

        for auth in auths:
            author = auth.get("author") or {}
            author_id = author.get("id")
            if not author_id:
                continue

            if author_id not in node_map:
                node_map[author_id] = len(nodes)
                nodes.append({
                    "id": author_id,
                    "name": author.get("display_name", author_id),
                    "is_focus": author_id == focus_author_id
                })

            author_ids.append(author_id)

        # Update edge weights for every unique pair within a work.
        for i in range(len(author_ids)):
            for j in range(i + 1, len(author_ids)):
                a, b = sorted((author_ids[i], author_ids[j]))
                link_weights[(a, b)] += 1
                degrees[a] += 1
                degrees[b] += 1

    links = [{"source": a, "target": b, "weight": weight}
             for (a, b), weight in link_weights.items()]

    for node in nodes:
        node_id = node["id"]
        node["degree"] = degrees.get(node_id, 0)

    top_authors = sorted(nodes, key=lambda item: item.get("degree", 0), reverse=True)

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "node_count": len(nodes),
            "link_count": len(links),
            "top_authors": [
                {"id": item["id"], "name": item["name"], "degree": item.get("degree", 0)}
                for item in top_authors[:10]
            ]
        }
    }


@app.route("/api/health")
def health_check():
    """Return a simple status message for health checks."""
    return jsonify({"status": "ok"})


@app.route("/api/trending/topics")
def get_trending_topics():
    """Return topics experiencing the fastest growth in recent publications."""
    limit = request.args.get("limit", default=5, type=int)
    limit = max(1, min(limit, 20))
    topics = compute_trending_topics(limit)
    if topics is None:
        topics = OFFLINE_DATA.trending_topics(limit) or []
    return jsonify({"topics": topics})


@app.route("/api/trending/scientists")
def get_trending_scientists():
    """Return authors with the strongest recent publication momentum."""
    limit = request.args.get("limit", default=5, type=int)
    limit = max(1, min(limit, 20))
    scientists = compute_trending_scientists(limit)
    if scientists is None:
        scientists = OFFLINE_DATA.trending_scientists(limit) or []
    return jsonify({"scientists": scientists})


@app.route("/api/match", methods=["POST"])
def post_match():
    """Compute a compatibility profile between the user and a target researcher."""
    payload = request.get_json(silent=True) or {}
    target_id = payload.get("target_id")
    if not target_id:
        return jsonify({"error": "Parameter 'target_id' is required"}), 400

    user_id = payload.get("user_id") or OFFLINE_DATA.default_user_id()

    user_profile = collect_research_profile(user_id)
    target_profile = collect_research_profile(target_id)

    if user_profile is None or target_profile is None:
        app.logger.warning(
            "Compatibility fallback used for user=%s target=%s",
            user_id,
            target_id
        )
        return jsonify(empty_compatibility_payload())

    result = compute_compatibility(user_profile, target_profile)
    result["user_id"] = user_profile.get("id")
    result["target_id"] = target_profile.get("id")
    return jsonify(result)


@app.route("/api/topics")
def search_topics():
    """Search for topics by name."""
    query = (request.args.get("q") or request.args.get("query") or "").strip()
    limit = request.args.get("limit", default=10, type=int)
    if not query:
        return jsonify({"error": "Parameter 'q' is required"}), 400

    params = {
        "search": query,
        "per_page": min(limit, 50)
    }
    data = fetch_openalex("/topics", params)
    if data is None:
        topics = OFFLINE_DATA.search_topics(query, limit)
        if topics is not None:
            return jsonify({"topics": topics})
        return jsonify({"error": "Failed to fetch topics from OpenAlex"}), 502

    topics = []
    for item in data.get("results", []):
        topics.append({
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "description": item.get("description"),
            "works_count": item.get("works_count")
        })
    return jsonify({"topics": topics})


@app.route("/api/authors")
def search_authors():
    """Search for authors by name."""
    query = (request.args.get("q") or request.args.get("query") or "").strip()
    limit = request.args.get("limit", default=10, type=int)
    if not query:
        return jsonify({"error": "Parameter 'q' is required"}), 400

    params = {
        "search": query,
        "per_page": min(limit, 50),
    }
    data = fetch_author_endpoint("/authors", params)
    if data is None:
        authors = OFFLINE_DATA.search_authors(query, limit)
        if authors is not None:
            return jsonify({"authors": authors})
        return jsonify({"error": "Failed to fetch authors from OpenAlex"}), 502

    authors = []
    for item in data.get("results", []):
        authors.append({
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "works_count": item.get("works_count"),
            "cited_by_count": item.get("cited_by_count"),
            "last_known_institution": extract_primary_institution(item)
        })
    return jsonify({"authors": authors})


@app.route("/api/authors/<path:topic_id>")
def get_authors_by_topic(topic_id: str):
    """Return a list of authors associated with a topic."""
    limit = request.args.get("limit", default=50, type=int)

    params = {
        "filter": f"concepts.id:{topic_id}",
        "sort": "works_count:desc",
        "per_page": limit
    }
    data = fetch_author_endpoint("/authors", params)
    if data is None:
        authors = OFFLINE_DATA.authors_by_topic(topic_id, limit)
        if authors is not None:
            return jsonify({"authors": authors})
        return jsonify({"error": "Failed to fetch authors from OpenAlex"}), 502

    authors = []
    for item in data.get("results", []):
        authors.append({
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "works_count": item.get("works_count"),
            "cited_by_count": item.get("cited_by_count"),
            "last_known_institution": extract_primary_institution(item)
        })
    return jsonify({"authors": authors})


@app.route("/api/author/<path:author_id>")
def get_author_profile(author_id: str):
    """Return profile details for a single author."""
    params: Dict[str, Any] = {}
    data = fetch_author_endpoint(f"/authors/{author_id}", params)
    if data is None:
        author = OFFLINE_DATA.author_profile(author_id)
        if author is not None:
            return jsonify({"author": author})
        return jsonify({"error": "Failed to fetch author profile from OpenAlex"}), 502

    author = {
        "id": data.get("id"),
        "display_name": data.get("display_name"),
        "works_count": data.get("works_count"),
        "cited_by_count": data.get("cited_by_count"),
        "last_known_institution": extract_institution(data.get("last_known_institution"))
    }
    return jsonify({"author": author})


@app.route("/api/institutions/<path:topic_id>")
def get_institutions_by_topic(topic_id: str):
    """Return a list of institutions associated with a topic."""
    limit = request.args.get("limit", default=50, type=int)
    params = {
        "filter": f"concepts.id:{topic_id}",
        "sort": "works_count:desc",
        "per_page": limit
    }
    data = fetch_institution_endpoint("/institutions", params)
    if data is None:
        institutions = OFFLINE_DATA.institutions_by_topic(topic_id, limit)
        if institutions is not None:
            return jsonify({"institutions": institutions})
        return jsonify({"error": "Failed to fetch institutions from OpenAlex"}), 502

    institutions = []
    for item in data.get("results", []):
        geo = extract_geo(item.get("geo"))
        institutions.append({
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "works_count": item.get("works_count"),
            "cited_by_count": item.get("cited_by_count"),
            **geo
        })
    return jsonify({"institutions": institutions})


@app.route("/api/coauthor-network/<path:topic_id>")
def get_coauthor_network(topic_id: str):
    """Return a co-authorship network for works in a given topic."""
    limit_works = request.args.get("limit_works", default=200, type=int)
    limit_works = max(1, min(limit_works, 200))
    params = {
        "filter": f"concepts.id:{topic_id}",
        "per_page": limit_works
    }
    data = fetch_works_endpoint("/works", params)
    if data is None:
        network = OFFLINE_DATA.topic_network(topic_id)
        if network is not None:
            return jsonify(network)
        return jsonify({"error": "Failed to fetch works from OpenAlex"}), 502

    works = data.get("results", [])
    return jsonify(build_coauthor_graph(works))


@app.route("/api/coauthor-network/author/<path:author_id>")
def get_author_coauthor_network(author_id: str):
    """Return a co-authorship network centered on a specific author."""
    limit_works = request.args.get("limit_works", default=200, type=int)
    limit_works = max(1, min(limit_works, 200))
    params = {
        "filter": f"authorships.author.id:{author_id}",
        "per_page": limit_works
    }
    data = fetch_works_endpoint("/works", params)
    if data is None:
        network = OFFLINE_DATA.author_network(author_id)
        if network is not None:
            return jsonify(network)
        return jsonify({"error": "Failed to fetch works from OpenAlex"}), 502

    works = data.get("results", [])
    return jsonify(build_coauthor_graph(works, focus_author_id=author_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
