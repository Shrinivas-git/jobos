import React, { useEffect, useState } from 'react';
import { Zap, ChevronDown, ChevronUp, CheckCircle, XCircle, Clock, AlertTriangle, RefreshCw } from 'lucide-react';
import { API, getAuthHeaders, JD, MatchResult, CandidateLookup } from '../utils/api';
import { recommendationBadge } from '../utils/badges';

const statusIcon = (status: string) => {
  if (status === 'pass_2_complete') return <CheckCircle size={14} className="text-emerald-400" />;
  if (status === 'pass_1') return <Clock size={14} className="text-yellow-400" />;
  return <AlertTriangle size={14} className="text-slate-400" />;
};

const Matching: React.FC = () => {
  const [jds, setJds] = useState<JD[]>([]);
  const [selectedJdId, setSelectedJdId] = useState<string>('');
  const [results, setResults] = useState<MatchResult[]>([]);
  const [candidateNames, setCandidateNames] = useState<CandidateLookup>({});
  const [loadingJds, setLoadingJds] = useState(true);
  const [running, setRunning] = useState(false);
  const [polling, setPolling] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [displayCount, setDisplayCount] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [lastRunTime, setLastRunTime] = useState<Date | null>(null);

  // Load JDs and candidate name lookup on mount
  useEffect(() => {
    const fetchInitial = async () => {
      try {
        const [jdRes, candRes] = await Promise.all([
          fetch(`${API}/jd/`, { headers: getAuthHeaders() }),
          fetch(`${API}/candidates/`, { headers: getAuthHeaders() }),
        ]);
        const jdData: JD[] = await jdRes.json();
        const candData: { candidate_id: string; name?: string }[] = await candRes.json();

        setJds(jdData);

        const lookup: CandidateLookup = {};
        candData.forEach(c => { lookup[c.candidate_id] = c.name || c.candidate_id; });
        setCandidateNames(lookup);
      } catch (e: any) {
        setError('Failed to load data: ' + e.message);
      } finally {
        setLoadingJds(false);
      }
    };
    fetchInitial();
  }, []);

  const fetchResults = async (jd_id: string, fromTrigger = false) => {
    try {
      const res = await fetch(`${API}/matching/results/${jd_id}`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: MatchResult[] = await res.json();
      setResults(data);
      if (fromTrigger && data.length > 0) setLastRunTime(new Date());
      return data;
    } catch (e: any) {
      setError('Failed to fetch results: ' + e.message);
      return [];
    }
  };

  const handleJdChange = async (jd_id: string) => {
    setSelectedJdId(jd_id);
    setResults([]);
    setLastRunTime(null);
    setDisplayCount(3);
    setExpandedRows(new Set());
    setRunMessage(null);
    setError(null);
    if (jd_id) await fetchResults(jd_id);
  };

  const handleRunMatching = async () => {
    if (!selectedJdId) return;
    setRunning(true);
    setError(null);
    setRunMessage(null);
    try {
      const res = await fetch(`${API}/matching/run/${selectedJdId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRunMessage('Matching triggered. Pass 1 running — results will appear below as they complete.');
      setPolling(true);
      pollResults(selectedJdId);
    } catch (e: any) {
      setError('Failed to trigger matching: ' + e.message);
    } finally {
      setRunning(false);
    }
  };

  const pollResults = (jd_id: string) => {
    let attempts = 0;
    const maxAttempts = 20;
    const interval = setInterval(async () => {
      attempts++;
      const data = await fetchResults(jd_id, true);
      const allPass2 = data.length > 0 && data.every(r => r.status === 'pass_2_complete');
      if (allPass2 || attempts >= maxAttempts) {
        clearInterval(interval);
        setPolling(false);
        if (allPass2) setRunMessage('Pass 2 complete — all candidates evaluated.');
        else if (attempts >= maxAttempts) setRunMessage('Polling timed out. Refresh manually.');
      }
    }, 3000);
  };

  const toggleRow = (candidate_id: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      next.has(candidate_id) ? next.delete(candidate_id) : next.add(candidate_id);
      return next;
    });
  };

  const getTimeAgo = (date: Date): string => {
    const secs = Math.floor((Date.now() - date.getTime()) / 1000);
    if (secs < 60) return 'now';
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
    return `${Math.floor(secs / 3600)}h ago`;
  };

  const visible = results.slice(0, displayCount);
  const hasMore = results.length > displayCount;
  const pass2Done = results.some(r => r.status === 'pass_2_complete');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <div className="bg-violet-600/20 p-2 rounded-xl border border-violet-500/30">
          <Zap size={20} className="text-violet-400" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-white">Matching Engine</h2>
          <p className="text-xs text-slate-400">2-pass Qdrant + Groq intelligence layer</p>
        </div>
      </div>

      {/* JD Selector + Run */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 space-y-4">
        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">Select Job Description</label>
        {loadingJds ? (
          <div className="text-slate-400 text-sm">Loading job descriptions...</div>
        ) : (
          <div className="flex items-center space-x-4">
            <select
              value={selectedJdId}
              onChange={e => handleJdChange(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-violet-500"
            >
              <option value="">— Choose a JD —</option>
              {jds.map(jd => (
                <option key={jd.jd_id} value={jd.jd_id}>
                  {jd.title} ({jd.jd_id}) — {jd.status}
                </option>
              ))}
            </select>
            <button
              onClick={handleRunMatching}
              disabled={!selectedJdId || running || polling}
              className="px-6 py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl transition-colors flex items-center space-x-2"
            >
              {(running || polling) ? (
                <RefreshCw size={14} className="animate-spin" />
              ) : (
                <Zap size={14} />
              )}
              <span>{running ? 'Triggering…' : polling ? 'Running…' : 'Run Matching'}</span>
            </button>
          </div>
        )}

        {/* Status banners */}
        {runMessage && (
          <div className="flex items-center space-x-2 px-4 py-3 bg-violet-500/10 border border-violet-500/20 rounded-xl">
            <CheckCircle size={14} className="text-violet-400 shrink-0" />
            <span className="text-xs text-violet-300">{runMessage}</span>
          </div>
        )}
        {error && (
          <div className="flex items-center space-x-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl">
            <XCircle size={14} className="text-red-400 shrink-0" />
            <span className="text-xs text-red-300">{error}</span>
          </div>
        )}
        {polling && (
          <div className="flex items-center space-x-2 px-4 py-3 bg-yellow-500/10 border border-yellow-500/20 rounded-xl">
            <RefreshCw size={14} className="text-yellow-400 animate-spin shrink-0" />
            <span className="text-xs text-yellow-300">Polling for Pass 2 results every 3s…</span>
          </div>
        )}
      </div>

      {/* Results */}
      {selectedJdId && results.length === 0 && !polling && (
        <div className="text-center py-12 text-slate-500 text-sm">
          No matching results yet. Run the matching engine above.
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                {results.length} candidate{results.length !== 1 ? 's' : ''} matched
                {pass2Done ? ' — Pass 2 complete' : ' — Pass 1 only (Pass 2 pending)'}
              </p>
              {lastRunTime ? (
                <p className="text-[10px] text-slate-500 mt-1">Last run: {getTimeAgo(lastRunTime)}</p>
              ) : (
                <p className="text-[10px] text-slate-500 mt-1">Loaded from database</p>
              )}
            </div>
          </div>

          {visible.map(result => {
            const expanded = expandedRows.has(result.candidate_id);
            const name = candidateNames[result.candidate_id] || result.candidate_id;
            const score = result.composite_score ?? result.match_score * 100;

            return (
              <div
                key={result.candidate_id}
                className="bg-slate-800/40 border border-slate-700/50 rounded-2xl overflow-hidden"
              >
                {/* Row header */}
                <button
                  onClick={() => toggleRow(result.candidate_id)}
                  className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-700/20 transition-colors"
                >
                  <div className="flex items-center space-x-4">
                    <div className="text-slate-500 text-sm font-bold w-6 text-left">#{result.rank}</div>
                    <div className="text-left">
                      <p className="text-sm font-bold text-white">{name}</p>
                      <p className="text-[11px] text-slate-400">{result.candidate_id}</p>
                    </div>
                    <div className="flex items-center space-x-1">
                      {statusIcon(result.status)}
                      <span className="text-[10px] text-slate-400">{result.status}</span>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <p className="text-lg font-bold text-white">{score.toFixed(1)}</p>
                      <p className="text-[10px] text-slate-400">composite score</p>
                    </div>
                    {recommendationBadge(result.recommendation)}
                    <div className="text-slate-400">
                      {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </div>
                  </div>
                </button>

                {/* Expanded detail */}
                {expanded && (
                  <div className="border-t border-slate-700/50 px-6 py-5 space-y-4">
                    {/* Score breakdown */}
                    <div className="grid grid-cols-3 gap-4">
                      {[
                        { label: 'Cosine (Pass 1)', value: (result.match_score * 100).toFixed(1) },
                        { label: 'Fitment (Pass 2)', value: result.fitment_score != null ? result.fitment_score.toFixed(1) : '—' },
                        { label: 'Completeness', value: result.completeness_score != null ? result.completeness_score.toFixed(1) : '—' },
                      ].map(({ label, value }) => (
                        <div key={label} className="bg-slate-900/50 rounded-xl p-3 text-center">
                          <p className="text-lg font-bold text-white">{value}</p>
                          <p className="text-[10px] text-slate-400 mt-0.5">{label}</p>
                        </div>
                      ))}
                    </div>

                    {result.reasoning && (
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Reasoning</p>
                        <p className="text-sm text-slate-300 leading-relaxed">{result.reasoning}</p>
                      </div>
                    )}

                    {(result.strengths?.length || result.gaps?.length) && (
                      <div className="grid grid-cols-2 gap-4">
                        {result.strengths && result.strengths.length > 0 && (
                          <div>
                            <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest mb-2">Strengths</p>
                            <ul className="space-y-1">
                              {result.strengths.map((s, i) => (
                                <li key={i} className="flex items-start space-x-2 text-xs text-slate-300">
                                  <CheckCircle size={11} className="text-emerald-400 mt-0.5 shrink-0" />
                                  <span>{s}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {result.gaps && result.gaps.length > 0 && (
                          <div>
                            <p className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-2">Gaps</p>
                            <ul className="space-y-1">
                              {result.gaps.map((g, i) => (
                                <li key={i} className="flex items-start space-x-2 text-xs text-slate-300">
                                  <XCircle size={11} className="text-red-400 mt-0.5 shrink-0" />
                                  <span>{g}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Load more */}
          {hasMore && (
            <button
              onClick={() => setDisplayCount(c => c + 3)}
              className="w-full py-3 text-xs font-bold text-slate-400 hover:text-white border border-slate-700/50 hover:border-slate-500 rounded-xl transition-colors"
            >
              Show {Math.min(3, results.length - displayCount)} more
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default Matching;
