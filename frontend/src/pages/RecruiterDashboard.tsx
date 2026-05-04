import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ClipboardList, CheckCircle, XCircle, ChevronDown, ChevronUp, Users,
  Clock, AlertTriangle, ArrowRight, Calendar, X,
} from 'lucide-react';
import keycloak from '../keycloak';
import {
  API, getAuthHeaders, JD, MatchResult, CandidateLookup,
  PipelineRecord, PipelineBreach, PipelineStageEntry,
} from '../utils/api';
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

const STAGE_LABELS: Record<string, string> = {
  shortlist: 'Shortlisted',
  interview_1: 'Interview 1',
  interview_final: 'Final Interview',
  offer: 'Offer',
  joined: 'Joined',
};
const STAGE_ORDER = ['shortlist', 'interview_1', 'interview_final', 'offer', 'joined'];

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

const getSlaProgress = (stage: PipelineStageEntry): { pct: number; barColor: string; textColor: string } => {
  const now = Date.now();
  const entered = new Date(stage.entered_at).getTime();
  const dueMs = stage.extension?.approved && stage.extension.approved_until
    ? new Date(stage.extension.approved_until).getTime()
    : new Date(stage.due_at).getTime();
  const total = dueMs - entered;
  const elapsed = now - entered;
  const rawPct = total > 0 ? Math.round((elapsed / total) * 100) : 100;
  const pct = Math.min(rawPct, 100);
  if (rawPct < 75) return { pct, barColor: 'bg-emerald-500', textColor: 'text-emerald-400' };
  if (rawPct < 100) return { pct, barColor: 'bg-yellow-500', textColor: 'text-yellow-400' };
  return { pct: 100, barColor: 'bg-red-500', textColor: 'text-red-400' };
};

const formatTimeRemaining = (stage: PipelineStageEntry): string => {
  const now = Date.now();
  const dueMs = stage.extension?.approved && stage.extension.approved_until
    ? new Date(stage.extension.approved_until).getTime()
    : new Date(stage.due_at).getTime();
  const diffMs = dueMs - now;
  if (diffMs <= 0) {
    const h = Math.floor(-diffMs / 3600000);
    return h < 24 ? `${h}h overdue` : `${Math.floor(h / 24)}d overdue`;
  }
  const h = Math.floor(diffMs / 3600000);
  if (h >= 24) return `${Math.floor(h / 24)}d ${h % 24}h left`;
  return `${h}h left`;
};

interface ContextualMatch {
  matches: string[];
  gaps: string[];
}

