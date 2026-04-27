import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ClipboardList, CheckCircle, XCircle, ChevronDown, ChevronUp, Users,
} from 'lucide-react';
import { API, getAuthHeaders, JD, MatchResult, CandidateLookup } from '../utils/api';
import { recommendationBadge } from '../utils/badges';

interface LocalAction {
  action: 'shortlist' | 'reject';
  reason?: string;
}

const BATCH_SIZE = 3;
const MAX_BATCHES = 3;

const REJECTION_REASONS = [
  'Skills gap',
  'Experience level mismatch',
  'Salary expectation mismatch',
  'Location mismatch',
  'JD clarity issue',
  'Cultural fit concern',
  'Other',
];

const statusPill = (status: string) => {
  const map: Record<string, string> = {
    pool_ready:    'bg-emerald-500/20 text-emerald-400',
    matching_done: 'bg-blue-500/20 text-blue-400',
    open:          'bg-yellow-500/20 text-yellow-400',
    closed:        'bg-slate-500/20 text-slate-400',
  };
  const cls = map[status] ?? 'bg-slate-500/20 text-slate-400';
  return (
    <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded ${cls}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
};

const getCardClass = (actioned: boolean, actionState: LocalAction | null): string => {
  if (!actioned) return 'bg-slate-800/40 border-slate-700/50';
  return actionState?.action === 'shortlist'
    ? 'bg-emerald-900/10 border-emerald-500/20'
    : 'bg-red-900/10 border-red-500/20 opacity-75';
};

interface ContextualMatch {
  matches: string[];
  gaps: string[];
}

const evaluateContextualMatch = (result: MatchResult, jd: JD | undefined): ContextualMatch => {
  const matches: string[] = [];
  const gaps: string[] = [];

  if (!jd) return { matches, gaps };

  const candidate = result as any;
  const candidateCompanyTypes = candidate.company_types || [];
  const candidateTeamSize = candidate.avg_team_size || 'Unknown';
  const candidateRoleType = candidate.role_type || 'Unknown';

  const jdCompanyTypes = (jd as any).preferred_company_type || [];
  const jdTeamSize = (jd as any).preferred_team_size || 'Any';
  const jdRoleType = (jd as any).role_type || 'Any';

  // Company Type check
  if (jdCompanyTypes && jdCompanyTypes.length > 0 && !jdCompanyTypes.includes('Any')) {
    const matchingTypes = candidateCompanyTypes.filter((ct: string) => jdCompanyTypes.includes(ct));
    if (matchingTypes.length > 0) {
      matchingTypes.forEach((type: string) => {
        matches.push(`Worked in ${type}`);
      });
    } else if (candidateCompanyTypes.length > 0) {
      const nonMatching = jdCompanyTypes.filter((t: string) => !candidateCompanyTypes.includes(t));
      nonMatching.forEach((type: string) => {
        gaps.push(`No ${type} experience`);
      });
    } else {
      gaps.push('Company type unknown');
    }
  }

  // Team Size check
  if (jdTeamSize && jdTeamSize !== 'Any') {
    if (candidateTeamSize === jdTeamSize) {
      matches.push(`Team size matches: ${candidateTeamSize}`);
    } else if (candidateTeamSize !== 'Unknown') {
      gaps.push(`Team size mismatch: candidate ${candidateTeamSize}, JD needs ${jdTeamSize}`);
    } else {
      gaps.push('Team size unknown');
    }
  }

  // Role Type check
  if (jdRoleType && jdRoleType !== 'Any') {
    if (candidateRoleType === jdRoleType) {
      matches.push(`Role type matches: ${candidateRoleType}`);
    } else if (candidateRoleType !== 'Unknown') {
      gaps.push(`Role type mismatch: was ${candidateRoleType}, JD needs ${jdRoleType}`);
    } else {
      gaps.push('Role type unknown');
    }
  }

  return { matches, gaps };
};

const RecruiterDashboard: React.FC = () => {
  const [jds, setJds] = useState<JD[]>([]);
  const [selectedJdId, setSelectedJdId] = useState<string>('');
  const [results, setResults] = useState<MatchResult[]>([]);
  const [candidateNames, setCandidateNames] = useState<CandidateLookup>({});
  const [localActions, setLocalActions] = useState<Record<string, LocalAction>>({});
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Prevents stale results from a superseded JD click arriving after a newer one.
  const pendingJdRef = useRef<string>('');

  useEffect(() => {
    const init = async () => {
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
        setError('Failed to load: ' + e.message);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const loadJd = async (jdId: string) => {
    pendingJdRef.current = jdId;
    setSelectedJdId(jdId);
    setResults([]);
    setLocalActions({});
    setExpandedIds(new Set());
    setRejectingId(null);
    setError(null);
    try {
      const res = await fetch(`${API}/matching/results/${jdId}`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (pendingJdRef.current !== jdId) return;
      setResults(await res.json());
    } catch (e: any) {
      if (pendingJdRef.current !== jdId) return;
      setError('Failed to load JD data: ' + e.message);
    }
  };

  const computedStats = useMemo(() => {
    const shortlisted = results.filter(r =>
      localActions[r.candidate_id]?.action === 'shortlist' || r.status === 'shortlisted'
    ).length;
    const rejected = results.filter(r =>
      localActions[r.candidate_id]?.action === 'reject' || r.status === 'rejected'
    ).length;
    return { total: results.length, shortlisted, rejected, pending: results.length - shortlisted - rejected };
  }, [results, localActions]);

  const isActioned = (r: MatchResult) =>
    !!localActions[r.candidate_id] || r.status === 'shortlisted' || r.status === 'rejected';

  const getActionState = (r: MatchResult): LocalAction | null => {
    if (localActions[r.candidate_id]) return localActions[r.candidate_id];
    if (r.status === 'shortlisted') return { action: 'shortlist' };
    if (r.status === 'rejected') return { action: 'reject' };
    return null;
  };

  const computeActiveBatch = (): number => {
    for (let b = 0; b < MAX_BATCHES; b++) {
      const batch = results.slice(b * BATCH_SIZE, (b + 1) * BATCH_SIZE);
      if (batch.length === 0) return b;
      if (batch.some(r => !isActioned(r))) return b;
    }
    return MAX_BATCHES;
  };

  const activeBatchIndex = computeActiveBatch();
  const totalBatches = Math.min(MAX_BATCHES, Math.ceil(results.length / BATCH_SIZE));
  const poolExhausted = results.length > 0 && activeBatchIndex >= totalBatches;
  const currentBatch = results.slice(activeBatchIndex * BATCH_SIZE, (activeBatchIndex + 1) * BATCH_SIZE);
  const allCurrentActioned = currentBatch.length > 0 && currentBatch.every(r => isActioned(r));

  const submitAction = async (
    candidateId: string,
    body: { action: 'shortlist' | 'reject'; reason?: string },
    onSuccess: () => void,
  ) => {
    const jdId = selectedJdId;
    setActionLoading(candidateId);
    setError(null);
    try {
      const res = await fetch(`${API}/matching/action/${jdId}/${candidateId}`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (pendingJdRef.current !== jdId) return;
      onSuccess();
    } catch (e: any) {
      if (pendingJdRef.current !== jdId) return;
      setError('Action failed: ' + e.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleShortlist = (candidateId: string) =>
    submitAction(candidateId, { action: 'shortlist' }, () => {
      setLocalActions(prev => ({ ...prev, [candidateId]: { action: 'shortlist' } }));
    });

  const handleRejectConfirm = (candidateId: string) => {
    if (!rejectReason) return;
    submitAction(candidateId, { action: 'reject', reason: rejectReason }, () => {
      setLocalActions(prev => ({ ...prev, [candidateId]: { action: 'reject', reason: rejectReason } }));
      setRejectingId(null);
      setRejectReason('');
    });
  };

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const renderCandidateCard = (result: MatchResult) => {
    const actioned = isActioned(result);
    const actionState = getActionState(result);
    const expanded = expandedIds.has(result.candidate_id);
    const name = candidateNames[result.candidate_id] || result.candidate_id;
    const fitment = result.fitment_score;
    const score = result.composite_score ?? result.match_score * 100;
    const isRejecting = rejectingId === result.candidate_id;
    const isBusy = actionLoading === result.candidate_id;

    const selectedJd = jds.find(j => j.jd_id === selectedJdId);
    const contextualMatch = evaluateContextualMatch(result, selectedJd);
    const contextBonus = (result as any).context_bonus || 0;

    // Debug: log full result to see what fields are present
    if (expanded) {
      console.log('DEBUG MatchResult:', {
        candidate_id: result.candidate_id,
        context_bonus: (result as any).context_bonus,
        company_types: (result as any).company_types,
        avg_team_size: (result as any).avg_team_size,
        role_type: (result as any).role_type,
        all_result: result
      });
    }

    return (
      <div
        key={result.candidate_id}
        className={`rounded-2xl border overflow-hidden transition-all ${getCardClass(actioned, actionState)}`}
      >
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center space-x-3 min-w-0">
              <span className="text-slate-500 text-sm font-bold shrink-0">#{result.rank}</span>
              <div className="min-w-0">
                <p className="text-sm font-bold text-white truncate">{name}</p>
                <p className="text-[11px] text-slate-400 truncate">{result.candidate_id}</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <p className="text-xl font-bold text-white">
                {fitment != null ? `${fitment.toFixed(0)}%` : score.toFixed(1)}
              </p>
              <p className="text-[10px] text-slate-400">{fitment != null ? 'fitment' : 'score'}</p>
            </div>
          </div>

          {recommendationBadge(result.recommendation)}

          {result.strengths && result.strengths.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest mb-1">Strengths</p>
              <ul className="space-y-0.5">
                {result.strengths.slice(0, 3).map((s, i) => (
                  <li key={i} className="flex items-start space-x-1.5 text-xs text-slate-300">
                    <CheckCircle size={10} className="text-emerald-400 mt-0.5 shrink-0" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.gaps && result.gaps.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-1">Gaps</p>
              <ul className="space-y-0.5">
                {result.gaps.slice(0, 2).map((g, i) => (
                  <li key={i} className="flex items-start space-x-1.5 text-xs text-slate-300">
                    <XCircle size={10} className="text-red-400 mt-0.5 shrink-0" />
                    <span>{g}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.reasoning && (
            <>
              <button
                onClick={() => toggleExpand(result.candidate_id)}
                className="flex items-center space-x-1 text-[10px] font-bold text-slate-500 hover:text-slate-300 uppercase tracking-widest transition-colors"
              >
                <span>Reasoning</span>
                {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {expanded && (
                <p className="text-xs text-slate-300 leading-relaxed border-t border-slate-700/50 pt-3">
                  {result.reasoning}
                </p>
              )}
            </>
          )}

          {expanded && (contextualMatch.matches.length > 0 || contextualMatch.gaps.length > 0) && (
            <div className="border-t border-slate-700/50 pt-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Contextual Match</p>
                {contextBonus > 0 && (
                  <span className="text-[9px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    Context Bonus: +{contextBonus}pts
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                {/* Matches Column */}
                <div className="bg-emerald-900/10 border border-emerald-500/20 rounded-lg p-3 space-y-2">
                  <p className="text-[9px] font-bold text-emerald-400 uppercase tracking-widest">Matches</p>
                  {contextualMatch.matches.length > 0 ? (
                    <div className="space-y-1.5">
                      {contextualMatch.matches.map((match, i) => (
                        <div key={i} className="flex items-start space-x-1.5">
                          <CheckCircle size={11} className="text-emerald-400 mt-0.5 shrink-0" />
                          <span className="text-[10px] text-emerald-300">{match}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-start space-x-1.5">
                      <span className="text-[10px] text-slate-500">—</span>
                    </div>
                  )}
                </div>
                {/* Gaps Column */}
                <div className="bg-red-900/10 border border-red-500/20 rounded-lg p-3 space-y-2">
                  <p className="text-[9px] font-bold text-red-400 uppercase tracking-widest">Gaps</p>
                  {contextualMatch.gaps.length > 0 ? (
                    <div className="space-y-1.5">
                      {contextualMatch.gaps.map((gap, i) => (
                        <div key={i} className="flex items-start space-x-1.5">
                          <XCircle size={11} className="text-red-400 mt-0.5 shrink-0" />
                          <span className="text-[10px] text-red-300">{gap}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-start space-x-1.5">
                      <span className="text-[10px] text-slate-500">—</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-slate-700/30 px-5 py-3">
          {actioned ? (
            <div className={`flex items-center space-x-2 text-xs font-bold ${
              actionState?.action === 'shortlist' ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {actionState?.action === 'shortlist' ? (
                <><CheckCircle size={14} /><span>Shortlisted</span></>
              ) : (
                <><XCircle size={14} /><span>Rejected — {actionState?.reason}</span></>
              )}
            </div>
          ) : isRejecting ? (
            <div className="flex items-center space-x-2">
              <select
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                className="flex-1 bg-slate-900 border border-red-500/30 text-white text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-red-500"
              >
                <option value="">— Select reason —</option>
                {REJECTION_REASONS.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
              <button
                onClick={() => handleRejectConfirm(result.candidate_id)}
                disabled={!rejectReason || isBusy}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white text-xs font-bold rounded-lg transition-colors"
              >
                {isBusy ? '…' : 'Confirm'}
              </button>
              <button
                onClick={() => { setRejectingId(null); setRejectReason(''); }}
                className="px-3 py-2 text-slate-400 hover:text-white text-xs rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleShortlist(result.candidate_id)}
                disabled={isBusy}
                className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-bold rounded-lg transition-colors flex items-center justify-center space-x-1.5"
              >
                <CheckCircle size={12} />
                <span>Shortlist</span>
              </button>
              <button
                onClick={() => { setRejectingId(result.candidate_id); setRejectReason(''); }}
                disabled={isBusy}
                className="flex-1 py-2 bg-red-600/20 hover:bg-red-600/40 disabled:opacity-40 text-red-400 text-xs font-bold rounded-lg border border-red-500/20 transition-colors flex items-center justify-center space-x-1.5"
              >
                <XCircle size={12} />
                <span>Reject</span>
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center space-x-3">
        <div className="bg-blue-600/20 p-2 rounded-xl border border-blue-500/30">
          <ClipboardList size={20} className="text-blue-400" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-white">Recruiter Dashboard</h2>
          <p className="text-xs text-slate-400">3-batch candidate review · PRD §6.6</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center space-x-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl">
          <XCircle size={14} className="text-red-400 shrink-0" />
          <span className="text-xs text-red-300">{error}</span>
        </div>
      )}

      {/* Assigned JDs */}
      <section>
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4">Assigned Job Descriptions</p>
        {loading ? (
          <p className="text-slate-400 text-sm">Loading...</p>
        ) : jds.length === 0 ? (
          <p className="text-slate-500 text-sm">No job descriptions found.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {jds.map(jd => (
              <button
                key={jd.jd_id}
                onClick={() => loadJd(jd.jd_id)}
                className={`text-left p-5 rounded-2xl border transition-all ${
                  selectedJdId === jd.jd_id
                    ? 'bg-blue-600/20 border-blue-500/50'
                    : 'bg-slate-800/40 border-slate-700/50 hover:border-slate-500 hover:bg-slate-800/60'
                }`}
              >
                <p className="text-sm font-bold text-white truncate">{jd.title}</p>
                <p className="text-[11px] text-slate-400 mt-0.5 truncate">{jd.jd_id}</p>
                <div className="mt-3 flex items-center justify-between">
                  {statusPill(jd.status)}
                  {selectedJdId === jd.jd_id && results.length > 0 && (
                    <span className="flex items-center space-x-1 text-[10px] text-slate-400">
                      <Users size={10} />
                      <span>{results.length} in pool</span>
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Batch Review */}
      {selectedJdId && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Batch Review</p>
            {results.length > 0 && !poolExhausted && (
              <div className="flex items-center space-x-2">
                {Array.from({ length: totalBatches }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 w-10 rounded-full transition-all ${
                      i < activeBatchIndex ? 'bg-emerald-500' :
                      i === activeBatchIndex ? 'bg-blue-500' :
                      'bg-slate-700'
                    }`}
                  />
                ))}
                <span className="text-[10px] font-bold text-slate-400">
                  Batch {activeBatchIndex + 1} of {totalBatches}
                </span>
              </div>
            )}
          </div>

          {results.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              No candidates matched yet. Run the matching engine from the Matching Engine page.
            </div>
          ) : poolExhausted ? (
            <div className="text-center py-16 bg-slate-800/40 border border-slate-700/50 rounded-2xl">
              <CheckCircle size={36} className="text-emerald-400 mx-auto mb-3" />
              <p className="text-white font-bold text-lg">Pool Exhausted</p>
              <p className="text-slate-400 text-sm mt-1">
                All {totalBatches} batch{totalBatches !== 1 ? 'es' : ''} reviewed.{' '}
                {computedStats.shortlisted} candidate{computedStats.shortlisted !== 1 ? 's' : ''} shortlisted.
              </p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {currentBatch.map(r => renderCandidateCard(r))}
              </div>
              {!allCurrentActioned && (
                <p className="mt-4 text-center text-[11px] text-slate-600">
                  Action all {currentBatch.length} candidate{currentBatch.length !== 1 ? 's' : ''} to unlock Batch {activeBatchIndex + 2}
                </p>
              )}
            </>
          )}
        </section>
      )}

      {/* Pipeline Stats */}
      {selectedJdId && results.length > 0 && (
        <section>
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Pipeline Status</p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Total Matched',  value: computedStats.total,       cls: 'text-slate-300' },
              { label: 'Shortlisted',    value: computedStats.shortlisted,  cls: 'text-emerald-400' },
              { label: 'Rejected',       value: computedStats.rejected,     cls: 'text-red-400' },
              { label: 'Pending Review', value: computedStats.pending,      cls: 'text-yellow-400' },
            ].map(({ label, value, cls }) => (
              <div key={label} className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-5 text-center">
                <p className={`text-3xl font-bold ${cls}`}>{value}</p>
                <p className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">{label}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default RecruiterDashboard;
