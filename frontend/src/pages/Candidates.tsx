import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API, getAuthHeaders } from '../utils/api';
import { Upload, FileText, Search, Loader2, CheckCircle2, AlertCircle, User, Mail, Phone, MapPin, Trash2, X } from 'lucide-react';

interface Candidate {
  candidate_id: string;
  name: string;
  email: string;
  phone: string;
  skills: string[];
  experience_years: number;
  location: string;
  notice_period: string;
  gender: string;
  college: string;
  college_tier: string;
  status: string;
  source: string;
  created_at: string;
}

const Candidates: React.FC = () => {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);
  const [search, setSearch] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null); // candidate_id pending confirmation
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchCandidates = async () => {
    try {
      const response = await axios.get(`${API}/candidates/`, {
        headers: getAuthHeaders()
      });
      // Sort by newest first
      const sorted = response.data.sort((a: any, b: any) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setCandidates(sorted);
    } catch (err) {
      console.error("Error fetching candidates", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setStatus(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post(`${API}/candidates/upload-resume`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...getAuthHeaders(),
        }
      });
      setStatus({ type: 'success', message: 'Resume processed and candidate profile created!' });
      setFile(null);
      fetchCandidates();
    } catch (err: any) {
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to process resume' });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (candidateId: string) => {
    setDeleting(candidateId);
    try {
      await axios.delete(`${API}/candidates/${candidateId}`, { headers: getAuthHeaders() });
      setCandidates(prev => prev.filter(c => c.candidate_id !== candidateId));
    } catch (err: any) {
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to delete candidate' });
    } finally {
      setDeleting(null);
      setDeleteConfirm(null);
    }
  };

  const filteredCandidates = candidates.filter(c => 
    c.name?.toLowerCase().includes(search.toLowerCase()) ||
    c.email?.toLowerCase().includes(search.toLowerCase()) ||
    c.skills?.some(s => s.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-8 max-w-[1600px] mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Upload Section */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-6 md:p-8 shadow-xl">
            <h3 className="text-xl font-bold text-white flex items-center mb-6">
              <Upload size={20} className="mr-2 text-blue-400" />
              Direct Intake
            </h3>
            
            <form onSubmit={handleUpload} className="space-y-6">
              <div className="relative group">
                <input
                  type="file"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                  disabled={uploading}
                />
                <div className={`w-full border-2 border-dashed ${file ? 'border-blue-500 bg-blue-500/5' : 'border-slate-700 group-hover:border-slate-600'} rounded-2xl p-12 text-center transition-all`}>
                  <FileText size={48} className={`mx-auto mb-4 ${file ? 'text-blue-400' : 'text-slate-600'}`} />
                  <p className="text-sm font-bold text-slate-300 uppercase tracking-wide">
                    {file ? file.name : 'Drop PDF or DOCX resume'}
                  </p>
                  <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-2">
                    Synchronous AI Extraction
                  </p>
                </div>
              </div>

              {status && (
                <div className={`p-4 rounded-xl flex items-start space-x-3 animate-in fade-in slide-in-from-top-1 ${status.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                  {status.type === 'success' ? <CheckCircle2 size={18} className="mt-0.5 shrink-0" /> : <AlertCircle size={18} className="mt-0.5 shrink-0" />}
                  <p className="text-xs font-bold leading-relaxed">{status.message}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={!file || uploading}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white font-black py-4 rounded-xl transition-all shadow-lg shadow-blue-500/20 flex items-center justify-center space-x-2 active:scale-[0.98] uppercase tracking-widest text-xs"
              >
                {uploading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    <span>Processing Metadata...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={18} />
                    <span>Analyze & Add Candidate</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* List Section */}
        <div className="lg:col-span-8 space-y-6">
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-6 md:p-8 shadow-xl min-h-[600px] flex flex-col">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center">
                  <User size={20} className="mr-2 text-blue-400" />
                  Verified Talent Pool
                </h3>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">
                  Showing {filteredCandidates.length} profiles
                </p>
              </div>

              <div className="relative">
                <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search name, skills, email..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-xl pl-11 pr-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 w-full md:w-80 transition-all"
                />
              </div>
            </div>

            {loading ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 className="animate-spin text-blue-500" size={32} />
              </div>
            ) : filteredCandidates.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center">
                <div className="bg-slate-900/50 p-8 rounded-full mb-4">
                  <User size={56} className="text-slate-700" />
                </div>
                <p className="text-slate-400 font-medium max-w-xs uppercase text-[10px] tracking-widest">No candidates found matching your criteria</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {filteredCandidates.map((c) => (
                  <div key={c.candidate_id} className="p-6 bg-slate-900/40 rounded-2xl border border-slate-800/50 hover:border-slate-700 transition-all group overflow-hidden">
                    <div className="flex flex-col md:flex-row gap-6">
                      {/* Avatar/Initials */}
                      <div className="w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400 font-black text-xl shrink-0">
                        {c.name ? c.name.charAt(0).toUpperCase() : '?'}
                      </div>

                      {/* Info */}
                      <div className="flex-1 space-y-4">
                        <div className="flex flex-col md:flex-row md:items-start justify-between gap-2">
                          <div>
                            <h4 className="text-lg font-bold text-white group-hover:text-blue-400 transition-colors">{c.name || 'Unknown Candidate'}</h4>
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-1">
                              <div className="flex items-center text-[11px] font-bold text-slate-400">
                                <Mail size={12} className="mr-1.5 text-slate-500" />
                                {c.email}
                              </div>
                              <div className="flex items-center text-[11px] font-bold text-slate-400">
                                <Phone size={12} className="mr-1.5 text-slate-500" />
                                {c.phone || 'No phone'}
                              </div>
                              <div className="flex items-center text-[11px] font-bold text-slate-400">
                                <MapPin size={12} className="mr-1.5 text-slate-500" />
                                {c.location || 'Not specified'}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <span className="text-[10px] font-black uppercase bg-blue-500/10 text-blue-400 px-3 py-1 rounded-full border border-blue-500/20">
                              {c.experience_years || 0} Years Exp
                            </span>
                            <span className="text-[10px] font-black uppercase bg-slate-800 text-slate-400 px-3 py-1 rounded-full border border-slate-700">
                              {c.college_tier || 'Tier 3'}
                            </span>
                            <button
                              onClick={() => setDeleteConfirm(c.candidate_id)}
                              className="p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                              title="Delete candidate"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>

                        {/* Extra Details Grid */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-3 bg-slate-900/60 rounded-xl border border-slate-800/50">
                          <div>
                            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Notice Period</p>
                            <p className="text-[11px] font-bold text-slate-300">{c.notice_period || 'Unknown'}</p>
                          </div>
                          <div>
                            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Gender</p>
                            <p className="text-[11px] font-bold text-slate-300">{c.gender || 'Unknown'}</p>
                          </div>
                          <div className="col-span-2">
                            <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">College</p>
                            <p className="text-[11px] font-bold text-slate-300 truncate">{c.college || 'Not specified'}</p>
                          </div>
                        </div>

                        {/* Skills */}
                        <div className="flex flex-wrap gap-1.5">
                          {c.skills && c.skills.length > 0 ? (
                            c.skills.slice(0, 8).map((s, i) => (
                              <span key={i} className="text-[9px] font-black uppercase tracking-tight bg-slate-800/50 text-slate-400 px-2 py-0.5 rounded border border-slate-700/50">
                                {s}
                              </span>
                            ))
                          ) : (
                            <span className="text-[9px] font-bold text-slate-600 italic">No skills extracted</span>
                          )}
                          {c.skills && c.skills.length > 8 && (
                            <span className="text-[9px] font-black text-slate-500 px-2 py-0.5">+{c.skills.length - 8} more</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      {/* Delete confirmation modal */}
      {deleteConfirm && (() => {
        const c = candidates.find(x => x.candidate_id === deleteConfirm);
        return (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[#1e293b] border border-red-500/30 rounded-2xl p-8 w-full max-w-md shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="bg-red-600/20 p-2 rounded-xl">
                    <Trash2 size={18} className="text-red-400" />
                  </div>
                  <h3 className="text-base font-bold text-white">Delete Candidate</h3>
                </div>
                <button onClick={() => setDeleteConfirm(null)} className="text-slate-400 hover:text-white">
                  <X size={18} />
                </button>
              </div>
              <p className="text-sm text-slate-300 mb-1">
                Are you sure you want to permanently delete <span className="font-bold text-white">{c?.name || deleteConfirm}</span>?
              </p>
              <p className="text-xs text-red-400 mb-6">
                This removes the candidate from the talent pool, all matching records, pipeline stages, and the resume file. This cannot be undone.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleDelete(deleteConfirm)}
                  disabled={deleting === deleteConfirm}
                  className="flex-1 py-3 bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white text-sm font-bold rounded-xl transition-colors"
                >
                  {deleting === deleteConfirm ? 'Deleting…' : 'Yes, Delete Permanently'}
                </button>
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="px-5 py-3 text-slate-400 hover:text-white text-sm rounded-xl border border-slate-700/50 hover:border-slate-500 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};

export default Candidates;
