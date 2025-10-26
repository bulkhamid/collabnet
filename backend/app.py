"""
Flask backend for the Collaborator Finder web application.

This backend exposes REST endpoints that wrap the OpenAlex API to provide
topic and author search, collaborator network construction, and institution
metadata. The endpoints are designed to be consumed by the React front-end in
the `frontend` directory.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
