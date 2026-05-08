import React, { useEffect, useState } from 'react';
import { API, getAuthHeaders } from '../utils/api';
import { RefreshCw, Download, Eye, CheckCircle, Clock, AlertCircle } from 'lucide-react';

interface FormResponse {
  response_id: string;
  candidate_id: string;
  jd_id: string;
  aadhar?: string;
  linkedin_url?: string;
  alternate_phone?: string;
  telegram_handle?: string;
  video_resume_path?: string;
  video_analysis?: {
    confidence_score: number;
    articulation_score: number;
    eye_contact_score: number;
    professionalism_score: number;
    traits: string[];
    overall_impression: string;
    analyzed_at: string;
  };
  status: string;
  submitted_at: string;
  created_at: string;
}

interface JD {
  jd_id: string;
  title: string;
}

const FormResponses: React.FC = () => {
  const [jds, setJds] = useState<JD[]>([]);
  const [selectedJdId, setSelectedJdId] = useState<string>('');
  const [responses, setResponses] = useState<FormResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ total: 0, submitted: 0, video_analyzed: 0 });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedResponse, setSelectedResponse] = useState<FormResponse | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  useEffect(() => {
    fetchJds();
  }, []);

  const fetchJds = async () => {
    try {
      const res = await fetch(`${API}/jd/`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error('Failed to fetch JDs');
      const data = await res.json();
      setJds(data);
    } catch (e: any) {
      console.error('Error fetching JDs:', e.message);
    }
  };

  const fetchResponses = async (jd_id: string) => {
    if (!jd_id) return;
    setLoading(true);
    try {
      const [responsesRes, statsRes] = await Promise.all([
        fetch(`${API}/forms/responses/${jd_id}`, { headers: getAuthHeaders() }),
        fetch(`${API}/forms/status/${jd_id}`, { headers: getAuthHeaders() })
      ]);

      if (!responsesRes.ok || !statsRes.ok) throw new Error('Failed to fetch data');

      const responsesData = await responsesRes.json();
      const statsData = await statsRes.json();

      setResponses(responsesData);
      setStats(statsData);
    } catch (e: any) {
      console.error('Error fetching responses:', e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleJdChange = (jd_id: string) => {
    setSelectedJdId(jd_id);
    setExpandedId(null);
    fetchResponses(jd_id);
  };

  const handleViewDetails = (response: FormResponse) => {
    setSelectedResponse(response);
    setShowDetailModal(true);
  };

  const getVideoStatus = (response: FormResponse) => {
    if (response.video_analysis?.analyzed_at) {
      return { status: 'analyzed', label: '✓ Analyzed', color: 'text-emerald-400' };
    } else if (response.video_resume_path) {
      return { status: 'analyzing', label: '⏳ Analyzing...', color: 'text-yellow-400' };
    } else {
      return { status: 'missing', label: '✗ No Video', color: 'text-red-400' };
    }
  };

  const jd = jds.find(j => j.jd_id === selectedJdId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Form Responses</h1>
          <p className="text-sm text-slate-400 mt-0.5">Track video resume submissions and analysis</p>
        </div>
        <button
          onClick={() => selectedJdId && fetchResponses(selectedJdId)}
          className="flex items-center gap-1.5 px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg border border-slate-600/50 transition-colors"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* JD Selector */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6">
        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">Select Job Description</label>
        <select
          value={selectedJdId}
          onChange={e => handleJdChange(e.target.value)}
          className="w-full mt-3 bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">— Choose a JD —</option>
          {jds.map(j => (
            <option key={j.jd_id} value={j.jd_id}>
              {j.title} ({j.jd_id})
            </option>
          ))}
        </select>
      </div>

      {/* Stats */}
      {selectedJdId && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Total Forms', value: stats.total, color: 'text-blue-400' },
            { label: 'Submitted', value: stats.submitted, color: 'text-emerald-400' },
            { label: 'Videos Analyzed', value: stats.video_analyzed, color: 'text-violet-400' }
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-slate-800/40 border border-slate-700/50 rounded-2xl px-5 py-4">
              <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">{label}</p>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Responses List */}
      {selectedJdId && (
        loading ? (
          <div className="text-center py-12 text-slate-400">Loading responses...</div>
        ) : responses.length === 0 ? (
          <div className="text-center py-12 text-slate-500">No form submissions yet</div>
        ) : (
          <div className="space-y-3">
            {responses.map(response => {
              const videoStatus = getVideoStatus(response);
              const isExpanded = expandedId === response.response_id;

              return (
                <div
                  key={response.response_id}
                  className="bg-slate-800/40 border border-slate-700/50 rounded-2xl overflow-hidden"
                >
                  {/* Row Header */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : response.response_id)}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-700/20 transition-colors text-left"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <p className="font-semibold text-white text-sm">{response.candidate_id}</p>
                        <span className={`text-xs px-2 py-1 rounded-lg font-bold ${
                          response.status === 'submitted' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-700/50 text-slate-400'
                        }`}>
                          {response.status === 'submitted' ? '✓ Submitted' : response.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Submitted: {new Date(response.submitted_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className={`text-sm font-bold ${videoStatus.color}`}>{videoStatus.label}</p>
                        {response.video_analysis?.traits && (
                          <p className="text-xs text-slate-500 mt-1">{response.video_analysis.traits.join(', ')}</p>
                        )}
                      </div>
                      <button
                        onClick={() => handleViewDetails(response)}
                        className="p-2 hover:bg-slate-700/50 rounded-lg text-slate-400 hover:text-white transition-colors"
                      >
                        <Eye size={16} />
                      </button>
                    </div>
                  </button>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="border-t border-slate-700/50 px-6 py-5 bg-slate-900/30 space-y-4">
                      {/* Form Data */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs font-bold text-slate-400 uppercase mb-1">Aadhar</p>
                          <p className="text-sm text-white">{response.aadhar || '—'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-400 uppercase mb-1">Telegram</p>
                          <p className="text-sm text-white">{response.telegram_handle || '—'}</p>
                        </div>
                        <div className="col-span-2">
                          <p className="text-xs font-bold text-slate-400 uppercase mb-1">LinkedIn</p>
                          <a href={response.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-400 hover:text-blue-300">
                            {response.linkedin_url || '—'}
                          </a>
                        </div>
                      </div>

                      {/* Video Analysis */}
                      {response.video_analysis && (
                        <div className="bg-slate-800/50 rounded-xl p-4">
                          <h4 className="text-sm font-bold text-white mb-3">📹 Video Analysis</h4>

                          <div className="grid grid-cols-4 gap-3 mb-4">
                            {[
                              { label: 'Confidence', value: response.video_analysis.confidence_score },
                              { label: 'Articulation', value: response.video_analysis.articulation_score },
                              { label: 'Eye Contact', value: response.video_analysis.eye_contact_score },
                              { label: 'Professional', value: response.video_analysis.professionalism_score }
                            ].map(({ label, value }) => (
                              <div key={label} className="bg-slate-900/50 rounded-lg p-2 text-center">
                                <p className="text-lg font-bold text-blue-400">{value}/10</p>
                                <p className="text-xs text-slate-500 mt-1">{label}</p>
                              </div>
                            ))}
                          </div>

                          {response.video_analysis.traits && (
                            <div className="mb-3">
                              <p className="text-xs font-bold text-slate-400 mb-2">TRAITS</p>
                              <div className="flex flex-wrap gap-2">
                                {response.video_analysis.traits.map(trait => (
                                  <span key={trait} className="px-2 py-1 bg-blue-500/15 text-blue-400 rounded text-xs font-medium">
                                    {trait}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          <p className="text-sm text-slate-300 italic">
                            "{response.video_analysis.overall_impression}"
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedResponse && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl max-w-2xl w-full max-h-96 overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white">{selectedResponse.candidate_id}</h2>
              <button
                onClick={() => setShowDetailModal(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            {selectedResponse.video_analysis && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-blue-400 mb-3">Video Analysis</h3>
                  <p className="text-sm text-slate-300">{selectedResponse.video_analysis.overall_impression}</p>
                </div>

                <div className="bg-slate-900/50 rounded-lg p-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-slate-400">Confidence</p>
                      <p className="text-2xl font-bold text-emerald-400">{selectedResponse.video_analysis.confidence_score}/10</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Articulation</p>
                      <p className="text-2xl font-bold text-emerald-400">{selectedResponse.video_analysis.articulation_score}/10</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Eye Contact</p>
                      <p className="text-2xl font-bold text-emerald-400">{selectedResponse.video_analysis.eye_contact_score}/10</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Professionalism</p>
                      <p className="text-2xl font-bold text-emerald-400">{selectedResponse.video_analysis.professionalism_score}/10</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default FormResponses;
