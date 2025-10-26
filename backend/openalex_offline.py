"""
Offline fallback dataset for environments without OpenAlex connectivity.

The helpers in this module return sample payloads that mimic the shape of the
OpenAlex API so the front-end can continue functioning during demos.
"""

from __future__ import annotations

import copy
from collections import Counter
from typing import Dict, List, Optional


def _copy_slice(items: List[Dict], limit: int) -> List[Dict]:
    """Return a deep copy of list items up to limit (or all when limit < 0)."""
    if limit is None or limit < 0:
        end = None
    else:
        end = limit
    return copy.deepcopy(items[:end])


def _build_graph(nodes: List[Dict], edges: List[Dict]) -> Dict:
    """Populate node degrees and stats for a predefined network."""
    degrees: Counter = Counter()
    for edge in edges:
        weight = edge.get("weight", 1)
        degrees[edge["source"]] += weight
        degrees[edge["target"]] += weight

    populated_nodes = []
    for node in nodes:
        node_copy = copy.deepcopy(node)
        node_copy["degree"] = degrees.get(node_copy["id"], 0)
        populated_nodes.append(node_copy)

    populated_edges = [copy.deepcopy(edge) for edge in edges]
    top_authors = sorted(populated_nodes, key=lambda entry: entry.get("degree", 0), reverse=True)[:10]

    return {
        "nodes": populated_nodes,
        "links": populated_edges,
        "stats": {
            "node_count": len(populated_nodes),
            "link_count": len(populated_edges),
            "top_authors": [
                {
                    "id": node["id"],
                    "name": node.get("name", node["id"]),
                    "degree": node.get("degree", 0)
                }
                for node in top_authors
            ]
        }
    }


