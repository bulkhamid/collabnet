import React, { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const SearchModeToggle = ({ value, onChange }) => {
  const baseStyle = {
    flex: 1,
    padding: '10px 16px',
    border: '1px solid #5e2ca5',
    background: '#fff',
    color: '#5e2ca5',
    borderRadius: 6,
    cursor: 'pointer',
    fontWeight: 600
  };

  const activeStyle = {
    ...baseStyle,
    background: '#5e2ca5',
    color: '#fff'
  };

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
      <button
        type="button"
        onClick={() => onChange('topic')}
        style={value === 'topic' ? activeStyle : baseStyle}
      >
        Topic Explorer
      </button>
      <button
        type="button"
        onClick={() => onChange('author')}
        style={value === 'author' ? activeStyle : baseStyle}
      >
        Author Explorer
      </button>
    </div>
  );
};

const ResultList = ({ items, mode, onSelect }) => {
  if (!items.length) return null;

  return (
    <div
      style={{
        marginTop: 12,
        border: '1px solid #eee',
        borderRadius: 8,
        padding: 12,
        background: '#faf8ff'
      }}
    >
      <strong style={{ display: 'block', marginBottom: 8 }}>
        {mode === 'topic' ? 'Matching Topics' : 'Matching Authors'}
      </strong>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item)}
          style={{
            width: '100%',
            textAlign: 'left',
            padding: '10px 12px',
            marginBottom: 8,
            border: '1px solid #ddd',
            borderRadius: 6,
            cursor: 'pointer',
            background: '#fff'
          }}
        >
          {mode === 'topic' ? (
            <div>
              <div style={{ fontWeight: 600 }}>{item.display_name}</div>
              {!!item.description && (
                <div style={{ color: '#555', marginTop: 4 }}>
                  {item.description}
                </div>
              )}
              <div style={{ color: '#777', marginTop: 4 }}>
                Works indexed: {item.works_count?.toLocaleString?.() ?? item.works_count}
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontWeight: 600 }}>{item.display_name}</div>
              <div style={{ color: '#777', marginTop: 4 }}>
                Works: {item.works_count?.toLocaleString?.() ?? item.works_count} · Citations:{' '}
                {item.cited_by_count?.toLocaleString?.() ?? item.cited_by_count}
              </div>
              {item.last_known_institution?.display_name && (
                <div style={{ color: '#555', marginTop: 4 }}>
                  {item.last_known_institution.display_name}
                  {item.last_known_institution.country_code ? ` · ${item.last_known_institution.country_code}` : ''}
                </div>
              )}
            </div>
          )}
        </button>
      ))}
    </div>
  );
};

