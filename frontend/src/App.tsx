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
import Matching from './pages/Matching';
import Admin from './pages/Admin';
import Invoices from './pages/Invoices';
import Assessment from './pages/Assessment';
import OfferResponse from './pages/OfferResponse';
import FormResponses from './pages/FormResponses';
import CandidateForm from './pages/CandidateForm';

// Public paths that must not trigger Keycloak login-required redirect
const _isPublicPath =
  window.location.pathname.startsWith('/assessment/') ||
  window.location.pathname.startsWith('/offer-response/') ||
  window.location.pathname.startsWith('/form/') ||
  window.location.pathname.startsWith('/apply/');

const App: React.FC = () => {
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    keycloak.init({
      onLoad: _isPublicPath ? 'check-sso' : 'login-required',
      checkLoginIframe: false,
      pkceMethod: 'S256'
    })
      .then((auth) => {
        setAuthenticated(auth);
        setLoading(false);

        // Refresh token 60 s before expiry; log out if refresh fails
        keycloak.onTokenExpired = () => {
          keycloak.updateToken(60).catch(() => keycloak.logout());
        };
        // Proactive check every 60 s — catches cases where onTokenExpired fires late
        setInterval(() => {
          keycloak.updateToken(60).catch(() => keycloak.logout());
        }, 60000);
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

  return (
    <Router>
      <Routes>
        {/* Public routes — no auth, no layout */}
        <Route path="/assessment/:id" element={<Assessment />} />
        <Route path="/offer-response/:token" element={<OfferResponse />} />
        <Route path="/form/:jdId/:candidateId" element={<CandidateForm />} />
        <Route path="/apply/:jdId/:candidateId" element={<CandidateForm />} />
        <Route path="/apply/:jdId" element={<CandidateForm />} />

        {/* Auth-gated routes */}
        <Route path="/*" element={
          !authenticated ? (
            <div className="flex items-center justify-center h-screen bg-gray-900 text-white">
              Redirecting to Login...
            </div>
          ) : (
            <Layout>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="/candidates" element={<Candidates />} />
                <Route path="/documents" element={<Documents />} />
                <Route path="/crm" element={<CRM />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/matching" element={<Matching />} />
                <Route path="/form-responses" element={<FormResponses />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="/invoices" element={
                  keycloak.tokenParsed?.realm_access?.roles?.some((r: string) => ['manager','admin'].includes(r))
                    ? <Invoices />
                    : <Navigate to="/dashboard" replace />
                } />
                <Route path="*" element={<div className="text-white p-8">Page Not Found</div>} />
              </Routes>
            </Layout>
          )
        } />
      </Routes>
    </Router>
  );
};

export default App;
