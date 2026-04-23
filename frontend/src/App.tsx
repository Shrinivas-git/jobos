import React, { useEffect, useState, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import keycloak from './keycloak';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Candidates from './pages/Candidates';
import Documents from './pages/Documents';
import CRM from './pages/CRM';
import Analytics from './pages/Analytics';

const App: React.FC = () => {
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    keycloak.init({ 
      onLoad: 'login-required', 
      checkLoginIframe: false,
      pkceMethod: 'S256'
    })
      .then((auth) => {
        setAuthenticated(auth);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Authenticated Failed", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-900 text-white space-y-4">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-lg font-medium">Loading JobOS...</p>
      </div>
    );
  }

  if (!authenticated) {
    return <div className="flex items-center justify-center h-screen bg-gray-900 text-white">Redirecting to Login...</div>;
  }

  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/crm" element={<CRM />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="*" element={<div className="text-white p-8">Page Not Found</div>} />
        </Routes>
      </Layout>
    </Router>
  );
};

export default App;
