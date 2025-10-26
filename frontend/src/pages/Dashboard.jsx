import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
  ArcElement,
  PointElement,
  LineElement,
} from 'chart.js';

// Register chart components
ChartJS.register(
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
  ArcElement,
  PointElement,
  LineElement
);

/**
 * Dashboard page. Shows the search controls and high‑level analytics charts.
 * When the search input is empty and the search button is pressed, an overlay
 * appears with trending topics and scientists. Real data is fetched from
 * backend endpoints and defaults are provided if the backend is unavailable.
 */
const Dashboard = () => {
  const navigate = useNavigate();
  const [searchMode, setSearchMode] = useState('topic');
  const [query, setQuery] = useState('');
  const [showOverlay, setShowOverlay] = useState(false);
  const [trendingTopics, setTrendingTopics] = useState([]);
  const [trendingScientists, setTrendingScientists] = useState([]);
  const [topInstitutions, setTopInstitutions] = useState([]);
  const [networkSizes, setNetworkSizes] = useState([]);
  const [error, setError] = useState('');

  // Fetch trending topics and scientists on mount
  useEffect(() => {
    async function fetchTrending() {
      try {
        const [topicsRes, scientistsRes] = await Promise.all([
          fetch('/api/trending/topics'),
          fetch('/api/trending/scientists')
        ]);
        if (topicsRes.ok) {
          const data = await topicsRes.json();
          setTrendingTopics(data.topics || []);
        }
        if (scientistsRes.ok) {
          const data = await scientistsRes.json();
          setTrendingScientists(data.scientists || []);
        }
      } catch (err) {
        console.error(err);
        setError('Failed to load trending information.');
      }
    }
    fetchTrending();
  }, []);

  // Fetch top institutions based on trending topics
  useEffect(() => {
    if (!trendingTopics.length) return;
    async function fetchInstitutions() {
      try {
        const allInst = {};
        const requests = trendingTopics.map((topic) =>
          fetch(`/api/institutions/${encodeURIComponent(topic.id)}?limit=5`)
        );
        const responses = await Promise.all(requests);
        for (let i = 0; i < responses.length; i++) {
          const res = responses[i];
          if (!res.ok) continue;
          const payload = await res.json();
          (payload.institutions || []).forEach((inst) => {
            const name = inst.display_name;
            if (!name) return;
            if (!allInst[name]) {
              allInst[name] = inst.works_count || 0;
            } else {
              allInst[name] += inst.works_count || 0;
            }
          });
        }
        // Convert to array and take top 5
        const sorted = Object.entries(allInst)
          .map(([name, count]) => ({ name, count }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 5);
        setTopInstitutions(sorted);
      } catch (err) {
        console.error(err);
      }
    }
    fetchInstitutions();
  }, [trendingTopics]);

  // Fetch network sizes for trending scientists
  useEffect(() => {
    if (!trendingScientists.length) return;
    async function fetchNetworks() {
      try {
        const sizes = [];
        const requests = trendingScientists.map((author) =>
          fetch(`/api/coauthor-network/author/${encodeURIComponent(author.id)}?limit_works=100`)
        );
        const responses = await Promise.all(requests);
        for (let i = 0; i < responses.length; i++) {
          const res = responses[i];
          if (!res.ok) continue;
          const payload = await res.json();
          sizes.push(payload.stats?.node_count || 0);
        }
        setNetworkSizes(sizes);
      } catch (err) {
        console.error(err);
      }
    }
    fetchNetworks();
  }, [trendingScientists]);

  // Chart data definitions
  const topicChartData = useMemo(() => {
    const labels = trendingTopics.map((t) => t.display_name);
    const data = trendingTopics.map((t) => t.works_count || 0);
    return {
      labels,
      datasets: [
        {
          label: 'Works Count',
          data,
          backgroundColor: ['#5e2ca5', '#69b3a2', '#ff7f0e', '#c05a00', '#008080'],
        },
      ],
    };
  }, [trendingTopics]);

  const institutionChartData = useMemo(() => {
    const labels = topInstitutions.map((inst) => inst.name);
    const data = topInstitutions.map((inst) => inst.count);
    return {
      labels,
      datasets: [
        {
          label: 'Total Works',
          data,
          backgroundColor: ['#5e2ca5', '#69b3a2', '#ff7f0e', '#c05a00', '#008080'],
        },
      ],
    };
  }, [topInstitutions]);

  const networkChartData = useMemo(() => {
    const labels = trendingScientists.map((sc) => sc.display_name);
    return {
      labels,
      datasets: [
        {
          label: 'Network Size',
          data: networkSizes,
          fill: false,
          borderColor: '#5e2ca5',
          backgroundColor: '#5e2ca5',
          tension: 0.3,
        },
      ],
    };
  }, [trendingScientists, networkSizes]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!query.trim()) {
      // Show overlay if no query
      setShowOverlay(true);
      return;
    }
    // Navigate to search page with query and mode
    const params = new URLSearchParams();
    params.set('q', query);
    params.set('mode', searchMode);
    navigate(`/search?${params.toString()}`);
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800">
      {/* Header */}
      <header className="flex items-center justify-between p-4 bg-white shadow">
        <h1 className="text-xl font-bold text-primary">CollabNet</h1>
        <nav className="flex items-center gap-4">
          <button className="text-sm text-primary hover:underline" onClick={() => navigate('/dashboard')}>Dashboard</button>
        </nav>
      </header>

      {/* Main content */}
      <main className="p-6 max-w-7xl mx-auto">
        {/* Intro text */}
        <h2 className="text-2xl font-semibold mb-2">Discover global research trends</h2>
        <p className="text-gray-600 mb-6">Explore the most active topics, institutions and scientists powering the next generation of discoveries.</p>

        {/* Search controls */}
        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setSearchMode('topic')}
              className={`px-4 py-2 border rounded-md text-sm font-medium ${searchMode === 'topic' ? 'bg-primary text-white' : 'bg-white border-primary text-primary'}`}
            >
              By Topic
            </button>
            <button
              type="button"
              onClick={() => setSearchMode('author')}
              className={`px-4 py-2 border rounded-md text-sm font-medium ${searchMode === 'author' ? 'bg-primary text-white' : 'bg-white border-primary text-primary'}`}
            >
              By Researcher
            </button>
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchMode === 'topic' ? 'Enter a research topic' : 'Enter a researcher name'}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-md"
          />
          <button
            type="submit"
            className="px-6 py-2 bg-primary text-white font-semibold rounded-md"
          >
            Search
          </button>
        </form>

        {error && <div className="text-red-500 mb-4">{error}</div>}

        {/* Chart cards */}
        <div className="grid gap-6 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 mb-8">
          <div className="bg-white p-4 rounded-lg shadow border">
            <h3 className="font-semibold mb-3">Global Research Trends</h3>
            <Bar data={topicChartData} options={{ plugins: { legend: { display: false } } }} />
          </div>
          <div className="bg-white p-4 rounded-lg shadow border">
            <h3 className="font-semibold mb-3">Top Contributing Institutions</h3>
            <Doughnut data={institutionChartData} options={{ plugins: { legend: { position: 'bottom' } } }} />
          </div>
          <div className="bg-white p-4 rounded-lg shadow border md:col-span-2 lg:col-span-1">
            <h3 className="font-semibold mb-3">Collaboration Network Overview</h3>
            <Line data={networkChartData} options={{ plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }} />
          </div>
        </div>

        {/* Featured researchers */}
        <section className="mb-12">
          <h3 className="text-xl font-semibold mb-4">Trending Scientists</h3>
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {trendingScientists.map((sc) => (
              <div key={sc.id} className="bg-white p-4 border rounded-lg shadow flex flex-col">
                <h4 className="font-semibold text-primary">{sc.display_name}</h4>
                <p className="text-sm text-gray-600 mt-1">
                  Works: {sc.works_count?.toLocaleString?.() ?? sc.works_count}
                </p>
                <p className="text-sm text-gray-600">
                  Citations: {sc.cited_by_count?.toLocaleString?.() ?? sc.cited_by_count}
                </p>
                {sc.last_known_institution?.display_name && (
                  <p className="text-sm text-gray-500 mt-1">
                    {sc.last_known_institution.display_name}{
                      sc.last_known_institution.country_code
                        ? ` • ${sc.last_known_institution.country_code}`
                        : ''
                    }
                  </p>
                )}
                <button
                  onClick={() => navigate(`/search?q=${encodeURIComponent(sc.display_name)}&mode=author`)}
                  className="mt-auto mt-4 px-3 py-2 text-sm border border-primary text-primary rounded-md hover:bg-primary hover:text-white transition"
                >
                  View Profile
                </button>
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* Overlay for trending suggestions */}
      {showOverlay && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowOverlay(false)}>
          <div className="bg-white rounded-lg p-6 max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">Trending Now</h3>
            <div className="mb-4">
              <h4 className="font-medium mb-2">Trending Topics</h4>
              {trendingTopics.map((topic) => (
                <button
                  key={topic.id}
                  className="block w-full text-left px-3 py-2 mb-1 border border-gray-200 rounded-md hover:bg-gray-100"
                  onClick={() => {
                    setShowOverlay(false);
                    navigate(`/search?q=${encodeURIComponent(topic.display_name)}&mode=topic`);
                  }}
                >
                  {topic.display_name}
                </button>
              ))}
            </div>
            <div>
              <h4 className="font-medium mb-2">Trending Scientists</h4>
              {trendingScientists.map((sc) => (
                <button
                  key={sc.id}
                  className="block w-full text-left px-3 py-2 mb-1 border border-gray-200 rounded-md hover:bg-gray-100"
                  onClick={() => {
                    setShowOverlay(false);
                    navigate(`/search?q=${encodeURIComponent(sc.display_name)}&mode=author`);
                  }}
                >
                  {sc.display_name}
                </button>
              ))}
            </div>
            <button
              className="mt-4 w-full text-center text-primary underline text-sm"
              onClick={() => setShowOverlay(false)}
            >
              Show me more results
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;