const InstitutionMap = ({ institutions }) => {
  const points = useMemo(() => {
    return (institutions || []).map((inst) => {
      const latitude = inst.latitude === null ? null : Number(inst.latitude);
      const longitude = inst.longitude === null ? null : Number(inst.longitude);
      return { ...inst, latitude, longitude };
    }).filter((inst) => Number.isFinite(inst.latitude) && Number.isFinite(inst.longitude));
  }, [institutions]);

  if (!points.length) {
    return (
      <div
        style={{
          padding: 12,
          border: '1px dashed #bbb',
          borderRadius: 8,
          color: '#555'
        }}
      >
        No geocoded institutions available for this topic.
      </div>
    );
  }

  const avgLat = points.reduce((acc, inst) => acc + inst.latitude, 0) / points.length;
  const avgLng = points.reduce((acc, inst) => acc + inst.longitude, 0) / points.length;

  const maxWorks = points.reduce((max, inst) => Math.max(max, inst.works_count || 0), 0);
  const minRadius = 4;
  const maxRadius = 14;

  const scaleRadius = (count) => {
    if (!maxWorks) return minRadius;
    const normalized = Math.log10(count + 1) / Math.log10(maxWorks + 1);
    return minRadius + normalized * (maxRadius - minRadius);
  };

  return (
    <MapContainer
      center={[avgLat, avgLng]}
      zoom={points.length === 1 ? 4 : 2}
      style={{ height: 420, width: '100%', borderRadius: 8 }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {points.map((inst) => (
        <CircleMarker
          key={inst.id}
          center={[inst.latitude, inst.longitude]}
          radius={scaleRadius(inst.works_count || 0)}
          pathOptions={{ color: '#5e2ca5', fillColor: '#5e2ca5', fillOpacity: 0.75, weight: 1 }}
        >
          <Tooltip direction="top">
            <div style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600 }}>{inst.display_name}</div>
              <div>Works: {inst.works_count?.toLocaleString?.() ?? inst.works_count}</div>
              {inst.country_code && <div>Country: {inst.country_code}</div>}
              {inst.city && <div>{inst.city}{inst.region ? `, ${inst.region}` : ''}</div>}
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
};

const GraphPanel = ({ graphData, stats, focusName }) => {
  const fgRef = useRef(null);

  useEffect(() => {
    if (!fgRef.current || !(graphData?.nodes?.length)) return;
    const timeout = setTimeout(() => {
      try {
        fgRef.current.zoomToFit(400, 80);
      } catch (err) {
        console.warn('Force graph zoom failed', err);
      }
    }, 400);
    return () => clearTimeout(timeout);
  }, [graphData]);

  if (!graphData?.nodes?.length) {
    return (
      <div
        style={{
          padding: 12,
          border: '1px dashed #bbb',
          borderRadius: 8,
          color: '#555'
        }}
      >
        No network data available for this selection.
      </div>
    );
  }

  const canvasStyle = { width: '100%', height: 520, border: '1px solid #ddd', borderRadius: 8 };
  const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 960;
  const width = Math.min(viewportWidth - 60, 960);
  const height = 520;

  const getNodeColor = (node) => (node.is_focus ? '#ff7f0e' : '#69b3a2');

  return (
    <div>
      <div style={{ marginBottom: 12, color: '#333' }}>
        {stats && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ padding: '6px 12px', borderRadius: 6, background: '#f4f0ff' }}>
              Nodes: <strong>{stats.node_count}</strong>
            </div>
            <div style={{ padding: '6px 12px', borderRadius: 6, background: '#f4f0ff' }}>
              Links: <strong>{stats.link_count}</strong>
            </div>
            {focusName && (
              <div style={{ padding: '6px 12px', borderRadius: 6, background: '#fde9d2' }}>
                Highlighting: <strong>{focusName}</strong>
              </div>
            )}
          </div>
        )}
      </div>
      <div style={canvasStyle}>
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          width={width}
          height={height}
          nodeId="id"
          linkSource="source"
          linkTarget="target"
          nodeLabel={(node) => node.name || node.id}
          linkDirectionalParticles={1}
          linkDirectionalParticleSpeed={(link) =>
            0.0006 + Math.min(link.weight || 0, 5) * 0.0004
          }
          linkWidth={(link) => 0.5 + Math.min(link.weight || 0, 5) * 0.4}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const label = node.name || node.id;
            const fontSize = 12 / globalScale;
            const radius = 4 + Math.min(node.degree || 0, 12);

            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
            ctx.fillStyle = getNodeColor(node);
            ctx.fill();

            ctx.lineWidth = node.is_focus ? 2 : 1;
            ctx.strokeStyle = node.is_focus ? '#c05a00' : '#003f5c';
            ctx.stroke();

            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.fillStyle = '#222';
            ctx.fillText(label, node.x + radius + 2, node.y + radius + 2);
          }}
        />
      </div>
    </div>
  );
};

