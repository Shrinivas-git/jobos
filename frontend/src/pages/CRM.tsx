import React, { useState, useEffect } from 'react';
import { Mail, Send, Clock, CheckCircle, XCircle, Eye, EyeOff, RefreshCw } from 'lucide-react';
import {
  API, getAuthHeaders, JD, MatchResult, CrmMessage,
  draftCrmMessage, listCrmMessages, approveAndSendCrmMessage,
} from '../utils/api';

const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

const candidateScore = (r: MatchResult): number => {
  if (r.composite_score != null) return r.composite_score > 1 ? r.composite_score : r.composite_score * 100;
  if (r.fitment_score != null) return r.fitment_score;
  return r.match_score * 100;
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  if (status === 'sent') return (
    <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg font-bold whitespace-nowrap">
      <CheckCircle size={10} /> Sent
    </span>
  );
  if (status === 'failed') return (
    <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg font-bold whitespace-nowrap">
      <XCircle size={10} /> Failed
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-lg font-bold whitespace-nowrap">
      <Clock size={10} /> Draft
    </span>
  );
};

const CRM: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'outreach' | 'history'>('outreach');

  // Outreach
  const [jds, setJds] = useState<JD[]>([]);
  const [selectedJdId, setSelectedJdId] = useState('');
  const [shortlisted, setShortlisted] = useState<MatchResult[]>([]);
  const [nameMap, setNameMap] = useState<Record<string, string>>({});
  const [loadingJds, setLoadingJds] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [draftingFor, setDraftingFor] = useState<string | null>(null);

  // Compose modal
  const [modal, setModal] = useState<CrmMessage | null>(null);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [sending, setSending] = useState(false);
  const [modalError, setModalError] = useState('');

  // History
  const [history, setHistory] = useState<CrmMessage[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyJdFilter, setHistoryJdFilter] = useState('');
  const [viewingMsg, setViewingMsg] = useState<CrmMessage | null>(null);

  // Toast
  const [toast, setToast] = useState('');
  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(''), 3500); };

  // Load JDs + candidate name map on mount
  useEffect(() => {
    Promise.all([
      fetch(`${API}/jd/`, { headers: getAuthHeaders() }).then(r => r.json()).catch(() => []),
      fetch(`${API}/candidates/`, { headers: getAuthHeaders() }).then(r => r.json()).catch(() => []),
    ]).then(([jdData, candData]) => {
      setJds(Array.isArray(jdData) ? jdData : []);
      const lookup: Record<string, string> = {};
      (candData as { candidate_id: string; name?: string }[]).forEach(c => {
        lookup[c.candidate_id] = c.name || c.candidate_id;
      });
      setNameMap(lookup);
    }).finally(() => setLoadingJds(false));
  }, []);

  // Load shortlisted candidates when JD changes
  useEffect(() => {
    if (!selectedJdId) { setShortlisted([]); return; }
    setLoadingCandidates(true);
    fetch(`${API}/matching/results/${selectedJdId}`, { headers: getAuthHeaders() })
      .then(r => r.json())
      .then((data: MatchResult[]) => setShortlisted(
        Array.isArray(data) ? data.filter(r => r.status === 'shortlisted') : []
      ))
      .catch(() => setShortlisted([]))
      .finally(() => setLoadingCandidates(false));
  }, [selectedJdId]);

  const loadHistory = async (jd_id?: string) => {
    setLoadingHistory(true);
    setHistory(await listCrmMessages(jd_id || undefined));
    setLoadingHistory(false);
  };

  useEffect(() => {
    if (activeTab === 'history') loadHistory(historyJdFilter || undefined);
  }, [activeTab]);

  const handleDraft = async (candidate_id: string) => {
    setDraftingFor(candidate_id);
    try {
      const msg = await draftCrmMessage(selectedJdId, candidate_id);
      setModal(msg);
      setEditSubject(msg.subject);
      setEditBody(msg.body);
      setModalError('');
      setShowPreview(false);
    } catch (e: any) {
      showToast(e.message ?? 'Draft failed');
    } finally {
      setDraftingFor(null);
    }
  };

  const handleSend = async () => {
    if (!modal) return;
    setSending(true);
    setModalError('');
    try {
      const updated = await approveAndSendCrmMessage(
        modal.message_id,
        editSubject !== modal.subject ? editSubject : undefined,
        editBody !== modal.body ? editBody : undefined,
      );
      setModal(null);
      showToast(
        updated.status === 'sent'
          ? `Email sent to ${updated.candidate_name}`
          : 'Send failed — check SMTP config'
      );
    } catch (e: any) {
      setModalError(e.message ?? 'Send failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 px-5 py-3 bg-slate-800 border border-slate-600 text-white text-sm font-semibold rounded-xl shadow-xl">
          {toast}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-[#0f172a] p-1 rounded-xl w-fit border border-slate-800">
        {(['outreach', 'history'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-lg text-sm font-bold transition-colors ${
              activeTab === tab ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            {tab === 'outreach' ? 'Compose Outreach' : 'Message History'}
          </button>
        ))}
      </div>

      {/* ── Outreach tab ── */}
      {activeTab === 'outreach' && (
        <div className="space-y-5">
          {/* JD selector */}
          <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4">Select Job Description</h3>
            {loadingJds ? (
              <p className="text-slate-500 text-sm">Loading JDs…</p>
            ) : (
              <select
                value={selectedJdId}
                onChange={e => setSelectedJdId(e.target.value)}
                className="w-full max-w-md bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">— Select a JD —</option>
                {jds.map(jd => (
                  <option key={jd.jd_id} value={jd.jd_id}>{jd.title} ({jd.jd_id})</option>
                ))}
              </select>
            )}
          </div>

          {/* Candidates table */}
          {selectedJdId && (
            <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between">
                <h3 className="text-base font-bold text-white">Shortlisted Candidates</h3>
                <span className="text-xs text-slate-500">
                  {loadingCandidates ? 'Loading…' : `${shortlisted.length} candidate${shortlisted.length !== 1 ? 's' : ''}`}
                </span>
              </div>

              {loadingCandidates ? (
                <div className="flex items-center justify-center h-32 text-slate-500 text-sm">Loading…</div>
              ) : shortlisted.length === 0 ? (
                <div className="flex items-center justify-center h-32 border-2 border-dashed border-slate-700 m-6 rounded-xl text-slate-500 text-sm">
                  No shortlisted candidates for this JD
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-[#0f172a]">
                      <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Candidate</th>
                      <th className="text-center px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Score</th>
                      <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider hidden md:table-cell">Recommendation</th>
                      <th className="px-5 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {shortlisted.map(r => (
                      <tr key={r.candidate_id} className="border-t border-slate-800/60 hover:bg-slate-800/20 transition-colors">
                        <td className="px-5 py-3">
                          <p className="text-white font-medium">{nameMap[r.candidate_id] ?? r.candidate_id}</p>
                          <p className="text-[10px] text-slate-500 font-mono mt-0.5">{r.candidate_id}</p>
                        </td>
                        <td className="px-5 py-3 text-center">
                          <span className="text-sm font-bold text-blue-400">{Math.round(candidateScore(r))}</span>
                          <span className="text-[10px] text-slate-500">/100</span>
                        </td>
                        <td className="px-5 py-3 text-slate-300 text-xs capitalize hidden md:table-cell">
                          {r.recommendation ?? '—'}
                        </td>
                        <td className="px-5 py-3 text-right">
                          <button
                            onClick={() => handleDraft(r.candidate_id)}
                            disabled={draftingFor === r.candidate_id}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5
                              bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500
                              disabled:cursor-not-allowed text-white text-xs font-bold rounded-xl transition-colors"
                          >
                            <Mail size={13} />
                            {draftingFor === r.candidate_id ? 'Drafting…' : 'Draft Message'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── History tab ── */}
      {activeTab === 'history' && (
        <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between">
            <h3 className="text-base font-bold text-white">Message History</h3>
            <button
              onClick={() => loadHistory(historyJdFilter || undefined)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs font-bold rounded-xl transition-colors"
            >
              <RefreshCw size={13} />
              Refresh
            </button>
          </div>

          <div className="px-6 py-4 border-b border-slate-800/60">
            <select
              value={historyJdFilter}
              onChange={e => { setHistoryJdFilter(e.target.value); loadHistory(e.target.value || undefined); }}
              className="bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">All JDs</option>
              {jds.map(jd => (
                <option key={jd.jd_id} value={jd.jd_id}>{jd.title}</option>
              ))}
            </select>
          </div>

          {loadingHistory ? (
            <div className="flex items-center justify-center h-32 text-slate-500 text-sm">Loading…</div>
          ) : history.length === 0 ? (
            <div className="flex items-center justify-center h-32 border-2 border-dashed border-slate-700 m-6 rounded-xl text-slate-500 text-sm">
              No messages yet
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-[#0f172a]">
                    <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Candidate</th>
                    <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider hidden md:table-cell">Subject</th>
                    <th className="text-center px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Status</th>
                    <th className="text-right px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Date</th>
                    <th className="px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(msg => (
                    <tr key={msg.message_id} className="border-t border-slate-800/60 hover:bg-slate-800/20 transition-colors">
                      <td className="px-5 py-3">
                        <p className="text-white font-medium">{msg.candidate_name}</p>
                        <p className="text-[10px] text-slate-500 mt-0.5">{msg.candidate_email}</p>
                      </td>
                      <td className="px-5 py-3 text-slate-300 text-xs max-w-xs truncate hidden md:table-cell">
                        {msg.subject}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex justify-center"><StatusBadge status={msg.status} /></div>
                      </td>
                      <td className="px-5 py-3 text-right text-slate-400 text-xs whitespace-nowrap">
                        {fmtDateTime(msg.sent_at ?? msg.created_at)}
                      </td>
                      <td className="px-5 py-3">
                        <button
                          onClick={() => setViewingMsg(msg)}
                          className="flex items-center gap-1 text-xs px-2.5 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg font-semibold transition-colors"
                        >
                          <Eye size={12} />
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Compose modal ── */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl bg-[#1e293b] border border-slate-700/60 rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between shrink-0">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Mail size={16} className="text-blue-400" />
                  Outreach to {modal.candidate_name}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">{modal.candidate_email} · {modal.jd_title}</p>
              </div>
              <button onClick={() => setModal(null)} className="text-slate-500 hover:text-white transition-colors">
                <XCircle size={20} />
              </button>
            </div>

            <div className="px-6 py-5 overflow-y-auto space-y-4">
              {modalError && (
                <div className="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                  {modalError}
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                  Subject
                </label>
                <input
                  value={editSubject}
                  onChange={e => setEditSubject(e.target.value)}
                  className="w-full bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Message Body (HTML)
                  </label>
                  <button
                    onClick={() => setShowPreview(p => !p)}
                    className="flex items-center gap-1 text-[10px] px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg font-bold transition-colors"
                  >
                    {showPreview ? <EyeOff size={11} /> : <Eye size={11} />}
                    {showPreview ? 'Hide Preview' : 'Preview'}
                  </button>
                </div>
                <textarea
                  value={editBody}
                  onChange={e => setEditBody(e.target.value)}
                  rows={showPreview ? 6 : 12}
                  className="w-full bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white font-mono focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>

              {showPreview && (
                <div className="bg-white rounded-xl p-5 text-sm text-gray-800 max-h-48 overflow-y-auto">
                  <div dangerouslySetInnerHTML={{ __html: editBody }} />
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-700/60 flex items-center justify-end gap-3 shrink-0">
              <button
                onClick={() => setModal(null)}
                className="px-4 py-2 text-sm font-bold text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSend}
                disabled={sending || !editSubject.trim() || !editBody.trim()}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500
                  disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed
                  text-white text-sm font-bold rounded-xl transition-colors"
              >
                <Send size={15} />
                {sending ? 'Sending…' : 'Approve & Send'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── View message modal (history) ── */}
      {viewingMsg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl bg-[#1e293b] border border-slate-700/60 rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between shrink-0">
              <div>
                <h3 className="text-base font-bold text-white">{viewingMsg.subject}</h3>
                <div className="flex items-center gap-3 mt-1">
                  <p className="text-xs text-slate-500">{viewingMsg.candidate_email}</p>
                  <StatusBadge status={viewingMsg.status} />
                  {viewingMsg.edited && (
                    <span className="text-[10px] text-slate-500 italic">edited</span>
                  )}
                </div>
              </div>
              <button onClick={() => setViewingMsg(null)} className="text-slate-500 hover:text-white transition-colors">
                <XCircle size={20} />
              </button>
            </div>
            <div className="px-6 py-5 overflow-y-auto">
              <div className="bg-white rounded-xl p-5 text-sm text-gray-800">
                <div dangerouslySetInnerHTML={{ __html: viewingMsg.body }} />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-700/60 flex justify-end shrink-0">
              <button
                onClick={() => setViewingMsg(null)}
                className="px-4 py-2 text-sm font-bold text-slate-400 hover:text-white transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CRM;