const evaluateContextualMatch = (result: MatchResult, jd: JD | undefined): ContextualMatch => {
  const matches: string[] = [];
  const gaps: string[] = [];

  const candidateCompanyTypes = result.company_types || [];
  const candidateTeamSize = result.avg_team_size || 'Unknown';
  const candidateRoleType = result.role_type || 'Unknown';

  const jdCompanyTypes = result.preferred_company_type || [];
  const jdTeamSize = result.preferred_team_size || 'Any';
  const jdRoleType = result.jd_role_type || 'Any';

  if (jdCompanyTypes && jdCompanyTypes.length > 0 && !jdCompanyTypes.includes('Any')) {
    const matchingTypes = candidateCompanyTypes.filter((ct: string) => jdCompanyTypes.includes(ct));
    if (matchingTypes.length > 0) {
      matchingTypes.forEach((type: string) => { matches.push(`Worked in ${type}`); });
    } else if (candidateCompanyTypes.length > 0) {
      const nonMatching = jdCompanyTypes.filter((t: string) => !candidateCompanyTypes.includes(t));
      nonMatching.forEach((type: string) => { gaps.push(`No ${type} experience`); });
    } else {
      gaps.push('Company type unknown');
    }
  }

  if (jdTeamSize && jdTeamSize !== 'Any') {
    if (candidateTeamSize === jdTeamSize) {
      matches.push(`Team size matches: ${candidateTeamSize}`);
    } else if (candidateTeamSize !== 'Unknown') {
      gaps.push(`Team size mismatch: candidate ${candidateTeamSize}, JD needs ${jdTeamSize}`);
    } else {
      gaps.push('Team size unknown');
    }
  }

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
  // Review tab state
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

  // Pipeline tab state
  const [activeTab, setActiveTab] = useState<'review' | 'pipeline'>('review');
  const [pipelineRecords, setPipelineRecords] = useState<PipelineRecord[]>([]);
  const [breaches, setBreaches] = useState<PipelineBreach[]>([]);
  const [extensionForms, setExtensionForms] = useState<Record<string, { open: boolean; hours: number; reason: string }>>({});
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [isManager, setIsManager] = useState(false);

  // Assessment state
  const [assessments, setAssessments] = useState<Record<string, { status: string; score: number | null; assessment_id: string }>>({});
  const [sendingAssessment, setSendingAssessment] = useState<string | null>(null);

  // Interview scheduling modal
  const [interviewModal, setInterviewModal] = useState<{ candidateId: string; nextStage: string } | null>(null);
  const [interviewForm, setInterviewForm] = useState({
    date: '', time: '', mode: 'online' as 'online' | 'in-person',
    meeting_link: '', location: '', duration: '1hour', notes: '',
  });
  const [interviewSubmitting, setInterviewSubmitting] = useState(false);

  // Prevents stale results from a superseded JD click arriving after a newer one.
  const pendingJdRef = useRef<string>('');

  useEffect(() => {
    const roles: string[] = (keycloak.tokenParsed as any)?.realm_access?.roles ?? [];
    setIsManager(roles.some(r => ['manager', 'admin'].includes(r)));
  }, []);

  useEffect(() => {
    const init = async () => {
      try {
        const [jdRes, candRes] = await Promise.all([
          fetch(`${API}/jd/`, { headers: getAuthHeaders() }),
          fetch(`${API}/candidates/`, { headers: getAuthHeaders() }),
        ]);
        const jdData = jdRes.ok ? await jdRes.json() : [];
        const candData = candRes.ok ? await candRes.json() : [];
        setJds(Array.isArray(jdData) ? jdData : []);
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

  useEffect(() => {
    if (activeTab === 'pipeline' && selectedJdId) {
      loadPipeline(selectedJdId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedJdId]);

  const loadJd = async (jdId: string) => {
    pendingJdRef.current = jdId;
    setSelectedJdId(jdId);
    setResults([]);
    setLocalActions({});
    setExpandedIds(new Set());
    setRejectingId(null);
    setError(null);
    setPipelineRecords([]);
    setPipelineError(null);
  };

  const loadPipeline = async (jdId: string) => {
    const roles: string[] = (keycloak.tokenParsed as any)?.realm_access?.roles ?? [];
    const managerRole = roles.some(r => ['manager', 'admin'].includes(r));
    setPipelineLoading(true);
    setPipelineError(null);
    try {
      const res = await fetch(`${API}/pipeline/${jdId}`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PipelineRecord[] = await res.json();
      setPipelineRecords(data);
      setExtensionForms({});
      if (managerRole) {
        const bRes = await fetch(`${API}/pipeline/breaches`, { headers: getAuthHeaders() });
        if (bRes.ok) setBreaches(await bRes.json());
      }
    } catch (e: any) {
      setPipelineError('Failed to load pipeline: ' + e.message);
    } finally {
      setPipelineLoading(false);
    }
  };

  const advanceStage = async (jdId: string, candidateId: string, body: object = {}) => {
    try {
      const res = await fetch(`${API}/pipeline/advance/${jdId}/${candidateId}`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadPipeline(jdId);
    } catch (e: any) {
      setPipelineError('Advance failed: ' + e.message);
    }
  };

  const handleAdvanceClick = (jdId: string, record: PipelineRecord) => {
    const stageIdx = STAGE_ORDER.indexOf(record.current_stage);
    const nextStage = STAGE_ORDER[stageIdx + 1];
    if (nextStage === 'interview_1' || nextStage === 'interview_final') {
      setInterviewForm({ date: '', time: '', mode: 'online', meeting_link: '', location: '', duration: '1hour', notes: '' });
      setInterviewModal({ candidateId: record.candidate_id, nextStage });
    } else {
      advanceStage(jdId, record.candidate_id);
    }
  };

  const submitInterviewAdvance = async () => {
    if (!interviewModal) return;
    setInterviewSubmitting(true);
    try {
      await advanceStage(selectedJdId, interviewModal.candidateId, {
        next_stage: interviewModal.nextStage,
        interview_details: {
          date: interviewForm.date,
          time: interviewForm.time,
          mode: interviewForm.mode,
          meeting_link: interviewForm.mode === 'online' ? interviewForm.meeting_link : undefined,
          location: interviewForm.mode === 'in-person' ? interviewForm.location : undefined,
          duration: interviewForm.duration,
          notes: interviewForm.notes || undefined,
        },
      });
      setInterviewModal(null);
    } finally {
      setInterviewSubmitting(false);
    }
  };

  const interviewFormValid =
    !!interviewForm.date &&
    !!interviewForm.time &&
    (interviewForm.mode === 'online' ? !!interviewForm.meeting_link : !!interviewForm.location);

  const requestExtension = async (jdId: string, candidateId: string) => {
    const form = extensionForms[candidateId];
    if (!form?.reason?.trim()) return;
    try {
      const res = await fetch(`${API}/pipeline/extension-request`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jd_id: jdId,
          candidate_id: candidateId,
          additional_hours: form.hours,
          reason: form.reason,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setExtensionForms(prev => ({ ...prev, [candidateId]: { ...prev[candidateId], open: false } }));
      await loadPipeline(jdId);
    } catch (e: any) {
      setPipelineError('Extension request failed: ' + e.message);
    }
  };

  const decideExtension = async (jdId: string, candidateId: string, approve: boolean) => {
    try {
      const res = await fetch(`${API}/pipeline/extension-approve`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd_id: jdId, candidate_id: candidateId, approve }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadPipeline(jdId);
    } catch (e: any) {
      setPipelineError('Decision failed: ' + e.message);
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
      fetch(`${API}/feedback/generate/${candidateId}/${selectedJdId}`, { method: 'POST', headers: getAuthHeaders() });
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

          {expanded && (
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
                    <span className="text-[10px] text-slate-500">—</span>
                  )}
                </div>
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
                    <span className="text-[10px] text-slate-500">—</span>
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

  const renderPipelineTab = () => {
    if (pipelineLoading) {
      return <p className="text-slate-400 text-sm py-12 text-center">Loading pipeline...</p>;
    }
    if (pipelineRecords.length === 0) {
      return (
        <div className="text-center py-12 text-slate-500 text-sm">
          No candidates in the pipeline yet. Shortlist candidates from the Review tab.
        </div>
      );
    }

    const jdBreaches = breaches.filter(b => b.jd_id === selectedJdId);

    return (
      <div className="space-y-6">
        {/* Manager: breach list */}
        {isManager && jdBreaches.length > 0 && (
          <section>
            <p className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-3">Overdue Stages</p>
            <div className="space-y-2">
              {jdBreaches.map(b => (
                <div
                  key={`${b.candidate_id}-breach`}
                  className="flex items-center justify-between px-4 py-3 bg-red-900/10 border border-red-500/20 rounded-xl"
                >
                  <div className="flex items-center space-x-3">
                    <AlertTriangle size={14} className="text-red-400 shrink-0" />
                    <div>
                      <p className="text-xs font-bold text-white">{candidateNames[b.candidate_id] || b.candidate_id}</p>
                      <p className="text-[10px] text-red-300">
                        {STAGE_LABELS[b.stage] || b.stage} — overdue since {new Date(b.due_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  {b.escalated && (
                    <span className="text-[9px] font-bold text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20">
                      Escalated
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Pipeline cards */}
        <div className="space-y-3">
          {pipelineRecords.map(record => {
            const currentStageEntry = record.stages.find(s => s.name === record.current_stage);
            if (!currentStageEntry) return null;

            const { pct, barColor, textColor } = getSlaProgress(currentStageEntry);
            const timeLabel = formatTimeRemaining(currentStageEntry);
            const stageIdx = STAGE_ORDER.indexOf(record.current_stage);
            const extForm = extensionForms[record.candidate_id];
            const ext = currentStageEntry.extension;
            const hasPendingExt = !!(ext && !ext.approved_at);
            const isLastStage = record.current_stage === STAGE_ORDER[STAGE_ORDER.length - 1];

            return (
              <div key={record.candidate_id} className="bg-slate-800/40 border border-slate-700/50 rounded-2xl overflow-hidden">
                <div className="px-5 py-4 space-y-3">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold text-white">
                        {candidateNames[record.candidate_id] || record.candidate_id}
                      </p>
                      <p className="text-[11px] text-slate-400">{record.candidate_id}</p>
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-blue-500/20 text-blue-400 shrink-0">
                      {STAGE_LABELS[record.current_stage] || record.current_stage}
                    </span>
                  </div>

                  {/* Stage progression dots */}
                  <div className="flex items-center">
                    {STAGE_ORDER.map((s, i) => (
                      <React.Fragment key={s}>
                        <div className={`h-2 w-2 rounded-full shrink-0 ${
                          i < stageIdx ? 'bg-emerald-500' : i === stageIdx ? 'bg-blue-400' : 'bg-slate-700'
                        }`} />
                        {i < STAGE_ORDER.length - 1 && (
                          <div className={`h-px flex-1 ${i < stageIdx ? 'bg-emerald-500/50' : 'bg-slate-700'}`} />
                        )}
                      </React.Fragment>
                    ))}
                  </div>

                  {/* SLA progress bar */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">SLA</p>
                      <span className={`text-[10px] font-bold ${textColor}`}>{timeLabel}</span>
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${barColor}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    {ext?.approved && (
                      <p className="text-[9px] text-blue-400">Extended by {ext.additional_hours}h</p>
                    )}
                    {hasPendingExt && (
                      <p className="text-[9px] text-yellow-400">
                        Extension pending approval (+{ext!.additional_hours}h)
                      </p>
                    )}
                  </div>

                  {/* Manager: approve / deny extension */}
                  {isManager && hasPendingExt && (
                    <div className="flex items-center space-x-2 pt-1 border-t border-slate-700/50">
                      <p className="text-[10px] text-slate-300 flex-1 truncate">
                        Extension: "{ext!.reason}"
                      </p>
                      <button
                        onClick={() => decideExtension(selectedJdId, record.candidate_id, true)}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold rounded-lg transition-colors"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => decideExtension(selectedJdId, record.candidate_id, false)}
                        className="px-3 py-1.5 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-[10px] font-bold rounded-lg border border-red-500/20 transition-colors"
                      >
                        Deny
                      </button>
                    </div>
                  )}

                  {/* Extension request form */}
                  {extForm?.open && (
                    <div className="space-y-2 border-t border-slate-700/50 pt-3">
                      <div className="flex items-center space-x-2">
                        <select
                          value={extForm.hours}
                          onChange={e => setExtensionForms(prev => ({
                            ...prev,
                            [record.candidate_id]: { ...prev[record.candidate_id], hours: Number(e.target.value) },
                          }))}
                          className="bg-slate-900 border border-slate-600 text-white text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
                        >
                          {[24, 48, 72, 96, 120].map(h => <option key={h} value={h}>{h}h</option>)}
                        </select>
                        <input
                          placeholder="Reason for extension"
                          value={extForm.reason}
                          onChange={e => setExtensionForms(prev => ({
                            ...prev,
                            [record.candidate_id]: { ...prev[record.candidate_id], reason: e.target.value },
                          }))}
                          className="flex-1 bg-slate-900 border border-slate-600 text-white text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 placeholder-slate-500"
                        />
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => requestExtension(selectedJdId, record.candidate_id)}
                          disabled={!extForm.reason.trim()}
                          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-bold rounded-lg transition-colors"
                        >
                          Submit
                        </button>
                        <button
                          onClick={() => setExtensionForms(prev => ({
                            ...prev,
                            [record.candidate_id]: { ...prev[record.candidate_id], open: false },
                          }))}
                          className="px-3 py-2 text-slate-400 hover:text-white text-xs rounded-lg transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Action footer */}
                {!extForm?.open && (
                  <div className="border-t border-slate-700/30 px-5 py-3 flex items-center space-x-2">
                    {isLastStage ? (
                      <span className="text-xs font-bold text-emerald-400 flex items-center space-x-1.5">
                        <CheckCircle size={12} />
                        <span>Placement Complete</span>
                      </span>
                    ) : (
                      <>
                        <button
                          onClick={() => handleAdvanceClick(selectedJdId, record)}
                          className="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-colors"
                        >
                          <ArrowRight size={12} />
                          <span>Advance Stage</span>
                        </button>
                        {!hasPendingExt && (
                          <button
                            onClick={() => setExtensionForms(prev => ({
                              ...prev,
                              [record.candidate_id]: { open: true, hours: 24, reason: '' },
                            }))}
                            className="flex items-center space-x-1.5 px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg border border-slate-600/50 transition-colors"
                          >
                            <Clock size={12} />
                            <span>Request Extension</span>
                          </button>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
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

      {(error || pipelineError) && (
        <div className="flex items-center space-x-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl">
          <XCircle size={14} className="text-red-400 shrink-0" />
          <span className="text-xs text-red-300">{error || pipelineError}</span>
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

      {selectedJdId && (
        <>
          {/* Tab switcher */}
          <div className="flex border-b border-slate-700/50">
            <button
              onClick={() => setActiveTab('review')}
              className={`px-4 py-2.5 text-xs font-bold uppercase tracking-widest transition-colors border-b-2 -mb-px ${
                activeTab === 'review'
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}
            >
              Review
            </button>
            <button
              onClick={() => setActiveTab('pipeline')}
              className={`px-4 py-2.5 text-xs font-bold uppercase tracking-widest transition-colors border-b-2 -mb-px ${
                activeTab === 'pipeline'
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}
            >
              Pipeline
            </button>
          </div>

          {activeTab === 'review' && (
            <>
              {/* Batch Review */}
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
                    Run matching first to see candidates — go to the Matching Engine page and click Run Matching for this JD.
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

              {/* Pipeline Stats */}
              {results.length > 0 && (
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
            </>
          )}

          {activeTab === 'pipeline' && renderPipelineTab()}
        </>
      )}

      {/* Interview scheduling modal */}
      {interviewModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-600/20 rounded-xl">
                  <Calendar className="text-blue-400" size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Schedule Interview</h3>
                  <p className="text-xs text-slate-400">
                    {STAGE_LABELS[interviewModal.nextStage]} — {candidateNames[interviewModal.candidateId] || interviewModal.candidateId}
                  </p>
                </div>
              </div>
              <button onClick={() => setInterviewModal(null)} className="text-slate-500 hover:text-white transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Date <span className="text-red-400">*</span></label>
                  <input
                    type="date"
                    value={interviewForm.date}
                    onChange={e => setInterviewForm(f => ({ ...f, date: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Time <span className="text-red-400">*</span></label>
                  <input
                    type="time"
                    value={interviewForm.time}
                    onChange={e => setInterviewForm(f => ({ ...f, time: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Mode <span className="text-red-400">*</span></label>
                  <select
                    value={interviewForm.mode}
                    onChange={e => setInterviewForm(f => ({ ...f, mode: e.target.value as 'online' | 'in-person' }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="online">Online</option>
                    <option value="in-person">In-person</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Duration</label>
                  <select
                    value={interviewForm.duration}
                    onChange={e => setInterviewForm(f => ({ ...f, duration: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="30min">30 minutes</option>
                    <option value="45min">45 minutes</option>
                    <option value="1hour">1 hour</option>
                  </select>
                </div>
              </div>

              {interviewForm.mode === 'online' ? (
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Meeting Link <span className="text-red-400">*</span></label>
                  <input
                    type="url"
                    placeholder="https://meet.google.com/..."
                    value={interviewForm.meeting_link}
                    onChange={e => setInterviewForm(f => ({ ...f, meeting_link: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Location <span className="text-red-400">*</span></label>
                  <input
                    type="text"
                    placeholder="Office address or room"
                    value={interviewForm.location}
                    onChange={e => setInterviewForm(f => ({ ...f, location: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">Notes for candidate <span className="text-slate-500">(optional)</span></label>
                <textarea
                  placeholder="Any preparation tips, documents to bring, etc."
                  value={interviewForm.notes}
                  onChange={e => setInterviewForm(f => ({ ...f, notes: e.target.value }))}
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={submitInterviewAdvance}
                disabled={!interviewFormValid || interviewSubmitting}
                className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/40 text-white font-semibold text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {interviewSubmitting ? 'Scheduling...' : 'Confirm & Advance'}
              </button>
              <button
                onClick={() => setInterviewModal(null)}
                disabled={interviewSubmitting}
                className="flex-1 py-2.5 bg-slate-700/50 hover:bg-slate-700 text-slate-300 font-semibold text-sm rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RecruiterDashboard;