function App() {
  const [searchMode, setSearchMode] = useState('topic');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');

  const [selectedTopic, setSelectedTopic] = useState(null);
  const [selectedAuthor, setSelectedAuthor] = useState(null);
  const [topicAuthors, setTopicAuthors] = useState([]);
  const [topicInstitutions, setTopicInstitutions] = useState([]);
  const [graphData, setGraphData] = useState(null);
  const [graphStats, setGraphStats] = useState(null);

  const clearDetailState = () => {
    setSelectedTopic(null);
    setSelectedAuthor(null);
    setTopicAuthors([]);
    setTopicInstitutions([]);
    setGraphData(null);
    setGraphStats(null);
  };

  const handleModeChange = (mode) => {
    if (mode === searchMode) return;
    setSearchMode(mode);
    setResults([]);
    setQuery('');
    setError('');
    clearDetailState();
  };

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!query.trim()) return;

    clearDetailState();
    setLoading(true);
    setError('');

    const endpoint =
      searchMode === 'topic'
        ? `/api/topics?query=${encodeURIComponent(query)}`
        : `/api/authors?query=${encodeURIComponent(query)}`;

    try {
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error(`Request failed with status ${response.status}`);

      const payload = await response.json();
      const list = searchMode === 'topic' ? payload.topics || [] : payload.authors || [];
      setResults(list);
      if (!list.length) {
        setError('No results found. Try a broader search term.');
      }
    } catch (err) {
      console.error(err);
      setError('Unable to reach the OpenAlex API. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const loadTopicDetails = async (topic) => {
    setDetailLoading(true);
    setError('');
    try {
      const encoded = encodeURIComponent(topic.id);
      const [authorsRes, institutionsRes, networkRes] = await Promise.all([
        fetch(`/api/authors/${encoded}?limit=25`),
        fetch(`/api/institutions/${encoded}?limit=50`),
        fetch(`/api/coauthor-network/${encoded}?limit_works=150`)
      ]);

      if (!authorsRes.ok || !institutionsRes.ok || !networkRes.ok) {
        throw new Error('Failed to load topic details');
      }

      const [authorsPayload, institutionsPayload, networkPayload] = await Promise.all([
        authorsRes.json(),
        institutionsRes.json(),
        networkRes.json()
      ]);

      setTopicAuthors(authorsPayload.authors || []);
      setTopicInstitutions(institutionsPayload.institutions || []);
      setGraphData({
        nodes: networkPayload.nodes || [],
        links: networkPayload.links || []
      });
      setGraphStats(networkPayload.stats || null);
    } catch (err) {
      console.error(err);
      setError('Failed to load topic details.');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSelectTopic = (topic) => {
    setSelectedTopic(topic);
    setSelectedAuthor(null);
    loadTopicDetails(topic);
  };

  const loadAuthorNetwork = async (authorId, { manageLoading = true } = {}) => {
    if (manageLoading) {
      setDetailLoading(true);
      setError('');
    }

    try {
      const encoded = encodeURIComponent(authorId);
      const response = await fetch(`/api/coauthor-network/author/${encoded}?limit_works=150`);
      if (!response.ok) throw new Error('Failed to load author network');

      const payload = await response.json();
      setGraphData({
        nodes: payload.nodes || [],
        links: payload.links || []
      });
      setGraphStats(payload.stats || null);
    } catch (err) {
      console.error(err);
      setError('Failed to load author collaboration network.');
    } finally {
      if (manageLoading) {
        setDetailLoading(false);
      }
    }
  };

  const handleSelectAuthor = async (author) => {
    setSelectedAuthor(null);
    setSelectedTopic(null);
    setTopicAuthors([]);
    setTopicInstitutions([]);
    setGraphData(null);
    setGraphStats(null);
    setError('');
    setDetailLoading(true);

    try {
      let profile = author;
      const needsProfile =
        profile.works_count === undefined || profile.cited_by_count === undefined;
      if (needsProfile) {
        const encoded = encodeURIComponent(author.id);
        const profileRes = await fetch(`/api/author/${encoded}`);
        if (!profileRes.ok) {
          throw new Error('Failed to fetch author profile');
        }
        const profilePayload = await profileRes.json();
        profile = profilePayload.author || profile;
      }

      setSelectedAuthor({
        id: profile.id,
        display_name: profile.display_name || profile.name || 'Unknown author',
        works_count: profile.works_count,
        cited_by_count: profile.cited_by_count,
        last_known_institution: profile.last_known_institution
      });

      await loadAuthorNetwork(profile.id, { manageLoading: false });
    } catch (err) {
      console.error(err);
      setError('Failed to load author details.');
      setSelectedAuthor({
        id: author.id,
        display_name: author.display_name || author.name || 'Unknown author'
      });
    } finally {
      setDetailLoading(false);
    }
  };

  const countrySummary = useMemo(() => {
    const counts = {};
    (topicInstitutions || []).forEach((inst) => {
      if (!inst.country_code) return;
      counts[inst.country_code] = (counts[inst.country_code] || 0) + (inst.works_count || 0);
    });
    return Object.entries(counts)
      .map(([code, works]) => ({ code, works }))
      .sort((a, b) => b.works - a.works)
      .slice(0, 5);
  }, [topicInstitutions]);

  const topCollaborators = useMemo(() => {
    if (!graphData?.nodes?.length) return [];
    if (!selectedAuthor) return [];
    const collaborators = graphData.nodes
      .filter((node) => node.id !== selectedAuthor.id)
      .sort((a, b) => (b.degree || 0) - (a.degree || 0))
      .slice(0, 8);
    return collaborators;
  }, [graphData, selectedAuthor]);

  const placeholder =
    searchMode === 'topic'
      ? 'Enter a research topic (e.g., machine learning, coral reef ecology)'
      : 'Enter an author name (e.g., Fei-Fei Li)';

  return (
    <div style={{ padding: 20, maxWidth: 1200, margin: '0 auto', color: '#212121' }}>
      <h1 style={{ margin: 0, padding: '8px 0 16px', borderBottom: '3px solid #5e2ca5' }}>
        OpenAlex Collaborator Recommender
      </h1>

      <p style={{ color: '#555', marginTop: 8 }}>
        Discover active scholars, labs, and collaboration patterns via the OpenAlex knowledge graph.
        Search by topic to see leading authors and institutions, or switch to the author explorer to
        map each scholar’s co-author network.
      </p>

      <SearchModeToggle value={searchMode} onChange={handleModeChange} />

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={placeholder}
          style={{
            flex: 1,
            padding: 12,
            border: '1px solid #ccc',
            borderRadius: 6,
            fontSize: 16
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '12px 20px',
            borderRadius: 6,
            border: 'none',
            cursor: 'pointer',
            background: loading ? '#bbb' : '#5e2ca5',
            color: '#fff',
            fontWeight: 600
          }}
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && (
        <div style={{ color: 'crimson', marginBottom: 12 }}>
          {error}
        </div>
      )}

      <ResultList
        items={results}
        mode={searchMode}
        onSelect={searchMode === 'topic' ? handleSelectTopic : handleSelectAuthor}
      />

      {detailLoading && (
        <div style={{ marginTop: 16, color: '#555' }}>
          Loading network intelligence…
        </div>
      )}

      {selectedTopic && (
        <section style={{ marginTop: 24 }}>
          <h2 style={{ marginBottom: 8 }}>
            {selectedTopic.display_name}
          </h2>
          <p style={{ color: '#555', marginBottom: 16 }}>
            Works indexed: {selectedTopic.works_count?.toLocaleString?.() ?? selectedTopic.works_count}
          </p>

          {topicAuthors.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h3 style={{ marginBottom: 8 }}>Active Authors</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {topicAuthors.slice(0, 8).map((author) => (
                  <div
                    key={author.id}
                    style={{
                      flex: '1 1 220px',
                      border: '1px solid #ddd',
                      borderRadius: 8,
                      padding: 12,
                      background: '#fff'
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{author.display_name}</div>
                    <div style={{ color: '#666', marginTop: 4 }}>
                      Works: {author.works_count?.toLocaleString?.() ?? author.works_count}
                    </div>
                    <div style={{ color: '#666', marginTop: 4 }}>
                      Citations: {author.cited_by_count?.toLocaleString?.() ?? author.cited_by_count}
                    </div>
                    {author.last_known_institution?.display_name && (
                      <div style={{ color: '#555', marginTop: 6 }}>
                        {author.last_known_institution.display_name}
                        {author.last_known_institution.country_code
                          ? ` · ${author.last_known_institution.country_code}`
                          : ''}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => handleSelectAuthor(author)}
                      style={{
                        marginTop: 10,
                        padding: '6px 10px',
                        borderRadius: 4,
                        border: '1px solid #5e2ca5',
                        background: '#fff',
                        color: '#5e2ca5',
                        cursor: 'pointer'
                      }}
                    >
                      View co-author network
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 12 }}>Topic Collaboration Network</h3>
            <GraphPanel
              graphData={graphData}
              stats={graphStats}
              focusName={null}
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 12 }}>Global Institution Footprint</h3>
            <InstitutionMap institutions={topicInstitutions} />
          </div>

          {!!countrySummary.length && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 8 }}>Top Countries by Output</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {countrySummary.map((entry) => (
                  <div
                    key={entry.code}
                    style={{
                      flex: '1 1 160px',
                      border: '1px solid #ddd',
                      borderRadius: 6,
                      padding: 10,
                      background: '#f8f5ff'
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{entry.code}</div>
                    <div style={{ color: '#555', marginTop: 6 }}>
                      Works: {entry.works.toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {selectedAuthor && (
        <section style={{ marginTop: 24 }}>
          <h2 style={{ marginBottom: 8 }}>
            {selectedAuthor.display_name}
          </h2>
          <div style={{ color: '#555', marginBottom: 16 }}>
            Works: {selectedAuthor.works_count?.toLocaleString?.() ?? selectedAuthor.works_count} ·
            Citations: {selectedAuthor.cited_by_count?.toLocaleString?.() ?? selectedAuthor.cited_by_count}
          </div>
          {selectedAuthor.last_known_institution?.display_name && (
            <div style={{ color: '#666', marginBottom: 16 }}>
              Affiliation: {selectedAuthor.last_known_institution.display_name}
              {selectedAuthor.last_known_institution.country_code
                ? ` (${selectedAuthor.last_known_institution.country_code})`
                : ''}
            </div>
          )}

          <div style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 12 }}>Author Collaboration Network</h3>
            <GraphPanel
              graphData={graphData}
              stats={graphStats}
              focusName={selectedAuthor.display_name}
            />
          </div>

          {!!topCollaborators.length && (
            <div style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 8 }}>Top Collaborators</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {topCollaborators.map((collab) => (
                  <div
                    key={collab.id}
                    style={{
                      flex: '1 1 200px',
                      border: '1px solid #ddd',
                      borderRadius: 6,
                      padding: 12,
                      background: '#fff'
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{collab.name}</div>
                    <div style={{ color: '#666', marginTop: 4 }}>
                      Collaboration links: {collab.degree}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSelectAuthor({ id: collab.id, display_name: collab.name })}
                      style={{
                        marginTop: 10,
                        padding: '6px 10px',
                        borderRadius: 4,
                        border: '1px solid #5e2ca5',
                        background: '#fff',
                        color: '#5e2ca5',
                        cursor: 'pointer'
                      }}
                    >
                      Center on collaborator
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default App;
