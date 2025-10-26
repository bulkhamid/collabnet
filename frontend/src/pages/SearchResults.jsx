import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';

/**
 * Page showing search results for topics or authors. When searching by topic,
 * it automatically retrieves the list of authors associated with the top
 * matching topic and displays them. Users can refine the search, switch
 * between modes, or view details for a specific researcher via an overlay.
 */
const SearchResults = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [mode, setMode] = useState(searchParams.get('mode') || 'topic');
  const [results, setResults] = useState([]);
  const [selectedAuthor, setSelectedAuthor] = useState(null);
  const [authorProfile, setAuthorProfile] = useState(null);
  const [authorGraph, setAuthorGraph] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [topicName, setTopicName] = useState('');

  // Perform search on initial load and when query/mode changes
  useEffect(() => {
    async function performSearch() {
      if (!query) return;
      setLoading(true);
      setError('');
      try {
        if (mode === 'topic') {
          // First search for topics
          const topicsRes = await fetch(`/api/topics?query=${encodeURIComponent(query)}`);
          if (!topicsRes.ok) throw new Error('Failed to fetch topics');
          const topicsPayload = await topicsRes.json();
          const topics = topicsPayload.topics || [];
          if (topics.length) {
            // Use the first matching topic
            const topic = topics[0];
            setTopicName(topic.display_name || '');
            const authorsRes = await fetch(`/api/authors/${encodeURIComponent(topic.id)}?limit=25`);
            if (!authorsRes.ok) throw new Error('Failed to fetch authors for topic');
            const authorsPayload = await authorsRes.json();
            setResults(authorsPayload.authors || []);
          } else {
            setResults([]);
            setTopicName('');
            setError('No matching topics found.');
          }
        } else {
          // Mode = author: search authors directly
          const authorsRes = await fetch(`/api/authors?query=${encodeURIComponent(query)}`);
          if (!authorsRes.ok) throw new Error('Failed to fetch authors');
          const authorsPayload = await authorsRes.json();
          setResults(authorsPayload.authors || []);
          setTopicName('');
        }
      } catch (err) {
        console.error(err);
        setError(err.message || 'Search failed');
      } finally {
        setLoading(false);
      }
    }
    performSearch();
  }, [query, mode]);

  // Handler for submitting a new search
  const handleSearch = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    const params = new URLSearchParams();
    params.set('q', query);
    params.set('mode', mode);
    navigate(`/search?${params.toString()}`);
    // after navigation, useEffect will trigger fetch
  };

  // Select author: fetch details and network then open modal
  const handleSelectAuthor = async (author) => {
    try {
      setLoading(true);
      setSelectedAuthor(author);
      // Fetch profile if missing details
      const needsProfile = !author.works_count || !author.cited_by_count;
      let profile = author;
      if (needsProfile) {
        const resProfile = await fetch(`/api/author/${encodeURIComponent(author.id)}`);
        if (resProfile.ok) {
          const payload = await resProfile.json();
          profile = payload.author || author;
        }
      }
      setAuthorProfile(profile);
      // Fetch network
      const resNet = await fetch(`/api/coauthor-network/author/${encodeURIComponent(author.id)}?limit_works=150`);
      if (resNet.ok) {
        const payload = await resNet.json();
        setAuthorGraph({ nodes: payload.nodes || [], links: payload.links || [] });
      }
    } catch (err) {
      console.error(err);
      setError('Failed to load author details');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800">
      <header className="flex items-center justify-between p-4 bg-white shadow">
        <h1 className="text-xl font-bold text-primary">CollabNet</h1>
        <nav className="flex items-center gap-4">
          <button className="text-sm text-primary hover:underline" onClick={() => navigate('/dashboard')}>Dashboard</button>
        </nav>
      </header>
      <main className="p-6 max-w-6xl mx-auto">
        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode('topic')}
              className={`px-4 py-2 border rounded-md text-sm font-medium ${mode === 'topic' ? 'bg-primary text-white' : 'bg-white border-primary text-primary'}`}
            >
              By Topic
            </button>
            <button
              type="button"
              onClick={() => setMode('author')}
              className={`px-4 py-2 border rounded-md text-sm font-medium ${mode === 'author' ? 'bg-primary text-white' : 'bg-white border-primary text-primary'}`}
            >
              By Researcher
            </button>
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={mode === 'topic' ? 'Enter a research topic' : 'Enter a researcher name'}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-md"
          />
          <button type="submit" className="px-6 py-2 bg-primary text-white font-semibold rounded-md">
            Search
          </button>
        </form>
        {loading && <div className="text-gray-600 mb-4">Searching…</div>}
        {error && <div className="text-red-500 mb-4">{error}</div>}
        {/* Heading for results */}
        {mode === 'topic' && topicName && (
          <h2 className="text-xl font-semibold mb-4">{`Results for “${query}” in topic “${topicName}”`}</h2>
        )}
        {mode === 'author' && query && (
          <h2 className="text-xl font-semibold mb-4">{`Authors matching “${query}”`}</h2>
        )}
        {/* Results grid */}
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {results.map((item) => (
            <div key={item.id} className="bg-white p-4 border rounded-lg shadow flex flex-col">
              <h3 className="font-semibold text-primary">{item.display_name}</h3>
              {mode === 'topic' && (
                <>
                  <p className="text-sm text-gray-600 mt-1">Works: {item.works_count?.toLocaleString?.() ?? item.works_count}</p>
                  <p className="text-sm text-gray-600">Citations: {item.cited_by_count?.toLocaleString?.() ?? item.cited_by_count}</p>
                  {item.last_known_institution?.display_name && (
                    <p className="text-sm text-gray-500 mt-1">
                      {item.last_known_institution.display_name}{item.last_known_institution.country_code ? ` • ${item.last_known_institution.country_code}` : ''}
                    </p>
                  )}
                </>
              )}
              {mode === 'author' && (
                <>
                  <p className="text-sm text-gray-600 mt-1">Works: {item.works_count?.toLocaleString?.() ?? item.works_count}</p>
                  <p className="text-sm text-gray-600">Citations: {item.cited_by_count?.toLocaleString?.() ?? item.cited_by_count}</p>
                  {item.last_known_institution?.display_name && (
                    <p className="text-sm text-gray-500 mt-1">
                      {item.last_known_institution.display_name}{item.last_known_institution.country_code ? ` • ${item.last_known_institution.country_code}` : ''}
                    </p>
                  )}
                </>
              )}
              <div className="mt-auto flex gap-2 pt-4">
                <button
                  onClick={() => handleSelectAuthor(item)}
                  className="px-3 py-2 text-sm border border-primary text-primary rounded-md hover:bg-primary hover:text-white transition"
                >
                  View Profile
                </button>
                <button
                  onClick={() => handleSelectAuthor(item)}
                  className="px-3 py-2 text-sm border border-primary text-primary rounded-md hover:bg-primary hover:text-white transition"
                >
                  Preview Network
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Author modal overlay */}
      {selectedAuthor && authorProfile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white max-w-3xl w-full m-4 rounded-lg overflow-hidden" style={{ maxHeight: '90vh' }}>
            {/* Modal header */}
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-xl font-semibold">{authorProfile.display_name}</h3>
              <button
                onClick={() => {
                  setSelectedAuthor(null);
                  setAuthorProfile(null);
                  setAuthorGraph(null);
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            {/* Modal body */}
            <div className="p-4 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 80px)' }}>
              <div className="mb-4">
                <p className="text-gray-600 mb-1">Works: {authorProfile.works_count?.toLocaleString?.() ?? authorProfile.works_count}</p>
                <p className="text-gray-600 mb-1">Citations: {authorProfile.cited_by_count?.toLocaleString?.() ?? authorProfile.cited_by_count}</p>
                {authorProfile.last_known_institution?.display_name && (
                  <p className="text-gray-600 mb-1">Affiliation: {authorProfile.last_known_institution.display_name}{authorProfile.last_known_institution.country_code ? ` (${authorProfile.last_known_institution.country_code})` : ''}</p>
                )}
              </div>
              {/* Graph panel */}
              {authorGraph && authorGraph.nodes?.length ? (
                <div className="border rounded-md p-2 mb-4" style={{ height: 400 }}>
                  <ForceGraph2D
                    graphData={authorGraph}
                    nodeId="id"
                    linkSource="source"
                    linkTarget="target"
                    width={600}
                    height={400}
                    nodeLabel={(node) => node.name || node.id}
                    linkDirectionalParticles={1}
                    linkDirectionalParticleSpeed={(link) => 0.0006 + Math.min(link.weight || 0, 5) * 0.0004}
                    linkWidth={(link) => 0.5 + Math.min(link.weight || 0, 5) * 0.4}
                    nodeCanvasObject={(node, ctx, globalScale) => {
                      const label = node.name || node.id;
                      const fontSize = 12 / globalScale;
                      const radius = 4 + Math.min(node.degree || 0, 12);
                      ctx.beginPath();
                      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
                      ctx.fillStyle = node.is_focus ? '#ff7f0e' : '#69b3a2';
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
              ) : (
                <div className="text-gray-600 mb-4">No network data available for this author.</div>
              )}
              {/* Connect button */}
              <button
                onClick={() => navigate(`/match?target=${encodeURIComponent(authorProfile.id)}&name=${encodeURIComponent(authorProfile.display_name)}`)}
                className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-dark transition"
              >
                Connect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchResults;