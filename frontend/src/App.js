import React, { useState, useRef, useEffect } from 'react';
import { ForceGraph2D } from 'react-force-graph';

function App() {
  const [query, setQuery] = useState('');
  const [topics, setTopics] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fgRef = useRef();

  // Show something no matter what
  const TestBanner = () => (
    <div style={{
      background: '#5e2ca5',
      color: 'white',
      padding: '12px 16px',
      borderRadius: 8,
      marginBottom: 12
    }}>
      <strong>App mounted.</strong> If you can read this, React is rendering.
    </div>
  );

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setError('');
    setSelectedTopic(null);
    setGraphData(null);
    setLoading(true);

    try {
      const response = await fetch(`/api/topics?query=${encodeURIComponent(query)}`);
      if (!response.ok) throw new Error('Failed to fetch topics');

      const data = await response.json();
      setTopics(data.topics || []);
      if (!data.topics || data.topics.length === 0) setError('No topics found');
    } catch (err) {
      console.error(err);
      setError('Error fetching topics');
    } finally {
      setLoading(false);
    }
  };

  const fetchGraphData = async (topicId, limitWorks = 100) => {
    setError('');
    setGraphData(null);
    setLoading(true);

    try {
      const response = await fetch(
        `/api/coauthor-network/${encodeURIComponent(topicId)}?limit_works=${limitWorks}`
      );
      if (!response.ok) throw new Error('Failed to fetch network');

      const data = await response.json();
      const nodes = data.nodes || [];
      const links = data.links || [];
      setGraphData({ nodes, links });
      if (nodes.length === 0) setError('No network data found for this topic');
    } catch (err) {
      console.error(err);
      setError('Error fetching network');
    } finally {
      setLoading(false);
    }
  };

  const handleTopicClick = (topic) => {
    setSelectedTopic(topic);
    setTopics([]);
    fetchGraphData(topic.id);
  };

  useEffect(() => {
    if (fgRef.current && graphData?.nodes?.length) {
      const t = setTimeout(() => {
        try { fgRef.current.zoomToFit(400, 40); } catch (_) {}
      }, 400);
      return () => clearTimeout(t);
    }
  }, [graphData]);

  return (
    <div style={{ padding: 20, maxWidth: 1100, margin: '0 auto', color: '#222' }}>
      <h1 style={{ margin: 0, padding: '8px 0 16px', borderBottom: '3px solid #5e2ca5' }}>
        Collaborator Finder
      </h1>

      <TestBanner />

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          placeholder="Enter a research topic (e.g., machine learning)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1, padding: 10, border: '1px solid #ccc', borderRadius: 6 }}
        />
        <button type="submit" disabled={loading} style={{ padding: '10px 16px' }}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && <div style={{ color: 'crimson', marginBottom: 12 }}>{error}</div>}

      {topics.length > 0 && (
        <div style={{ marginBottom: 16, border: '1px solid #eee', borderRadius: 6, padding: 8 }}>
          <strong>Topics</strong>
          {topics.map((topic) => (
            <div
              key={topic.id}
              onClick={() => handleTopicClick(topic)}
              style={{ cursor: 'pointer', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}
            >
              <span>{topic.display_name}</span>
              {topic.description && <span> — {topic.description}</span>}
            </div>
          ))}
        </div>
      )}

      {selectedTopic && (
        <div>
          <h2 style={{ marginTop: 8, marginBottom: 12 }}>
            Co-authorship network for: {selectedTopic.display_name}
          </h2>

          {graphData?.nodes?.length > 0 ? (
            <div style={{ width: '100%', height: 600, border: '1px solid #ddd', borderRadius: 8 }}>
              <ForceGraph2D
                ref={fgRef}
                graphData={graphData}
                width={900}
                height={600}
                nodeId="id"
                linkSource="source"
                linkTarget="target"
                nodeLabel={(n) => n.name || n.id}
                linkDirectionalParticles={1}
                linkDirectionalParticleSpeed={d =>
                  0.001 + (d.weight ? Math.min(d.weight, 5) : 0) * 0.0005
                }
                nodeCanvasObject={(node, ctx, globalScale) => {
                  const label = node.name || node.id;
                  const fontSize = 12 / globalScale;
                  const radius = 5 + Math.min(node.degree || 0, 10);

                  ctx.beginPath();
                  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
                  ctx.fillStyle = '#69b3a2';
                  ctx.fill();

                  ctx.lineWidth = 1;
                  ctx.strokeStyle = '#003f5c';
                  ctx.stroke();

                  ctx.font = `${fontSize}px Sans-Serif`;
                  ctx.fillStyle = '#222';
                  ctx.fillText(label, node.x + radius + 2, node.y + radius + 2);
                }}
              />
            </div>
          ) : (
            <div style={{
              padding: 12,
              border: '1px dashed #aaa',
              borderRadius: 8,
              color: '#555'
            }}>
              Select a topic above to load its network…
            </div>
          )}
        </div>
      )}

      {!selectedTopic && (
        <div style={{
          marginTop: 16,
          padding: 12,
          border: '1px dashed #aaa',
          borderRadius: 8,
          color: '#555'
        }}>
          Tip: try a broad query like <em>“machine learning”</em> or <em>“climate change”</em>.
        </div>
      )}
    </div>
  );
}

export default App;
