"""
Flask backend for the Collaborator Finder web application.

This backend exposes a simple REST API for searching topics and retrieving
authors and institutions associated with a given topic using the OpenAlex API.
The API endpoints return JSON that can be consumed by a React front‑end.

Note: This code expects network access to the OpenAlex API. When running
locally, ensure that your environment can make outbound HTTP requests.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
# Enable CORS so the React front‑end can call this API from a different port
CORS(app)

# Base URL for the OpenAlex API
OPENALEX_BASE_URL = "https://api.openalex.org"


def fetch_openalex(endpoint: str, params: dict = None):
    """Helper function to call the OpenAlex API and return JSON data.

    Args:
        endpoint: The path after the base URL, e.g. "/topics".
        params: Query parameters for the request.

    Returns:
        The parsed JSON response from OpenAlex, or None on error.
    """
    url = f"{OPENALEX_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        app.logger.error(f"OpenAlex request failed: {exc}")
        return None


@app.route("/api/topics")
def search_topics():
    """Search for topics by name.

    Query parameters:
        q: The search string (required).
        limit: Maximum number of topics to return (optional, default 10).

    Returns:
        A JSON list of topics with their IDs and display names.
    """
    query = request.args.get("q", default="", type=str).strip()
    limit = request.args.get("limit", default=10, type=int)
    if not query:
        return jsonify({"error": "Parameter 'q' is required"}), 400

    params = {
        "search": query,
        "per_page": limit
    }
    data = fetch_openalex("/topics", params)
    if data is None:
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


@app.route("/api/authors/<path:topic_id>")
def get_authors_by_topic(topic_id: str):
    """Return a list of authors associated with a topic.

    Args:
        topic_id: The OpenAlex ID of the topic (e.g. "https://openalex.org/T11636").

    Query parameters:
        limit: Maximum number of authors to return (optional, default 50).

    Returns:
        A JSON list of authors, sorted by works_count descending.
    """
    limit = request.args.get("limit", default=50, type=int)

    params = {
        "filter": f"concept.id:{topic_id}",
        "sort": "works_count:desc",
        "per_page": limit
    }
    data = fetch_openalex("/authors", params)
    if data is None:
        return jsonify({"error": "Failed to fetch authors from OpenAlex"}), 502

    authors = []
    for item in data.get("results", []):
        authors.append({
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "works_count": item.get("works_count"),
            "cited_by_count": item.get("cited_by_count"),
            "last_known_institution": item.get("last_known_institution")
        })
    return jsonify({"authors": authors})


@app.route("/api/institutions/<path:topic_id>")
def get_institutions_by_topic(topic_id: str):
    """Return a list of institutions associated with a topic.

    Args:
        topic_id: The OpenAlex ID of the topic.

    Query parameters:
        limit: Maximum number of institutions to return (optional, default 50).

    Returns:
        A JSON list of institutions with geo coordinates, sorted by works_count.
    """
    limit = request.args.get("limit", default=50, type=int)
    params = {
        "filter": f"concept.id:{topic_id}",
        "sort": "works_count:desc",
        "per_page": limit
    }
    data = fetch_openalex("/institutions", params)
    if data is None:
        return jsonify({"error": "Failed to fetch institutions from OpenAlex"}), 502

    institutions = []
    for item in data.get("results", []):
        geo = item.get("geo", {}) if item else {}
        institutions.append({
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "works_count": item.get("works_count"),
            "cited_by_count": item.get("cited_by_count"),
            "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude"),
            "country_code": geo.get("country_code")
        })
    return jsonify({"institutions": institutions})


# Route to generate a co‑authorship network for a topic
@app.route("/api/coauthor-network/<path:topic_id>")
def get_coauthor_network(topic_id: str):
    """Return a co‑authorship network for works in a given topic.

    This endpoint fetches a set of works associated with the topic and builds
    a graph where each node is an author and each link represents a
    co‑authorship between two authors. The weight of an edge corresponds to the
    number of works that pair of authors wrote together.

    Args:
        topic_id: The OpenAlex ID of the topic.

    Query parameters:
        limit_works: Maximum number of works to process (default 200). Higher
            values will increase processing time and may trigger rate limits.

    Returns:
        A JSON object with `nodes` and `links` lists suitable for rendering with
        a network graph library such as react-d3-graph or react-force-graph.
    """
    limit_works = request.args.get("limit_works", default=200, type=int)
    # Select only the authorship information to reduce payload size
    params = {
        "filter": f"concepts.id:{topic_id}",
        "per_page": limit_works,
        "select": "authorships.author"
    }
    data = fetch_openalex("/works", params)
    if data is None:
        return jsonify({"error": "Failed to fetch works from OpenAlex"}), 502

    # Build a list of works with their authors
    works = data.get("results", [])
    # Map OpenAlex author IDs to index in node list and metadata
    node_map = {}
    nodes = []
    links = {}

    for work in works:
        authorships = work.get("authorships", [])
        # Extract authors (OpenAlex ID and display name)
        author_ids = []
        for auth in authorships:
            author = auth.get("author", {})
            author_id = author.get("id")
            if not author_id:
                continue
            # Map the author ID to an index in nodes
            if author_id not in node_map:
                index = len(nodes)
                node_map[author_id] = index
                nodes.append({
                    "id": author_id,
                    "label": author.get("display_name", author_id)
                })
            author_ids.append(author_id)
        # Generate all pairs of authors in this work
        for i in range(len(author_ids)):
            for j in range(i + 1, len(author_ids)):
                a = author_ids[i]
                b = author_ids[j]
                # Use tuple of sorted IDs to ensure uniqueness
                edge_key = tuple(sorted((a, b)))
                links[edge_key] = links.get(edge_key, 0) + 1

    # Convert edge dictionary to list of link objects
    link_list = []
    for (a, b), weight in links.items():
        link_list.append({
            "source": node_map[a],
            "target": node_map[b],
            "value": weight
        })

    return jsonify({"nodes": nodes, "links": link_list})


@app.route("/api/health")
def health_check():
    """Return a simple status message for health checks."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Run the Flask development server on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)