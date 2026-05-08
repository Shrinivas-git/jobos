import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ClipboardList, CheckCircle, XCircle, ChevronDown, ChevronUp, Users,
  Clock, AlertTriangle, ArrowRight, Calendar, X,
} from 'lucide-react';
import keycloak from '../keycloak';
import {
  API, getAuthHeaders, JD, MatchResult, CandidateLookup,
  PipelineRecord, PipelineBreach, PipelineStageEntry, CandidateOfferResponse,
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
  interview_1: 'Interview Round 1',
  interview_final: 'Final Interview',
  offer: 'Offer',
  joined: 'Joined',
};
const STAGE_ORDER = ['shortlist', 'interview_1', 'interview_final', 'offer', 'joined'];

const getStagLabel = (stage: string): string => {
  if (STAGE_LABELS[stage]) return STAGE_LABELS[stage];
  const im = stage.match(/^interview_(\d+)$/);
  if (im) return `Interview Round ${im[1]}`;
  const am = stage.match(/^assessment_(\d+)$/);
  if (am) return `Assessment Round ${am[1]}`;
  return stage.replace(/_/g, ' ');
};

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
  const [expandedFlagIds, setExpandedFlagIds] = useState<Set<string>>(new Set());
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

  // Send to client state
  const [clientSubmission, setClientSubmission] = useState<{ sent: boolean; sent_at?: string; client_email?: string; candidates_sent?: number } | null>(null);
  const [sendingToClient, setSendingToClient] = useState(false);
  const [clientSendError, setClientSendError] = useState<string | null>(null);

  // Interview outcome state
  const [interviewOutcomeLoading, setInterviewOutcomeLoading] = useState<string | null>(null);
  const [outcomeModal, setOutcomeModal] = useState<{ candidateId: string; currentStage: string } | null>(null);
  const [outcomeNextStep, setOutcomeNextStep] = useState<'next_round' | 'offer'>('next_round');
  const [outcomeForm, setOutcomeForm] = useState({
    date: '', time: '', mode: 'online' as 'online' | 'in-person',
    meeting_link: '', location: '', duration: '1hour', notes: '',
  });

  // Configure pipeline modal
  const [pipelineConfigModal, setPipelineConfigModal] = useState(false);
  const [pipelineConfigForm, setPipelineConfigForm] = useState({ assessment_rounds: 0, interview_rounds: 1 });
  const [pipelineConfigSaving, setPipelineConfigSaving] = useState(false);

  // Candidate response message modal
  const [responseMessageModal, setResponseMessageModal] = useState<{ name: string; message: string } | null>(null);

  // Give Offer modal
  const [offerModal, setOfferModal] = useState<{ candidateId: string } | null>(null);
  const [offerForm, setOfferForm] = useState({ joining_date: '', work_location: '' });
  const [offerSubmitting, setOfferSubmitting] = useState(false);

  // Stage type picker modal (Assessment vs Interview)
  const [stageTypeModal, setStageTypeModal] = useState<{ jdId: string; candidateId: string; candidateName: string } | null>(null);

  // Assessment scheduling modal
  const [assessmentModal, setAssessmentModal] = useState<{ jdId: string; candidateId: string } | null>(null);
  const [assessmentForm, setAssessmentForm] = useState({ date: '', time: '', mode: 'online' as 'online' | 'in-person', platform: '', location: '', duration: '1hour', notes: '' });
  const [assessmentSubmitting, setAssessmentSubmitting] = useState(false);

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
    setClientSubmission(null);
    setClientSendError(null);

    try {
      const [matchRes, subRes] = await Promise.all([
        fetch(`${API}/matching/results/${jdId}`, { headers: getAuthHeaders() }),
        fetch(`${API}/pipeline/submission-status/${jdId}`, { headers: getAuthHeaders() }),
      ]);
      if (pendingJdRef.current !== jdId) return;
      if (matchRes.ok) {
        const data = await matchRes.json();
        setResults(Array.isArray(data) ? data : []);
      }
      if (subRes.ok) setClientSubmission(await subRes.json());
    } catch {
      // silently ignore — empty results state already set above
    }
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
      const asmtRes = await fetch(`${API}/assessments/by-jd/${jdId}`, { headers: getAuthHeaders() });
      if (asmtRes.ok) setAssessments(await asmtRes.json());
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
    const order = record.planned_stages && record.planned_stages.length > 0 ? record.planned_stages : STAGE_ORDER;
    const stageIdx = order.indexOf(record.current_stage);
    const nextStage = order[stageIdx + 1];
    if (record.current_stage === 'shortlist') {
      // Ask recruiter: assessment or interview?
      setStageTypeModal({ jdId, candidateId: record.candidate_id, candidateName: candidateNames[record.candidate_id] || record.candidate_id });
    } else if (nextStage && nextStage.startsWith('interview_')) {
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

  const submitGiveOffer = async () => {
    if (!offerModal || !offerForm.joining_date || !offerForm.work_location) return;
    setOfferSubmitting(true);
    try {
      const r = await fetch(`${API}/pipeline/give-offer/${selectedJdId}/${offerModal.candidateId}`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(offerForm),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setOfferModal(null);
      setOfferForm({ joining_date: '', work_location: '' });
      await loadPipeline(selectedJdId);
    } catch (e: any) {
      setPipelineError('Give offer failed: ' + e.message);
    } finally {
      setOfferSubmitting(false);
    }
  };

  const savePipelineConfig = async () => {
    if (!selectedJdId) return;
    setPipelineConfigSaving(true);
    try {
      const r = await fetch(`${API}/jd/${selectedJdId}/pipeline-config`, {
        method: 'PATCH',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(pipelineConfigForm),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setPipelineConfigModal(false);
    } catch (e: any) {
      setPipelineError('Failed to save pipeline config: ' + e.message);
    } finally {
      setPipelineConfigSaving(false);
    }
  };

  const interviewFormValid =
    !!interviewForm.date &&
    !!interviewForm.time &&
    (interviewForm.mode === 'online' ? !!interviewForm.meeting_link : !!interviewForm.location);

  const submitSelectedOutcome = async () => {
    if (!outcomeModal || !selectedJdId) return;
    const { candidateId } = outcomeModal;
    if (outcomeNextStep === 'next_round') {
      if (!outcomeForm.date || !outcomeForm.time) return;
    }
    setInterviewOutcomeLoading(candidateId);
    try {
      const body: any = { outcome: 'selected', next_step: outcomeNextStep };
      if (outcomeNextStep === 'next_round') {
        body.interview_details = {
          date: outcomeForm.date,
          time: outcomeForm.time,
          mode: outcomeForm.mode,
          meeting_link: outcomeForm.meeting_link || null,
          location: outcomeForm.location || null,
          duration: outcomeForm.duration,
          notes: outcomeForm.notes || null,
        };
      }
      const r = await fetch(`${API}/pipeline/interview-outcome/${selectedJdId}/${candidateId}`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        setOutcomeModal(null);
        setOutcomeForm({ date: '', time: '', mode: 'online', meeting_link: '', location: '', duration: '1hour', notes: '' });
        await loadPipeline(selectedJdId);
      }
    } finally {
      setInterviewOutcomeLoading(null);
    }
  };

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

  const handleSendToClient = async () => {
    if (!selectedJdId) return;
    setSendingToClient(true);
    setClientSendError(null);
    try {
      const res = await fetch(`${API}/pipeline/send-to-client/${selectedJdId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      setClientSubmission({ sent: true, sent_at: data.sent_at, client_email: data.client_email, candidates_sent: data.candidates_sent });
    } catch (e: any) {
      setClientSendError(e.message);
    } finally {
      setSendingToClient(false);
    }
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

          {/* Intelligence summary badges — always visible */}
          {(result.role_level_detected || result.tool_currency || result.availability_signal) && (
            <div className="flex flex-wrap items-center gap-1.5">
              {result.role_level_detected && result.role_level_match && result.role_level_match !== 'Unknown' && (
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                  result.role_level_match === 'Match'
                    ? 'bg-emerald-500/15 border-emerald-500/20 text-emerald-400'
                    : result.role_level_match === 'Over-qualified'
                      ? 'bg-yellow-500/15 border-yellow-500/20 text-yellow-400'
                      : 'bg-red-500/15 border-red-500/20 text-red-400'
                }`}>
                  {result.role_level_detected} · {result.role_level_match}
                </span>
              )}
              {result.tool_currency && result.tool_currency !== 'None' && result.tool_currency !== 'Unknown' && (
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${
                  result.tool_currency === 'Current'
                    ? 'bg-blue-500/15 border-blue-500/20 text-blue-400'
                    : 'bg-slate-600/30 border-slate-500/20 text-slate-400'
                }`}>
                  Tools: {result.tool_currency}
                </span>
              )}
              {result.cv_narrative_style && result.cv_narrative_style !== 'Unknown' && (
                <span className="text-[9px] px-1.5 py-0.5 rounded border bg-slate-700/30 border-slate-600/20 text-slate-500">
                  {result.cv_narrative_style}
                </span>
              )}
              {result.availability_signal && result.availability_signal !== 'Unknown' && (
                <span className="text-[9px] italic text-slate-500">
                  Avail: {result.availability_signal}
                </span>
              )}
            </div>
          )}

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

          {expanded && (result as any).scoring_factors?.length > 0 && (
            <div className="border-t border-slate-700/50 pt-3 space-y-2">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Scoring Factors</p>
              <div className="flex flex-wrap gap-2">
                {(result as any).scoring_factors.map((sf: { factor: string; impact: string; reason: string }, i: number) => {
                  const negative = sf.impact.startsWith('-') && sf.impact !== '-0';
                  return (
                    <div
                      key={i}
                      className={`px-2.5 py-1.5 rounded-lg border ${
                        negative
                          ? 'bg-red-500/10 border-red-500/20'
                          : 'bg-emerald-500/10 border-emerald-500/20'
                      }`}
                    >
                      <div className={`flex items-center space-x-1.5 text-[10px] font-bold ${negative ? 'text-red-400' : 'text-emerald-400'}`}>
                        <span>{sf.factor}</span>
                        <span className="font-black opacity-80">{sf.impact}</span>
                      </div>
                      <p className={`text-[9px] mt-0.5 font-normal leading-snug ${negative ? 'text-red-300/70' : 'text-emerald-300/70'}`}>
                        {sf.reason}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Rare assets — purple badges */}
          {expanded && result.rare_assets && result.rare_assets.length > 0 && (
            <div className="border-t border-slate-700/50 pt-3 space-y-2">
              <p className="text-[10px] font-bold text-purple-400 uppercase tracking-widest">Rare Assets</p>
              <div className="flex flex-wrap gap-1.5">
                {result.rare_assets.map((asset, i) => (
                  <span key={i} className="text-[10px] px-2 py-1 rounded-lg border bg-purple-500/10 border-purple-500/20 text-purple-300">
                    {asset}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Interview flags — collapsible */}
          {expanded && result.interview_flags && result.interview_flags.length > 0 && (
            <div className="border-t border-slate-700/50 pt-3 space-y-2">
              <button
                onClick={() => setExpandedFlagIds(prev => {
                  const next = new Set(prev);
                  next.has(result.candidate_id) ? next.delete(result.candidate_id) : next.add(result.candidate_id);
                  return next;
                })}
                className="flex items-center space-x-1 text-[10px] font-bold text-amber-500 hover:text-amber-400 uppercase tracking-widest transition-colors"
              >
                <span>Probe in Interview ({result.interview_flags.length})</span>
                {expandedFlagIds.has(result.candidate_id) ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
              {expandedFlagIds.has(result.candidate_id) && (
                <ul className="space-y-1">
                  {result.interview_flags.map((flag, i) => (
                    <li key={i} className="flex items-start space-x-1.5 text-[10px] text-amber-300/80">
                      <span className="shrink-0 mt-0.5 text-amber-500">›</span>
                      <span>{flag}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Unverified claims — amber section */}
          {expanded && result.self_reported_unverified && result.self_reported_unverified.length > 0 && (
            <div className="border-t border-slate-700/50 pt-3 space-y-2">
              <p className="text-[10px] font-bold text-amber-400 uppercase tracking-widest">Unverified Claims</p>
              <ul className="space-y-1">
                {result.self_reported_unverified.map((claim, i) => (
                  <li key={i} className="flex items-start space-x-1.5 text-[10px] text-amber-300/70">
                    <span className="shrink-0 mt-0.5 text-amber-500">!</span>
                    <span>{claim}</span>
                  </li>
                ))}
              </ul>
            </div>
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

        {/* Configure Pipeline button */}
        <div className="flex justify-end">
          <button
            onClick={() => {
              const selJd = jds.find(j => j.jd_id === selectedJdId);
              if (selJd?.pipeline_config) {
                setPipelineConfigForm({ assessment_rounds: selJd.pipeline_config.assessment_rounds, interview_rounds: selJd.pipeline_config.interview_rounds });
              } else {
                setPipelineConfigForm({ assessment_rounds: 0, interview_rounds: 1 });
              }
              setPipelineConfigModal(true);
            }}
            className="flex items-center space-x-1.5 px-4 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg border border-slate-600/50 transition-colors"
          >
            <Calendar size={12} />
            <span>Configure Pipeline Rounds</span>
          </button>
        </div>

        {/* Pipeline cards */}
        <div className="space-y-3">
          {pipelineRecords.filter(r => r.current_stage !== 'rejected').map(record => {
            const currentStageEntry = record.stages.find(s => s.name === record.current_stage);
            if (!currentStageEntry) return null;

            const { pct, barColor, textColor } = getSlaProgress(currentStageEntry);
            const timeLabel = formatTimeRemaining(currentStageEntry);
            // Use candidate's own planned_stages if available, else fall back to global
            const cardStageOrder = record.planned_stages && record.planned_stages.length > 0
              ? record.planned_stages
              : STAGE_ORDER;
            const stageIdx = cardStageOrder.indexOf(record.current_stage);
            const extForm = extensionForms[record.candidate_id];
            const ext = currentStageEntry.extension;
            const hasPendingExt = !!(ext && !ext.approved_at);
            const isLastStage = record.current_stage === cardStageOrder[cardStageOrder.length - 1];

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
                    <div className="flex items-center gap-1.5 shrink-0">
                      {record.on_hold && (
                        <span className="text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-yellow-500/20 text-yellow-400">
                          On Hold
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Current stage label */}
                  <div className="mb-1.5">
                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{getStagLabel(record.current_stage)}</span>
                  </div>

                  {/* Stage progression dots */}
                  <div className="flex items-center">
                    {cardStageOrder.map((s, i) => (
                      <React.Fragment key={s}>
                        <div
                          className={`h-2 w-2 rounded-full shrink-0 ${
                            i < stageIdx ? 'bg-emerald-500' : i === stageIdx ? 'bg-blue-400' : 'bg-slate-700'
                          }`}
                          title={getStagLabel(s)}
                        />
                        {i < cardStageOrder.length - 1 && (
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
                        {/* Assessment stage — Pass / Fail */}
                        {record.current_stage.startsWith('assessment_') ? (
                          <>
                            <button
                              onClick={() => advanceStage(selectedJdId, record.candidate_id)}
                              className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-colors"
                            >
                              <CheckCircle size={12} />
                              <span>Pass</span>
                            </button>
                            <button
                              onClick={async () => {
                                const r = await fetch(`${API}/pipeline/interview-outcome/${selectedJdId}/${record.candidate_id}`, {
                                  method: 'POST',
                                  headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ outcome: 'rejected' }),
                                });
                                if (r.ok) await loadPipeline(selectedJdId);
                              }}
                              className="flex items-center space-x-1.5 px-4 py-2 bg-red-600/80 hover:bg-red-500 text-white text-xs font-bold rounded-lg transition-colors"
                            >
                              <XCircle size={12} />
                              <span>Fail</span>
                            </button>
                          </>
                        ) : record.current_stage.startsWith('interview_') ? (
                          <>
                            <button
                              onClick={() => {
                                setOutcomeNextStep('next_round');
                                setOutcomeForm({ date: '', time: '', mode: 'online', meeting_link: '', location: '', duration: '1hour', notes: '' });
                                setOutcomeModal({ candidateId: record.candidate_id, currentStage: record.current_stage });
                              }}
                              className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-colors"
                            >
                              <CheckCircle size={12} />
                              <span>Selected</span>
                            </button>
                            <button
                              disabled={interviewOutcomeLoading === record.candidate_id}
                              onClick={async () => {
                                setInterviewOutcomeLoading(record.candidate_id);
                                try {
                                  const r = await fetch(`${API}/pipeline/interview-outcome/${selectedJdId}/${record.candidate_id}`, {
                                    method: 'POST',
                                    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ outcome: 'on_hold' }),
                                  });
                                  if (r.ok) await loadPipeline(selectedJdId);
                                } finally {
                                  setInterviewOutcomeLoading(null);
                                }
                              }}
                              className="flex items-center space-x-1.5 px-4 py-2 bg-yellow-600/80 hover:bg-yellow-500 disabled:opacity-40 text-white text-xs font-bold rounded-lg transition-colors"
                            >
                              <Clock size={12} />
                              <span>On Hold</span>
                            </button>
                            <button
                              disabled={interviewOutcomeLoading === record.candidate_id}
                              onClick={async () => {
                                setInterviewOutcomeLoading(record.candidate_id);
                                try {
                                  const r = await fetch(`${API}/pipeline/interview-outcome/${selectedJdId}/${record.candidate_id}`, {
                                    method: 'POST',
                                    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ outcome: 'rejected' }),
                                  });
                                  if (r.ok) await loadPipeline(selectedJdId);
                                } finally {
                                  setInterviewOutcomeLoading(null);
                                }
                              }}
                              className="flex items-center space-x-1.5 px-4 py-2 bg-red-600/80 hover:bg-red-500 disabled:opacity-40 text-white text-xs font-bold rounded-lg transition-colors"
                            >
                              <XCircle size={12} />
                              <span>Rejected</span>
                            </button>
                          </>
                        ) : record.current_stage === 'offer' ? (() => {
                          const offerStage = record.stages.find(s => s.name === 'offer');
                          const joiningDateSet = !!(offerStage as any)?.joining_date;
                          const candidateResp = record.candidate_response as CandidateOfferResponse | null | undefined;

                          if (!joiningDateSet) {
                            // Recruiter hasn't sent the offer yet
                            return (
                              <button
                                onClick={() => {
                                  setOfferForm({ joining_date: '', work_location: '' });
                                  setOfferModal({ candidateId: record.candidate_id });
                                }}
                                className="flex items-center space-x-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold rounded-lg transition-colors"
                              >
                                <CheckCircle size={12} />
                                <span>Give Offer</span>
                              </button>
                            );
                          }

                          if (!candidateResp) {
                            // Offer sent, waiting for candidate
                            return (
                              <span className="text-[10px] font-bold text-slate-400 italic px-2">
                                Awaiting candidate response…
                              </span>
                            );
                          }

                          if (candidateResp.response === 'accept') {
                            return (
                              <>
                                <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20">
                                  Candidate Agreed ✓
                                </span>
                                <button
                                  onClick={async () => {
                                    const r = await fetch(`${API}/pipeline/confirm-joining/${selectedJdId}/${record.candidate_id}`, {
                                      method: 'POST', headers: getAuthHeaders(),
                                    });
                                    if (r.ok) await loadPipeline(selectedJdId);
                                    else setPipelineError('Confirm joining failed');
                                  }}
                                  className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-colors"
                                >
                                  <CheckCircle size={12} />
                                  <span>Confirm Joining</span>
                                </button>
                                <button
                                  onClick={async () => {
                                    const r = await fetch(`${API}/pipeline/reject-from-offer/${selectedJdId}/${record.candidate_id}`, {
                                      method: 'POST', headers: getAuthHeaders(),
                                    });
                                    if (r.ok) await loadPipeline(selectedJdId);
                                  }}
                                  className="flex items-center space-x-1.5 px-3 py-2 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-xs font-bold rounded-lg border border-red-500/20 transition-colors"
                                >
                                  <XCircle size={12} />
                                  <span>Reject</span>
                                </button>
                              </>
                            );
                          }

                          // Candidate postponed / not interested
                          return (
                            <>
                              <button
                                onClick={() => setResponseMessageModal({
                                  name: candidateNames[record.candidate_id] || record.candidate_id,
                                  message: candidateResp.reason || 'Postpone / Not interested (no note left)',
                                })}
                                className="text-[10px] font-bold text-yellow-400 bg-yellow-500/10 px-2 py-1 rounded border border-yellow-500/20 max-w-[160px] truncate hover:bg-yellow-500/20 transition-colors text-left"
                              >
                                {candidateResp.reason ? `"${candidateResp.reason}"` : 'Postpone / Not interested'}
                              </button>
                              <button
                                onClick={() => {
                                  setOfferForm({ joining_date: '', work_location: '' });
                                  setOfferModal({ candidateId: record.candidate_id });
                                }}
                                className="flex items-center space-x-1.5 px-3 py-2 bg-violet-600/20 hover:bg-violet-600/40 text-violet-400 text-xs font-bold rounded-lg border border-violet-500/20 transition-colors"
                              >
                                <ArrowRight size={12} />
                                <span>Update Date</span>
                              </button>
                              <button
                                onClick={async () => {
                                  const r = await fetch(`${API}/pipeline/reject-from-offer/${selectedJdId}/${record.candidate_id}`, {
                                    method: 'POST', headers: getAuthHeaders(),
                                  });
                                  if (r.ok) await loadPipeline(selectedJdId);
                                }}
                                className="flex items-center space-x-1.5 px-3 py-2 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-xs font-bold rounded-lg border border-red-500/20 transition-colors"
                              >
                                <XCircle size={12} />
                                <span>Reject</span>
                              </button>
                            </>
                          );
                        })() : (
                        <button
                          onClick={() => handleAdvanceClick(selectedJdId, record)}
                          className="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-colors"
                        >
                          <ArrowRight size={12} />
                          <span>Advance Stage</span>
                        </button>
                        )}
                        {/* Assessment + Extension — hidden during interview outcome flow */}
                        {!record.current_stage.startsWith('interview_') && (() => {
                          const asmt = assessments[record.candidate_id];
                          if (asmt?.status === 'completed') {
                            return (
                              <span className="px-3 py-2 text-[10px] font-bold rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                                Assessment: {asmt.score}/100
                              </span>
                            );
                          }
                          if (asmt?.status === 'pending') {
                            return null;
                          }
                          return null;
                        })()}
                        {!record.current_stage.startsWith('interview_') && !hasPendingExt && (
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

              {/* Send to Client */}
              {results.some(r => r.status === 'pass_2_complete') && (
                <section>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Client Submission</p>
                  </div>
                  {clientSubmission?.sent ? (
                    <div className="flex items-center space-x-3 px-4 py-3 bg-emerald-900/10 border border-emerald-500/20 rounded-xl">
                      <CheckCircle size={16} className="text-emerald-400 shrink-0" />
                      <div>
                        <p className="text-xs font-bold text-emerald-400">
                          Sent {clientSubmission.candidates_sent} candidate{clientSubmission.candidates_sent !== 1 ? 's' : ''} to {clientSubmission.client_email}
                        </p>
                        <p className="text-[10px] text-slate-500 mt-0.5">
                          {clientSubmission.sent_at ? new Date(clientSubmission.sent_at).toLocaleString() : ''}
                        </p>
                      </div>
                      <button
                        onClick={handleSendToClient}
                        disabled={sendingToClient}
                        className="ml-auto px-3 py-1.5 text-[10px] font-bold text-slate-400 hover:text-white bg-slate-700/50 hover:bg-slate-700 rounded-lg border border-slate-600/50 transition-colors disabled:opacity-40"
                      >
                        {sendingToClient ? '…' : 'Resend'}
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-3">
                      <button
                        onClick={handleSendToClient}
                        disabled={sendingToClient}
                        className="flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-bold rounded-xl transition-colors"
                      >
                        <ArrowRight size={14} />
                        <span>{sendingToClient ? 'Sending…' : `Send ${results.filter(r => r.status === 'pass_2_complete').length} Candidate Assessments to Client`}</span>
                      </button>
                      {clientSendError && (
                        <p className="text-xs text-red-400">{clientSendError}</p>
                      )}
                    </div>
                  )}
                </section>
              )}

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
      {/* Interview Outcome Modal (Selected flow) */}
      {outcomeModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="bg-emerald-600/20 p-2 rounded-xl border border-emerald-500/30">
                  <CheckCircle size={18} className="text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Candidate Selected</h3>
                  <p className="text-xs text-slate-400">{candidateNames[outcomeModal.candidateId] || outcomeModal.candidateId} — {getStagLabel(outcomeModal.currentStage)}</p>
                </div>
              </div>
              <button onClick={() => setOutcomeModal(null)} className="text-slate-400 hover:text-white">
                <X size={18} />
              </button>
            </div>

            {/* Next step choice */}
            <div className="mb-5">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Next Step</p>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setOutcomeNextStep('next_round')}
                  className={`px-4 py-3 rounded-xl border text-sm font-bold transition-colors ${outcomeNextStep === 'next_round' ? 'bg-blue-600/20 border-blue-500/50 text-blue-300' : 'bg-slate-800/50 border-slate-600/50 text-slate-400 hover:border-slate-500'}`}
                >
                  Schedule Next Round
                </button>
                <button
                  onClick={() => setOutcomeNextStep('offer')}
                  className={`px-4 py-3 rounded-xl border text-sm font-bold transition-colors ${outcomeNextStep === 'offer' ? 'bg-violet-600/20 border-violet-500/50 text-violet-300' : 'bg-slate-800/50 border-slate-600/50 text-slate-400 hover:border-slate-500'}`}
                >
                  Move to Offer
                </button>
              </div>
            </div>

            {/* Interview details — shown only for next_round */}
            {outcomeNextStep === 'next_round' && (
              <div className="space-y-4 mb-6">
                <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Interview Details</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-slate-400 uppercase tracking-widest">Date</label>
                    <input type="date" value={outcomeForm.date} onChange={e => setOutcomeForm(f => ({ ...f, date: e.target.value }))}
                      className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 uppercase tracking-widest">Time</label>
                    <input type="time" value={outcomeForm.time} onChange={e => setOutcomeForm(f => ({ ...f, time: e.target.value }))}
                      className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-slate-400 uppercase tracking-widest">Mode</label>
                    <select value={outcomeForm.mode} onChange={e => setOutcomeForm(f => ({ ...f, mode: e.target.value as 'online' | 'in-person' }))}
                      className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
                      <option value="online">Online</option>
                      <option value="in-person">In-Person</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 uppercase tracking-widest">Duration</label>
                    <select value={outcomeForm.duration} onChange={e => setOutcomeForm(f => ({ ...f, duration: e.target.value }))}
                      className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
                      <option value="30min">30 min</option>
                      <option value="45min">45 min</option>
                      <option value="1hour">1 hour</option>
                    </select>
                  </div>
                </div>
                {outcomeForm.mode === 'online' ? (
                  <div>
                    <label className="text-[10px] text-slate-400 uppercase tracking-widest">Meeting Link</label>
                    <input type="url" placeholder="https://meet.google.com/..." value={outcomeForm.meeting_link} onChange={e => setOutcomeForm(f => ({ ...f, meeting_link: e.target.value }))}
                      className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                  </div>
                ) : (
                  <div>
                    <label className="text-[10px] text-slate-400 uppercase tracking-widest">Location</label>
                    <input type="text" placeholder="Office address..." value={outcomeForm.location} onChange={e => setOutcomeForm(f => ({ ...f, location: e.target.value }))}
                      className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                  </div>
                )}
                <div>
                  <label className="text-[10px] text-slate-400 uppercase tracking-widest">Notes (optional)</label>
                  <textarea rows={2} value={outcomeForm.notes} onChange={e => setOutcomeForm(f => ({ ...f, notes: e.target.value }))}
                    className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none" />
                </div>
              </div>
            )}

            {outcomeNextStep === 'offer' && (
              <div className="mb-6 px-4 py-3 bg-violet-500/10 border border-violet-500/20 rounded-xl text-xs text-violet-300">
                Candidate will be moved to Offer stage and an offer response email will be sent automatically.
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={submitSelectedOutcome}
                disabled={interviewOutcomeLoading === outcomeModal.candidateId || (outcomeNextStep === 'next_round' && (!outcomeForm.date || !outcomeForm.time))}
                className="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl transition-colors"
              >
                {interviewOutcomeLoading === outcomeModal.candidateId ? 'Saving…' : outcomeNextStep === 'next_round' ? 'Confirm & Schedule' : 'Move to Offer'}
              </button>
              <button onClick={() => setOutcomeModal(null)} className="px-5 py-3 text-slate-400 hover:text-white text-sm rounded-xl border border-slate-700/50 hover:border-slate-500 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Configure Pipeline Rounds modal */}
      {pipelineConfigModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1e293b] border border-slate-600/50 rounded-2xl p-8 w-full max-w-sm shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">Configure Pipeline Rounds</h3>
            <p className="text-xs text-slate-400 mb-6">Set assessment and interview rounds for <span className="text-slate-200 font-medium">{selectedJdId}</span></p>
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Assessment Rounds (0–5)</label>
                <input
                  type="number"
                  min={0}
                  max={5}
                  value={pipelineConfigForm.assessment_rounds}
                  onChange={e => setPipelineConfigForm(f => ({ ...f, assessment_rounds: Math.min(5, Math.max(0, Number(e.target.value))) }))}
                  className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500/60"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Interview Rounds (1–10)</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={pipelineConfigForm.interview_rounds}
                  onChange={e => setPipelineConfigForm(f => ({ ...f, interview_rounds: Math.min(10, Math.max(1, Number(e.target.value))) }))}
                  className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500/60"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => setPipelineConfigModal(false)}
                className="flex-1 px-4 py-2.5 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-sm font-semibold rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={savePipelineConfig}
                disabled={pipelineConfigSaving}
                className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors"
              >
                {pipelineConfigSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Candidate response message modal */}
      {responseMessageModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1e293b] border border-yellow-500/30 rounded-2xl p-8 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="bg-yellow-500/20 p-2 rounded-xl border border-yellow-500/30">
                  <Clock size={18} className="text-yellow-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Candidate's Message</h3>
                  <p className="text-xs text-slate-400">{responseMessageModal.name}</p>
                </div>
              </div>
              <button onClick={() => setResponseMessageModal(null)} className="text-slate-400 hover:text-white">
                <X size={18} />
              </button>
            </div>
            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl px-5 py-4">
              <p className="text-sm text-slate-200 leading-relaxed">"{responseMessageModal.message}"</p>
            </div>
            <button
              onClick={() => setResponseMessageModal(null)}
              className="mt-5 w-full py-2.5 text-slate-400 hover:text-white text-sm rounded-xl border border-slate-700/50 hover:border-slate-500 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Give Offer Modal */}
      {offerModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="bg-violet-600/20 p-2 rounded-xl border border-violet-500/30">
                  <CheckCircle size={18} className="text-violet-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Give Offer</h3>
                  <p className="text-xs text-slate-400">{candidateNames[offerModal.candidateId] || offerModal.candidateId}</p>
                </div>
              </div>
              <button onClick={() => setOfferModal(null)} className="text-slate-400 hover:text-white">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4 mb-6">
              <div>
                <label className="text-[10px] text-slate-400 uppercase tracking-widest">Joining Date <span className="text-red-400">*</span></label>
                <input
                  type="date"
                  value={offerForm.joining_date}
                  onChange={e => setOfferForm(f => ({ ...f, joining_date: e.target.value }))}
                  className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 uppercase tracking-widest">Work Location <span className="text-red-400">*</span></label>
                <input
                  type="text"
                  placeholder="e.g. Mumbai HQ, Remote, Hybrid - Bangalore"
                  value={offerForm.work_location}
                  onChange={e => setOfferForm(f => ({ ...f, work_location: e.target.value }))}
                  className="mt-1 w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-violet-500 placeholder-slate-600"
                />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={submitGiveOffer}
                disabled={offerSubmitting || !offerForm.joining_date || !offerForm.work_location.trim()}
                className="flex-1 py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-bold rounded-xl transition-colors"
              >
                {offerSubmitting ? 'Confirming…' : 'Confirm Offer & Mark Joined'}
              </button>
              <button onClick={() => setOfferModal(null)} className="px-5 py-3 text-slate-400 hover:text-white text-sm rounded-xl border border-slate-700/50 hover:border-slate-500 transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stage type picker — Assessment or Interview */}
      {stageTypeModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 w-full max-w-sm shadow-2xl">
            <h3 className="text-base font-bold text-white mb-1">What's the next round?</h3>
            <p className="text-xs text-slate-400 mb-6">{stageTypeModal.candidateName}</p>
            <div className="flex flex-col space-y-3">
              <button
                onClick={() => {
                  setAssessmentForm({ date: '', time: '', mode: 'online', platform: '', location: '', duration: '1hour', notes: '' });
                  setAssessmentModal({ jdId: stageTypeModal.jdId, candidateId: stageTypeModal.candidateId });
                  setStageTypeModal(null);
                }}
                className="flex items-center justify-between px-5 py-4 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 rounded-xl transition-colors text-left"
              >
                <div>
                  <p className="text-sm font-bold text-purple-300">Assessment</p>
                  <p className="text-xs text-slate-400 mt-0.5">Schedule an assessment round for the candidate</p>
                </div>
                <ArrowRight size={16} className="text-purple-400 shrink-0" />
              </button>
              <button
                onClick={() => {
                  setStageTypeModal(null);
                  setInterviewForm({ date: '', time: '', mode: 'online', meeting_link: '', location: '', duration: '1hour', notes: '' });
                  setInterviewModal({ candidateId: stageTypeModal.candidateId, nextStage: 'interview_1' });
                }}
                className="flex items-center justify-between px-5 py-4 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 rounded-xl transition-colors text-left"
              >
                <div>
                  <p className="text-sm font-bold text-blue-300">Interview</p>
                  <p className="text-xs text-slate-400 mt-0.5">Schedule an interview round</p>
                </div>
                <ArrowRight size={16} className="text-blue-400 shrink-0" />
              </button>
            </div>
            <button onClick={() => setStageTypeModal(null)} className="mt-4 w-full text-xs text-slate-500 hover:text-slate-300 transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {/* Assessment scheduling modal */}
      {assessmentModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-600/20 rounded-xl">
                  <Calendar className="text-purple-400" size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">Schedule Assessment</h3>
                  <p className="text-xs text-slate-400">{candidateNames[assessmentModal.candidateId] || assessmentModal.candidateId}</p>
                </div>
              </div>
              <button onClick={() => setAssessmentModal(null)} className="text-slate-500 hover:text-white transition-colors"><X size={18} /></button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Date <span className="text-red-400">*</span></label>
                  <input type="date" value={assessmentForm.date} onChange={e => setAssessmentForm(f => ({ ...f, date: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Time <span className="text-red-400">*</span></label>
                  <input type="time" value={assessmentForm.time} onChange={e => setAssessmentForm(f => ({ ...f, time: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Mode <span className="text-red-400">*</span></label>
                  <select value={assessmentForm.mode} onChange={e => setAssessmentForm(f => ({ ...f, mode: e.target.value as 'online' | 'in-person' }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500">
                    <option value="online">Online</option>
                    <option value="in-person">In-person</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Duration</label>
                  <select value={assessmentForm.duration} onChange={e => setAssessmentForm(f => ({ ...f, duration: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500">
                    <option value="30min">30 minutes</option>
                    <option value="45min">45 minutes</option>
                    <option value="1hour">1 hour</option>
                    <option value="2hours">2 hours</option>
                  </select>
                </div>
              </div>

              {assessmentForm.mode === 'online' ? (
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Platform / Link <span className="text-red-400">*</span></label>
                  <input type="text" placeholder="e.g. HackerRank link, Google Form URL..." value={assessmentForm.platform}
                    onChange={e => setAssessmentForm(f => ({ ...f, platform: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1.5">Location <span className="text-red-400">*</span></label>
                  <input type="text" placeholder="Office address or room" value={assessmentForm.location}
                    onChange={e => setAssessmentForm(f => ({ ...f, location: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500" />
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">Notes for candidate <span className="text-slate-500">(optional)</span></label>
                <textarea placeholder="Topics to prepare, tools required, instructions..." value={assessmentForm.notes}
                  onChange={e => setAssessmentForm(f => ({ ...f, notes: e.target.value }))} rows={3}
                  className="w-full px-3 py-2 bg-slate-900/50 border border-slate-700/50 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none" />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                disabled={assessmentSubmitting || !assessmentForm.date || !assessmentForm.time || !(assessmentForm.mode === 'online' ? assessmentForm.platform : assessmentForm.location)}
                onClick={async () => {
                  if (!assessmentModal) return;
                  setAssessmentSubmitting(true);
                  try {
                    const r = await fetch(`${API}/assessments/generate/${assessmentModal.jdId}/${assessmentModal.candidateId}`, {
                      method: 'POST',
                      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        date: assessmentForm.date,
                        time: assessmentForm.time,
                        mode: assessmentForm.mode,
                        platform: assessmentForm.mode === 'online' ? assessmentForm.platform : undefined,
                        location: assessmentForm.mode === 'in-person' ? assessmentForm.location : undefined,
                        duration: assessmentForm.duration,
                        notes: assessmentForm.notes,
                      }),
                    });
                    if (r.ok) {
                      const d = await r.json();
                      setAssessments(prev => ({ ...prev, [assessmentModal.candidateId]: { status: 'pending', score: null, assessment_id: d.assessment_id } }));
                    }
                    setAssessmentModal(null);
                    await loadPipeline(selectedJdId);
                  } finally {
                    setAssessmentSubmitting(false);
                  }
                }}
                className="flex-1 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-600/40 text-white font-semibold text-sm rounded-lg transition-colors"
              >
                {assessmentSubmitting ? 'Sending...' : 'Confirm & Send Assessment'}
              </button>
              <button onClick={() => setAssessmentModal(null)} disabled={assessmentSubmitting}
                className="flex-1 py-2.5 bg-slate-700/50 hover:bg-slate-700 text-slate-300 font-semibold text-sm rounded-lg transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

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
