import React, { useState } from 'react';
import { ShieldCheck, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import keycloak from '../keycloak';
import { API, getAuthHeaders } from '../utils/api';

interface ConsentProps {
  candidateId: string;
  onAccepted: () => void;
}

const Consent: React.FC<ConsentProps> = ({ candidateId, onAccepted }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAccept = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API}/candidates/${candidateId}/consent`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed to record consent');
      onAccepted();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 max-w-lg w-full shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-blue-600/20 rounded-xl">
            <ShieldCheck className="text-blue-400" size={24} />
          </div>
          <h2 className="text-xl font-bold text-white">Data Consent Required</h2>
        </div>

        <p className="text-slate-300 text-sm leading-relaxed mb-4">
          Under the <strong className="text-white">Digital Personal Data Protection Act (DPDP), 2023</strong>,
          we require your explicit consent before processing your personal data.
        </p>

        <ul className="space-y-2 mb-6">
          {[
            'Your resume and profile data will be used solely for recruitment matching.',
            'Your data will not be shared with third parties without consent.',
            'You may request erasure of your data at any time.',
            'Data is stored securely and access is logged for audit purposes.',
          ].map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-slate-400">
              <CheckCircle size={14} className="text-emerald-400 mt-0.5 shrink-0" />
              {item}
            </li>
          ))}
        </ul>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2">
            <AlertCircle size={16} className="text-red-400" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleAccept}
            disabled={loading}
            className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {loading ? <><Loader size={16} className="animate-spin" /> Recording...</> : 'I Accept'}
          </button>
          <button
            onClick={() => keycloak.logout()}
            disabled={loading}
            className="flex-1 py-2.5 bg-slate-700/50 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg transition-colors"
          >
            Decline & Logout
          </button>
        </div>
      </div>
    </div>
  );
};

export default Consent;
