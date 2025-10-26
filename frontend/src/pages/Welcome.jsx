import React from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Landing page shown on first load. Displays a hero call‑to‑action inviting
 * visitors to start exploring collaboration opportunities. Clicking the
 * primary button navigates to the dashboard where the search and charts
 * reside.
 */
const Welcome = () => {
  const navigate = useNavigate();
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-primary to-purple-200 p-6 text-center">
      <div className="max-w-2xl">
        <h1 className="text-4xl md:text-5xl font-bold text-white drop-shadow-lg">
          Collaboration starts here
        </h1>
        <p className="mt-4 text-xl md:text-2xl text-purple-100">
          Find the perfect co‑author or institution partner and explore cutting edge
          research trends.
        </p>
        <button
          onClick={() => navigate('/dashboard')}
          className="mt-8 px-6 py-3 bg-white text-primary font-semibold rounded-lg shadow hover:bg-purple-100 transition"
        >
          Start Exploring
        </button>
      </div>
    </main>
  );
};

export default Welcome;