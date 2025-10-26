import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Welcome from './pages/Welcome';
import Dashboard from './pages/Dashboard';
import SearchResults from './pages/SearchResults';
import MatchEvaluating from './pages/MatchEvaluating';
import Compatibility from './pages/Compatibility';

/**
 * Top level application component. Defines the client‑side routes for the
 * Collaborator Finder. Each route corresponds to a page in the design PDF.
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/search" element={<SearchResults />} />
        <Route path="/match" element={<MatchEvaluating />} />
        <Route path="/compatibility" element={<Compatibility />} />
        <Route path="*" element={<div className="p-8 text-center">Page not found</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;