import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle, Loader } from 'lucide-react';
import keycloak from '../keycloak';

interface Config {
  p_threshold: number;
  k_threshold: number;
  batch_size: number;
}

const Admin: React.FC = () => {
  const roles = keycloak.tokenParsed?.realm_access?.roles || [];
  const isAdmin = roles.includes('admin');
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState<Config>({
    p_threshold: 0.5,
    k_threshold: 10,
    batch_size: 3,
  });

  useEffect(() => {
    if (!isAdmin) return;

    const fetchConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/admin/config`,
          {
            headers: {
              Authorization: `Bearer ${keycloak.token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to load config: ${response.statusText}`);
        }

        const data = await response.json();
        setConfig(data);
        setFormData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load configuration');
      } finally {
        setLoading(false);
      }
    };

    fetchConfig();
  }, [isAdmin]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'batch_size' || name === 'k_threshold' ? parseInt(value) || 0 : parseFloat(value) || 0,
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/admin/config`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${keycloak.token}`,
          },
          body: JSON.stringify(formData),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Failed to save config: ${response.statusText}`);
      }

      await response.json();
      setSuccess('Configuration updated successfully');
      setConfig(formData);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (config) {
      setFormData(config);
      setError(null);
    }
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="mx-auto mb-4 text-red-500" size={48} />
          <h2 className="text-xl font-bold text-white mb-2">Access Denied</h2>
          <p className="text-slate-400">You do not have admin privileges to access this page.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <Loader className="mx-auto mb-4 text-blue-500 animate-spin" size={48} />
          <p className="text-slate-400">Loading configuration...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-8">
        <h1 className="text-2xl font-bold text-white mb-2">System Configuration</h1>
        <p className="text-slate-400 mb-8">Manage core matching engine parameters.</p>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3">
            <AlertCircle className="text-red-400 mt-0.5" size={20} />
            <div>
              <p className="text-sm font-semibold text-red-400">Error</p>
              <p className="text-sm text-red-300 mt-1">{error}</p>
            </div>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-start gap-3">
            <CheckCircle className="text-emerald-400 mt-0.5" size={20} />
            <div>
              <p className="text-sm font-semibold text-emerald-400">Success</p>
              <p className="text-sm text-emerald-300 mt-1">{success}</p>
            </div>
          </div>
        )}

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-white mb-2">
              Probability Threshold (p_threshold)
            </label>
            <input
              type="number"
              name="p_threshold"
              value={formData.p_threshold}
              onChange={handleChange}
              min="0"
              max="1"
              step="0.01"
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-slate-400 mt-2">
              Minimum probability score for a candidate match (0.0 - 1.0)
            </p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-white mb-2">
              K Threshold (k_threshold)
            </label>
            <input
              type="number"
              name="k_threshold"
              value={formData.k_threshold}
              onChange={handleChange}
              min="1"
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-slate-400 mt-2">
              Number of top candidates to return from vector search
            </p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-white mb-2">
              Batch Size (batch_size)
            </label>
            <input
              type="number"
              name="batch_size"
              value={formData.batch_size}
              onChange={handleChange}
              min="1"
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-slate-400 mt-2">
              Number of candidates to process per batch in matching operations
            </p>
          </div>
        </div>

        <div className="flex gap-3 mt-8">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {saving ? (
              <>
                <Loader size={16} className="animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </button>
          <button
            onClick={handleReset}
            disabled={saving}
            className="flex-1 px-6 py-2.5 bg-slate-700/50 hover:bg-slate-700 disabled:bg-slate-700/30 text-slate-300 font-semibold rounded-lg transition-colors"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
};

export default Admin;
