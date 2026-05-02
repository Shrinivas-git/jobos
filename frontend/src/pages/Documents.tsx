import React, { useState, useEffect, useRef } from 'react';
import keycloak from '../keycloak';
import {
  VaultDocument,
  DocumentListResponse,
  AccessLogEntry,
  uploadDocument,
  listMyDocuments,
  listCandidateDocuments,
  revokeDocumentConsent,
  fetchDocumentBlob,
  getAccessLog,
} from '../utils/api';
import { Upload, FileText, Eye, Download, XCircle, Clock, Shield, Search } from 'lucide-react';

const DOC_TYPE_LABELS: Record<string, string> = {
  experience: 'Experience',
  education:  'Education',
  licence:    'Professional Licence',
  identity:   'Identity',
  salary:     'Salary',
};

const TIER_META: Record<number, { label: string; color: string; bg: string }> = {
  1: { label: 'Tier 1 · Preview',  color: 'text-slate-400',   bg: 'bg-slate-700/50' },
  2: { label: 'Tier 2 · Review',   color: 'text-blue-400',    bg: 'bg-blue-500/15'  },
  3: { label: 'Tier 3 · Verified', color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
  4: { label: 'Tier 4 · Offer',    color: 'text-amber-400',   bg: 'bg-amber-500/15' },
};

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

// ── Candidate view ───────────────────────────────────────────────────────────

const CandidateVault: React.FC = () => {
  const [docs, setDocs] = useState<VaultDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [docType, setDocType] = useState('experience');
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    setDocs(await listMyDocuments());
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async () => {
    if (!file || !consent) return;
    setUploading(true);
    setError('');
    setSuccess('');
    try {
      await uploadDocument(docType, consent, file);
      setSuccess('Document uploaded successfully.');
      setFile(null);
      setConsent(false);
      if (fileRef.current) fileRef.current.value = '';
      await load();
    } catch (e: any) {
      setError(e.message);
    }
    setUploading(false);
  };

  const handleRevoke = async (docId: string) => {
    setError('');
    setSuccess('');
    try {
      await revokeDocumentConsent(docId);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload card */}
      <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl p-6">
        <h3 className="text-lg font-bold text-white mb-1">Upload Document</h3>
        <p className="text-slate-400 text-sm mb-5">
          Documents are only accessible to recruiters at the appropriate hiring stage. You can revoke access at any time.
        </p>

        {error && (
          <div className="mb-4 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 px-4 py-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm">
            {success}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
              Document Type
            </label>
            <select
              value={docType}
              onChange={e => setDocType(e.target.value)}
              className="w-full bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              {Object.entries(DOC_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
              File (PDF, DOCX, JPG, PNG — max 10 MB)
            </label>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.jpg,.jpeg,.png"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
              className="w-full bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-300
                file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0
                file:bg-blue-600 file:text-white file:text-xs file:cursor-pointer
                focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <label className="flex items-start gap-3 cursor-pointer mb-5 select-none">
          <input
            type="checkbox"
            checked={consent}
            onChange={e => setConsent(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-800 accent-blue-500 cursor-pointer"
          />
          <span className="text-sm text-slate-300">
            I consent to share this document with recruiters during active hiring processes. I understand I
            can revoke access at any time (except during an active offer stage).
          </span>
        </label>

        <button
          onClick={handleUpload}
          disabled={!file || !consent || uploading}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500
            disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed
            text-white text-sm font-bold rounded-xl transition-colors"
        >
          <Upload size={15} />
          {uploading ? 'Uploading…' : 'Upload Document'}
        </button>
      </div>

      {/* My Documents list */}
      <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl p-6">
        <h3 className="text-lg font-bold text-white mb-5">My Documents</h3>

        {loading ? (
          <div className="flex items-center justify-center h-32 text-slate-500 text-sm">Loading…</div>
        ) : docs.length === 0 ? (
          <div className="flex items-center justify-center h-32 border-2 border-dashed border-slate-700 rounded-xl text-slate-500 text-sm">
            No documents uploaded yet
          </div>
        ) : (
          <div className="space-y-3">
            {docs.map(doc => (
              <div
                key={doc.doc_id}
                className={`flex items-center justify-between px-4 py-3 rounded-xl border ${
                  doc.access_revoked
                    ? 'bg-slate-800/30 border-slate-700/30 opacity-60'
                    : 'bg-[#0f172a] border-slate-700/50'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <FileText size={18} className={doc.access_revoked ? 'text-slate-600 shrink-0' : 'text-blue-400 shrink-0'} />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-white truncate">{doc.original_filename}</p>
                    <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${TIER_META[doc.tier_required]?.bg} ${TIER_META[doc.tier_required]?.color}`}>
                        {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        Uploaded {fmtDate(doc.uploaded_at)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 ml-4">
                  {doc.access_revoked ? (
                    <span className="text-[10px] px-2 py-1 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg font-bold whitespace-nowrap">
                      Access Revoked
                    </span>
                  ) : (
                    <>
                      <span className="text-[10px] px-2 py-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg font-bold whitespace-nowrap hidden sm:inline">
                        Consent Active
                      </span>
                      <button
                        onClick={() => handleRevoke(doc.doc_id)}
                        className="flex items-center gap-1.5 text-xs px-3 py-1.5
                          bg-red-500/10 hover:bg-red-500/20 border border-red-500/20
                          text-red-400 rounded-lg font-semibold transition-colors whitespace-nowrap"
                      >
                        <XCircle size={13} />
                        Revoke
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ── Recruiter / Manager / HOD / Admin view ───────────────────────────────────

const RecruiterVault: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'docs' | 'log'>('docs');

  // Documents tab
  const [candidateId, setCandidateId] = useState('');
  const [jdId, setJdId] = useState('');
  const [docResult, setDocResult] = useState<DocumentListResponse | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState('');
  const [actionError, setActionError] = useState('');

  // Access log tab
  const [logCandidateId, setLogCandidateId] = useState('');
  const [logResult, setLogResult] = useState<{ total: number; logs: AccessLogEntry[] } | null>(null);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState('');

  const handleDocSearch = async () => {
    if (!candidateId.trim() || !jdId.trim()) return;
    setDocLoading(true);
    setDocError('');
    setActionError('');
    setDocResult(null);
    try {
      setDocResult(await listCandidateDocuments(candidateId.trim(), jdId.trim()));
    } catch (e: any) {
      setDocError(e.message);
    }
    setDocLoading(false);
  };

  const handleView = async (doc: VaultDocument) => {
    setActionError('');
    try {
      const { blob, filename } = await fetchDocumentBlob(doc.doc_id, jdId, 'view');
      const url = URL.createObjectURL(blob);
      const opened = window.open(url, '_blank');
      if (!opened) {
        const a = document.createElement('a');
        a.href = url; a.target = '_blank'; a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e: any) {
      setActionError(e.message);
    }
  };

  const handleDownload = async (doc: VaultDocument) => {
    setActionError('');
    try {
      const { blob, filename } = await fetchDocumentBlob(doc.doc_id, jdId, 'download');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e: any) {
      setActionError(e.message);
    }
  };

  const handleLogSearch = async () => {
    if (!logCandidateId.trim()) return;
    setLogLoading(true);
    setLogError('');
    setLogResult(null);
    try {
      setLogResult(await getAccessLog({ candidateId: logCandidateId.trim() }));
    } catch (e: any) {
      setLogError(e.message);
    }
    setLogLoading(false);
  };

  return (
    <div className="space-y-6">
      {/* Tab switcher */}
      <div className="flex gap-1 bg-[#0f172a] p-1 rounded-xl w-fit border border-slate-800">
        {(['docs', 'log'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-lg text-sm font-bold transition-colors ${
              activeTab === tab ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            {tab === 'docs' ? 'Documents' : 'Access Log'}
          </button>
        ))}
      </div>

      {/* ── Documents tab ── */}
      {activeTab === 'docs' && (
        <div className="space-y-5">
          <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4">Search Candidate Documents</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                  Candidate ID
                </label>
                <input
                  value={candidateId}
                  onChange={e => setCandidateId(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleDocSearch()}
                  placeholder="CAN-20260502-xxxxxxxx"
                  className="w-full bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                  JD ID
                </label>
                <input
                  value={jdId}
                  onChange={e => setJdId(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleDocSearch()}
                  placeholder="JD-20260502-xxxxxxxx"
                  className="w-full bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <button
              onClick={handleDocSearch}
              disabled={!candidateId.trim() || !jdId.trim() || docLoading}
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500
                disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed
                text-white text-sm font-bold rounded-xl transition-colors"
            >
              <Search size={15} />
              {docLoading ? 'Searching…' : 'Search'}
            </button>
            {docError && <p className="mt-3 text-sm text-red-400">{docError}</p>}
          </div>

          {docResult && (
            <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-bold text-white">Available Documents</h3>
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border
                  ${TIER_META[docResult.unlocked_tier]?.bg} ${TIER_META[docResult.unlocked_tier]?.color}
                  border-current/20`}
                >
                  <Shield size={13} />
                  {TIER_META[docResult.unlocked_tier]?.label ?? `Tier ${docResult.unlocked_tier}`}
                </div>
              </div>

              {actionError && (
                <div className="mb-4 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                  {actionError}
                </div>
              )}

              {docResult.documents.length === 0 ? (
                <div className="flex items-center justify-center h-24 border-2 border-dashed border-slate-700 rounded-xl text-slate-500 text-sm">
                  No documents accessible at the current pipeline stage
                </div>
              ) : (
                <div className="space-y-3">
                  {docResult.documents.map(doc => (
                    <div
                      key={doc.doc_id}
                      className="flex items-center justify-between px-4 py-3 bg-[#0f172a] border border-slate-700/50 rounded-xl"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <FileText size={18} className="text-blue-400 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-white truncate">{doc.original_filename}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${TIER_META[doc.tier_required]?.bg} ${TIER_META[doc.tier_required]?.color}`}>
                              {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                            </span>
                            <span className="text-[10px] text-slate-500">{fmtDate(doc.uploaded_at)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-4">
                        <button
                          onClick={() => handleView(doc)}
                          className="flex items-center gap-1.5 text-xs px-3 py-1.5
                            bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20
                            text-blue-400 rounded-lg font-semibold transition-colors"
                        >
                          <Eye size={13} />
                          View
                        </button>
                        {docResult.unlocked_tier >= 4 && (
                          <button
                            onClick={() => handleDownload(doc)}
                            className="flex items-center gap-1.5 text-xs px-3 py-1.5
                              bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20
                              text-amber-400 rounded-lg font-semibold transition-colors"
                          >
                            <Download size={13} />
                            Download
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Access Log tab ── */}
      {activeTab === 'log' && (
        <div className="space-y-5">
          <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4">Access Log</h3>
            <div className="flex gap-4 mb-4">
              <div className="flex-1 max-w-sm">
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                  Candidate ID
                </label>
                <input
                  value={logCandidateId}
                  onChange={e => setLogCandidateId(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleLogSearch()}
                  placeholder="CAN-20260502-xxxxxxxx"
                  className="w-full bg-[#0f172a] border border-slate-700 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <button
              onClick={handleLogSearch}
              disabled={!logCandidateId.trim() || logLoading}
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500
                disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed
                text-white text-sm font-bold rounded-xl transition-colors"
            >
              <Search size={15} />
              {logLoading ? 'Loading…' : 'Load Log'}
            </button>
            {logError && <p className="mt-3 text-sm text-red-400">{logError}</p>}
          </div>

          {logResult && (
            <div className="bg-[#1e293b] border border-slate-700/60 rounded-2xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between">
                <h3 className="text-base font-bold text-white">Audit Trail</h3>
                <span className="text-xs text-slate-500">{logResult.total} entries</span>
              </div>

              {logResult.logs.length === 0 ? (
                <div className="flex items-center justify-center h-24 text-slate-500 text-sm">
                  No access events recorded
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-[#0f172a]">
                        <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Accessor</th>
                        <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Document</th>
                        <th className="text-center px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Action</th>
                        <th className="text-center px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Tier</th>
                        <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">JD</th>
                        <th className="text-right px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logResult.logs.map(entry => (
                        <tr
                          key={entry.log_id}
                          className="border-t border-slate-800/60 hover:bg-slate-800/20 transition-colors"
                        >
                          <td className="px-5 py-3">
                            <p className="text-white font-medium text-sm">
                              {entry.accessor_email || entry.accessed_by}
                            </p>
                            <p className="text-[10px] text-slate-500 mt-0.5 uppercase">{entry.accessor_role}</p>
                          </td>
                          <td className="px-5 py-3">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${TIER_META[entry.tier_at_access]?.bg} ${TIER_META[entry.tier_at_access]?.color}`}>
                              {DOC_TYPE_LABELS[entry.doc_type] ?? entry.doc_type}
                            </span>
                          </td>
                          <td className="px-5 py-3 text-center">
                            {entry.access_type === 'download' ? (
                              <span className="text-[10px] px-2 py-1 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-lg font-bold">
                                Download
                              </span>
                            ) : (
                              <span className="text-[10px] px-2 py-1 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-lg font-bold">
                                View
                              </span>
                            )}
                          </td>
                          <td className="px-5 py-3 text-center">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${TIER_META[entry.tier_at_access]?.bg} ${TIER_META[entry.tier_at_access]?.color}`}>
                              T{entry.tier_at_access}
                            </span>
                          </td>
                          <td className="px-5 py-3 text-slate-400 text-xs font-mono">{entry.jd_id}</td>
                          <td className="px-5 py-3 text-right text-slate-400 text-xs whitespace-nowrap">
                            <Clock size={11} className="inline mr-1 text-slate-600" />
                            {fmtDateTime(entry.timestamp)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ── Root component ────────────────────────────────────────────────────────────

const Documents: React.FC = () => {
  const roles: string[] = (keycloak.tokenParsed as any)?.realm_access?.roles ?? [];
  return roles.includes('candidate') ? <CandidateVault /> : <RecruiterVault />;
};

export default Documents;
