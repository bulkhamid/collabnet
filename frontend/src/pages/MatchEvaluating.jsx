import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

/**
 * Match evaluation page. Simulates calculating compatibility with the selected
 * researcher. Displays a progress bar and placeholder content while the
 * compatibility metrics are being fetched from the backend. Once complete,
 * redirects to the compatibility summary page.
 */
const MatchEvaluating = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const targetId = searchParams.get('target');
  const targetName = searchParams.get('name');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!targetId) {
      navigate('/dashboard');
      return;
    }
    // Simulate progress bar
    const interval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 10, 95));
    }, 300);
    // Call backend to compute match
    async function computeMatch() {
      try {
        const res = await fetch('/api/match', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_id: targetId })
        });
        const payload = await res.json();
        clearInterval(interval);
        setProgress(100);
        // Navigate to compatibility page after short delay
        setTimeout(() => {
          navigate('/compatibility', { state: { targetName, breakdown: payload.breakdown, evidence: payload.evidence } });
        }, 700);
      } catch (err) {
        clearInterval(interval);
        setProgress(100);
        console.error(err);
        setTimeout(() => {
          navigate('/compatibility', { state: { targetName, breakdown: null, evidence: null, error: 'Failed to compute compatibility.' } });
        }, 700);
      }
    }
    computeMatch();
    return () => clearInterval(interval);
  }, [targetId, targetName, navigate]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4 text-center">Evaluating match…</h2>
        <div className="w-full bg-gray-200 rounded-full h-4 mb-4 overflow-hidden">
          <div
            className="bg-primary h-full rounded-full transition-all"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        {/* Skeleton content */}
        <div className="space-y-4 animate-pulse">
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded w-5/6"></div>
          <div className="h-4 bg-gray-200 rounded w-4/5"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    </div>
  );
};

export default MatchEvaluating;