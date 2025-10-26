import React, { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Doughnut, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
} from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

/**
 * Compatibility summary page. Displays an overall match score using a radial
 * gauge and a breakdown of sub‑scores in a bar chart. Additional evidence
 * such as overlapping concepts, shared co‑authors, and aligned publications
 * is listed below. If an error occurs during match computation, a fallback
 * message is shown.
 */
const Compatibility = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const targetName = state?.targetName || 'Selected Researcher';
  const breakdown = state?.breakdown;
  const evidence = state?.evidence;
  const error = state?.error;

  const gaugeData = useMemo(() => {
    const overall = breakdown?.overall || 0;
    return {
      labels: ['Compatibility', 'Remaining'],
      datasets: [
        {
          data: [overall, 100 - overall],
          backgroundColor: ['#5e2ca5', '#e5e7eb'],
          hoverBackgroundColor: ['#5e2ca5', '#e5e7eb'],
          borderWidth: 0,
        },
      ],
    };
  }, [breakdown]);

  const breakdownData = useMemo(() => {
    const labels = ['Topic Similarity', 'Co‑author Distance', 'Institution Proximity', 'Recency Alignment'];
    const data = breakdown
      ? [breakdown.topic_similarity, breakdown.coauthor_distance, breakdown.institution_proximity, breakdown.recency_alignment]
      : [0, 0, 0, 0];
    return {
      labels,
      datasets: [
        {
          label: 'Score',
          data,
          backgroundColor: ['#5e2ca5', '#69b3a2', '#ff7f0e', '#c05a00'],
        },
      ],
    };
  }, [breakdown]);

  return (
    <div className="min-h-screen bg-gray-50 p-6 text-gray-800">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-primary">CollabNet</h1>
        <button className="text-sm text-primary hover:underline" onClick={() => navigate('/dashboard')}>Dashboard</button>
      </header>
      <div className="max-w-5xl mx-auto bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-semibold mb-6">Compatibility with {targetName}</h2>
        {error ? (
          <div className="text-red-500">{error}</div>
        ) : (
          <>
            <div className="grid gap-8 grid-cols-1 md:grid-cols-2">
              {/* Gauge chart */}
              <div className="flex flex-col items-center justify-center">
                <div className="relative w-56 h-56 md:w-64 md:h-64">
                  <Doughnut data={gaugeData} options={{ plugins: { legend: { display: false } }, cutout: '70%' }} />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-3xl font-bold text-primary">
                      {breakdown?.overall ?? 0}%
                    </span>
                  </div>
                </div>
                <p className="mt-2 text-gray-600">Overall Compatibility</p>
              </div>
              {/* Breakdown bar chart */}
              <div>
                <Bar data={breakdownData} options={{ indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { max: 100, beginAtZero: true } } }} />
              </div>
            </div>
            {/* Evidence lists */}
            <div className="mt-8 grid gap-8 grid-cols-1 md:grid-cols-3">
              <div>
                <h3 className="font-semibold text-lg mb-2">Overlapping Concepts</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-700">
                  {evidence?.overlapping_concepts?.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  )) || <li>No overlapping concepts available.</li>}
                </ul>
              </div>
              <div>
                <h3 className="font-semibold text-lg mb-2">Shared Co‑authors</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-700">
                  {evidence?.shared_coauthors?.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  )) || <li>No shared co‑authors identified.</li>}
                </ul>
              </div>
              <div>
                <h3 className="font-semibold text-lg mb-2">Aligned Publications</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-700">
                  {evidence?.aligned_publications?.map((pub, idx) => (
                    <li key={idx}>{pub.title} ({pub.year})</li>
                  )) || <li>No aligned publications found.</li>}
                </ul>
              </div>
            </div>
          </>
        )}
        <div className="mt-8 flex gap-4">
          <button
            onClick={() => navigate(-1)}
            className="px-4 py-2 border border-primary text-primary rounded-md hover:bg-primary hover:text-white transition"
          >
            Go Back
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-4 py-2 bg-primary text-white rounded-md hover:bg-primary-dark transition"
          >
            Finish
          </button>
        </div>
      </div>
    </div>
  );
};

export default Compatibility;