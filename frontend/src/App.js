import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Companies from './pages/Companies';
import CompanyDetail from './pages/CompanyDetail';
import ErrorBoundary from './components/ErrorBoundary';
import HealthCheck from './components/HealthCheck';

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <div className="flex h-screen bg-bg overflow-hidden">
          <HealthCheck />
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/companies" element={<Companies />} />
              <Route path="/companies/:id" element={<CompanyDetail />} />
            </Routes>
          </main>
        </div>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