class OfflineOpenAlexData:
    """Simple in-memory sample data for offline use."""

    def __init__(self) -> None:
        self._topics: List[Dict] = [
            {
                "id": "https://openalex.org/T101",
                "display_name": "Machine Learning",
                "description": (
                    "Algorithms and statistical models enabling computers to learn patterns from data."
                ),
                "works_count": 2450000
            },
            {
                "id": "https://openalex.org/T202",
                "display_name": "Coral Reef Ecology",
                "description": (
                    "Dynamics of coral reef ecosystems under environmental and climate stressors."
                ),
                "works_count": 82000
            }
        ]

        self._author_lookup: Dict[str, Dict] = {
            "https://openalex.org/A1969205032": {
                "id": "https://openalex.org/A1969205032",
                "display_name": "Fei-Fei Li",
                "works_count": 420,
                "cited_by_count": 98000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4200000001",
                    "display_name": "Stanford University",
                    "type": "education",
                    "country_code": "US"
                }
            },
            "https://openalex.org/A2093607087": {
                "id": "https://openalex.org/A2093607087",
                "display_name": "Andrew Ng",
                "works_count": 350,
                "cited_by_count": 178000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4200000001",
                    "display_name": "Stanford University",
                    "type": "education",
                    "country_code": "US"
                }
            },
            "https://openalex.org/A2053681587": {
                "id": "https://openalex.org/A2053681587",
                "display_name": "Geoffrey Hinton",
                "works_count": 590,
                "cited_by_count": 244000,
                "last_known_institution": {
                    "id": "https://openalex.org/I120372680",
                    "display_name": "University of Toronto",
                    "type": "education",
                    "country_code": "CA"
                }
            },
            "https://openalex.org/A1983283131": {
                "id": "https://openalex.org/A1983283131",
                "display_name": "Yoshua Bengio",
                "works_count": 670,
                "cited_by_count": 225000,
                "last_known_institution": {
                    "id": "https://openalex.org/I145106085",
                    "display_name": "Universite de Montreal",
                    "type": "education",
                    "country_code": "CA"
                }
            },
            "https://openalex.org/A1962342457": {
                "id": "https://openalex.org/A1962342457",
                "display_name": "Yann LeCun",
                "works_count": 540,
                "cited_by_count": 203000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4210117015",
                    "display_name": "Meta AI",
                    "type": "business",
                    "country_code": "US"
                }
            },
            "https://openalex.org/A1971464923": {
                "id": "https://openalex.org/A1971464923",
                "display_name": "Jeff Dean",
                "works_count": 310,
                "cited_by_count": 167000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4210217567",
                    "display_name": "Google Research",
                    "type": "business",
                    "country_code": "US"
                }
            },
            "https://openalex.org/A2112779243": {
                "id": "https://openalex.org/A2112779243",
                "display_name": "Ove Hoegh-Guldberg",
                "works_count": 420,
                "cited_by_count": 96000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4210146751",
                    "display_name": "University of Queensland",
                    "type": "education",
                    "country_code": "AU"
                }
            },
            "https://openalex.org/A2112743840": {
                "id": "https://openalex.org/A2112743840",
                "display_name": "Terry Hughes",
                "works_count": 380,
                "cited_by_count": 92000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4210147050",
                    "display_name": "James Cook University",
                    "type": "education",
                    "country_code": "AU"
                }
            },
            "https://openalex.org/A2135812432": {
                "id": "https://openalex.org/A2135812432",
                "display_name": "Enric Sala",
                "works_count": 250,
                "cited_by_count": 41000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4200208672",
                    "display_name": "National Geographic Society",
                    "type": "nonprofit",
                    "country_code": "US"
                }
            },
            "https://openalex.org/A2128745141": {
                "id": "https://openalex.org/A2128745141",
                "display_name": "Maria Dornelas",
                "works_count": 210,
                "cited_by_count": 36000,
                "last_known_institution": {
                    "id": "https://openalex.org/I4210108427",
                    "display_name": "University of St Andrews",
                    "type": "education",
                    "country_code": "GB"
                }
            }
        }

        self._topic_authors: Dict[str, List[str]] = {
            "https://openalex.org/T101": [
                "https://openalex.org/A1969205032",
                "https://openalex.org/A2093607087",
                "https://openalex.org/A2053681587",
                "https://openalex.org/A1983283131",
                "https://openalex.org/A1962342457",
                "https://openalex.org/A1971464923"
            ],
            "https://openalex.org/T202": [
                "https://openalex.org/A2112779243",
                "https://openalex.org/A2112743840",
                "https://openalex.org/A2135812432",
                "https://openalex.org/A2128745141"
            ]
        }

        self._topic_institutions: Dict[str, List[Dict]] = {
            "https://openalex.org/T101": [
                {
                    "id": "https://openalex.org/I4200000001",
                    "display_name": "Stanford University",
                    "works_count": 128000,
                    "cited_by_count": 410000,
                    "latitude": 37.4275,
                    "longitude": -122.1697,
                    "city": "Stanford",
                    "region": "California",
                    "country_code": "US"
                },
                {
                    "id": "https://openalex.org/I120372680",
                    "display_name": "University of Toronto",
                    "works_count": 98000,
                    "cited_by_count": 320000,
                    "latitude": 43.6629,
                    "longitude": -79.3957,
                    "city": "Toronto",
                    "region": "Ontario",
                    "country_code": "CA"
                },
                {
                    "id": "https://openalex.org/I4210217567",
                    "display_name": "Google DeepMind",
                    "works_count": 61000,
                    "cited_by_count": 176000,
                    "latitude": 51.5237,
                    "longitude": -0.1436,
                    "city": "London",
                    "region": "England",
                    "country_code": "GB"
                }
            ],
            "https://openalex.org/T202": [
                {
                    "id": "https://openalex.org/I4210146751",
                    "display_name": "University of Queensland",
                    "works_count": 26400,
                    "cited_by_count": 98000,
                    "latitude": -27.4975,
                    "longitude": 153.0137,
                    "city": "Brisbane",
                    "region": "Queensland",
                    "country_code": "AU"
                },
                {
                    "id": "https://openalex.org/I4210147050",
                    "display_name": "James Cook University",
                    "works_count": 18400,
                    "cited_by_count": 72000,
                    "latitude": -19.329,
                    "longitude": 146.757,
                    "city": "Townsville",
                    "region": "Queensland",
                    "country_code": "AU"
                },
                {
                    "id": "https://openalex.org/I4210149301",
                    "display_name": "Woods Hole Oceanographic Institution",
                    "works_count": 15800,
                    "cited_by_count": 54000,
                    "latitude": 41.5265,
                    "longitude": -70.6731,
                    "city": "Woods Hole",
                    "region": "Massachusetts",
                    "country_code": "US"
                }
            ]
        }

        self._topic_networks: Dict[str, Dict] = {
            "https://openalex.org/T101": _build_graph(
                nodes=[
                    {"id": "https://openalex.org/A1969205032", "name": "Fei-Fei Li"},
                    {"id": "https://openalex.org/A2093607087", "name": "Andrew Ng"},
                    {"id": "https://openalex.org/A2053681587", "name": "Geoffrey Hinton"},
                    {"id": "https://openalex.org/A1983283131", "name": "Yoshua Bengio"},
                    {"id": "https://openalex.org/A1962342457", "name": "Yann LeCun"},
                    {"id": "https://openalex.org/A1971464923", "name": "Jeff Dean"}
                ],
                edges=[
                    {"source": "https://openalex.org/A1969205032", "target": "https://openalex.org/A2093607087", "weight": 3},
                    {"source": "https://openalex.org/A1969205032", "target": "https://openalex.org/A2053681587", "weight": 1},
                    {"source": "https://openalex.org/A2093607087", "target": "https://openalex.org/A1971464923", "weight": 2},
                    {"source": "https://openalex.org/A2053681587", "target": "https://openalex.org/A1983283131", "weight": 4},
                    {"source": "https://openalex.org/A1983283131", "target": "https://openalex.org/A1962342457", "weight": 3},
                    {"source": "https://openalex.org/A2053681587", "target": "https://openalex.org/A1962342457", "weight": 2},
                    {"source": "https://openalex.org/A1971464923", "target": "https://openalex.org/A1962342457", "weight": 1},
                    {"source": "https://openalex.org/A1971464923", "target": "https://openalex.org/A1983283131", "weight": 1}
                ]
            ),
            "https://openalex.org/T202": _build_graph(
                nodes=[
                    {"id": "https://openalex.org/A2112779243", "name": "Ove Hoegh-Guldberg"},
                    {"id": "https://openalex.org/A2112743840", "name": "Terry Hughes"},
                    {"id": "https://openalex.org/A2135812432", "name": "Enric Sala"},
                    {"id": "https://openalex.org/A2128745141", "name": "Maria Dornelas"}
                ],
                edges=[
                    {"source": "https://openalex.org/A2112779243", "target": "https://openalex.org/A2112743840", "weight": 4},
                    {"source": "https://openalex.org/A2112779243", "target": "https://openalex.org/A2135812432", "weight": 2},
                    {"source": "https://openalex.org/A2112779243", "target": "https://openalex.org/A2128745141", "weight": 2},
                    {"source": "https://openalex.org/A2112743840", "target": "https://openalex.org/A2128745141", "weight": 1},
                    {"source": "https://openalex.org/A2135812432", "target": "https://openalex.org/A2128745141", "weight": 1}
                ]
            )
        }

        self._author_networks: Dict[str, Dict] = {
            "https://openalex.org/A1969205032": _build_graph(
                nodes=[
                    {"id": "https://openalex.org/A1969205032", "name": "Fei-Fei Li", "is_focus": True},
                    {"id": "https://openalex.org/A2093607087", "name": "Andrew Ng"},
                    {"id": "https://openalex.org/A4210001001", "name": "Jia Deng"},
                    {"id": "https://openalex.org/A4210001002", "name": "Justin Johnson"},
                    {"id": "https://openalex.org/A4210001003", "name": "Juan Carlos Niebles"},
                    {"id": "https://openalex.org/A4210001004", "name": "Olga Russakovsky"}
                ],
                edges=[
                    {"source": "https://openalex.org/A1969205032", "target": "https://openalex.org/A2093607087", "weight": 3},
                    {"source": "https://openalex.org/A1969205032", "target": "https://openalex.org/A4210001001", "weight": 4},
                    {"source": "https://openalex.org/A1969205032", "target": "https://openalex.org/A4210001002", "weight": 2},
                    {"source": "https://openalex.org/A1969205032", "target": "https://openalex.org/A4210001003", "weight": 2},
                    {"source": "https://openalex.org/A1969205032", "target": "https://openalex.org/A4210001004", "weight": 3},
                    {"source": "https://openalex.org/A4210001004", "target": "https://openalex.org/A4210001003", "weight": 1},
                    {"source": "https://openalex.org/A4210001004", "target": "https://openalex.org/A4210001001", "weight": 2},
                    {"source": "https://openalex.org/A4210001002", "target": "https://openalex.org/A4210001001", "weight": 1}
                ]
            ),
            "https://openalex.org/A2112779243": _build_graph(
                nodes=[
                    {"id": "https://openalex.org/A2112779243", "name": "Ove Hoegh-Guldberg", "is_focus": True},
                    {"id": "https://openalex.org/A2112743840", "name": "Terry Hughes"},
                    {"id": "https://openalex.org/A2135812432", "name": "Enric Sala"},
                    {"id": "https://openalex.org/A2128745141", "name": "Maria Dornelas"},
                    {"id": "https://openalex.org/A4210001010", "name": "Jeremy Jackson"}
                ],
                edges=[
                    {"source": "https://openalex.org/A2112779243", "target": "https://openalex.org/A2112743840", "weight": 4},
                    {"source": "https://openalex.org/A2112779243", "target": "https://openalex.org/A2135812432", "weight": 2},
                    {"source": "https://openalex.org/A2112779243", "target": "https://openalex.org/A2128745141", "weight": 2},
                    {"source": "https://openalex.org/A2112743840", "target": "https://openalex.org/A4210001010", "weight": 2},
                    {"source": "https://openalex.org/A2135812432", "target": "https://openalex.org/A2128745141", "weight": 1}
                ]
            )
        }

    # Public helper methods --------------------------------------------

    def search_topics(self, query: str, limit: int) -> Optional[List[Dict]]:
        if not query:
            return []
        normalized = query.lower()
        matches = [
            topic for topic in self._topics
            if normalized in topic["display_name"].lower()
            or normalized in topic.get("description", "").lower()
        ]
        return _copy_slice(matches, limit)

    def search_authors(self, query: str, limit: int) -> Optional[List[Dict]]:
        if not query:
            return []
        normalized = query.lower()
        matches = [
            author for author in self._author_lookup.values()
            if normalized in author["display_name"].lower()
        ]
        return _copy_slice(matches, limit)

    def authors_by_topic(self, topic_id: str, limit: int) -> Optional[List[Dict]]:
        author_ids = self._topic_authors.get(topic_id)
        if author_ids is None:
            return []
        authors = [self._author_lookup.get(author_id) for author_id in author_ids]
        authors = [author for author in authors if author]
        return _copy_slice(authors, limit)

    def author_profile(self, author_id: str) -> Optional[Dict]:
        author = self._author_lookup.get(author_id)
        if author is None:
            return None
        return copy.deepcopy(author)

    def institutions_by_topic(self, topic_id: str, limit: int) -> Optional[List[Dict]]:
        institutions = self._topic_institutions.get(topic_id)
        if institutions is None:
            return []
        return _copy_slice(institutions, limit)

    def topic_network(self, topic_id: str) -> Optional[Dict]:
        graph = self._topic_networks.get(topic_id)
        if graph is None:
            return {
                "nodes": [],
                "links": [],
                "stats": {"node_count": 0, "link_count": 0, "top_authors": []}
            }
        return copy.deepcopy(graph)

    def author_network(self, author_id: str) -> Optional[Dict]:
        graph = self._author_networks.get(author_id)
        if graph is not None:
            return copy.deepcopy(graph)

        author = self._author_lookup.get(author_id)
        if author is None:
            return {
                "nodes": [],
                "links": [],
                "stats": {"node_count": 0, "link_count": 0, "top_authors": []}
            }

        node_name = author.get("display_name") or author_id
        return {
            "nodes": [
                {
                    "id": author_id,
                    "name": node_name,
                    "is_focus": True,
                    "degree": 0
                }
            ],
            "links": [],
            "stats": {
                "node_count": 1,
                "link_count": 0,
                "top_authors": [
                    {"id": author_id, "name": node_name, "degree": 0}
                ]
            }
        }


OFFLINE_DATA = OfflineOpenAlexData()
