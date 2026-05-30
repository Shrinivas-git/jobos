import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ShieldCheck, Upload, CheckCircle, Loader } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || '/api';

const CandidateForm: React.FC = () => {
  const { jdId, candidateId } = useParams<{ jdId: string; candidateId?: string }>();
  const [searchParams] = useSearchParams();
  const source = searchParams.get('source') || 'direct';

  // Open mode = no candidateId in URL (came from Indeed, Internshala, etc.)
  const isOpenMode = !candidateId;

  const [jdTitle, setJdTitle] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);

  // Open mode fields
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [linkedin, setLinkedin] = useState('');
  const [currentCtc, setCurrentCtc] = useState('');
  const [expectedCtc, setExpectedCtc] = useState('');
  const [noticePeriod, setNoticePeriod] = useState('');

  // Existing candidate mode fields
  const [aadhar, setAadhar] = useState('');
  const [telegram, setTelegram] = useState('');
  const [candidateResumeFile, setCandidateResumeFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const promises: Promise<any>[] = [
          fetch(`${API}/jd/${jdId}/public`),
        ];
        if (!isOpenMode && candidateId) {
          promises.push(fetch(`${API}/candidates/${candidateId}/public`));
          promises.push(fetch(`${API}/forms/response/${jdId}/${candidateId}/public`));
        }
        const [jdRes, candRes, formRes] = await Promise.all(promises);

        if (jdRes?.ok) {
          const j = await jdRes.json();
          setJdTitle(j.title || jdId);
        }
        if (candRes?.ok) {
          const c = await candRes.json();
          setCandidateName(c.name || candidateId || '');
        }
        if (formRes?.ok) {
          setAlreadySubmitted(true);
        }
      } catch {
        // non-critical
      } finally {
        setLoading(false);
      }
    };
    fetchInfo();
  }, [jdId, candidateId, isOpenMode]);

  const handleOpenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError('Full name is required.'); return; }
    if (!email.trim()) { setError('Email is required.'); return; }
    if (!phone.trim()) { setError('Phone number is required.'); return; }
    if (!resumeFile) { setError('Please upload your resume.'); return; }

    setSubmitting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('jd_id', jdId!);
      formData.append('name', name.trim());
      formData.append('email', email.trim());
      formData.append('phone', phone.trim());
      formData.append('source', source);
      formData.append('resume_file', resumeFile);
      if (linkedin.trim()) formData.append('linkedin_url', linkedin.trim());
      if (currentCtc.trim()) formData.append('current_ctc', currentCtc.trim());
      if (expectedCtc.trim()) formData.append('expected_ctc', expectedCtc.trim());
      if (noticePeriod) formData.append('notice_period', noticePeriod);

      const res = await fetch(`${API}/forms/open-submit`, { method: 'POST', body: formData });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleExistingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!aadhar.trim()) { setError('Aadhar number is required.'); return; }
    if (!email.trim()) { setError('Email is required.'); return; }
    if (!candidateResumeFile) { setError('Please upload your resume.'); return; }

    setSubmitting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('jd_id', jdId!);
      formData.append('candidate_id', candidateId!);
      formData.append('aadhar', aadhar.trim());
      formData.append('email', email.trim());
      formData.append('resume_file', candidateResumeFile!);
      if (linkedin.trim()) formData.append('linkedin_url', linkedin.trim());
      if (phone.trim()) formData.append('alternate_phone', phone.trim());
      if (telegram.trim()) formData.append('telegram_handle', telegram.trim());
      if (videoFile) formData.append('video_file', videoFile);

      const res = await fetch(`${API}/forms/submit`, { method: 'POST', body: formData });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <Loader className="animate-spin text-blue-400" size={32} />
      </div>
    );
  }

  if (alreadySubmitted) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-6">
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 max-w-md w-full text-center">
          <CheckCircle className="text-emerald-400 mx-auto mb-4" size={48} />
          <h2 className="text-xl font-bold text-white mb-2">Already Submitted</h2>
          <p className="text-slate-400 text-sm">You have already submitted your application for this role. We will be in touch!</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-6">
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-8 max-w-md w-full text-center">
          <CheckCircle className="text-emerald-400 mx-auto mb-4" size={48} />
          <h2 className="text-xl font-bold text-white mb-2">Application Submitted!</h2>
          <p className="text-slate-400 text-sm">
            Thank you{name || candidateName ? `, ${name || candidateName}` : ''}! Your application has been received. Our team will reach out soon.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f172a] py-12 px-4">
      <div className="max-w-lg mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <div className="bg-blue-600 p-2 rounded-xl">
            <ShieldCheck className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white leading-none">JobOS</h1>
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">
              {isOpenMode ? 'Apply Now' : 'Video Resume Form'}
            </p>
          </div>
        </div>

        <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-6">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-white">{jdTitle || jdId}</h2>
            {!isOpenMode && candidateName && (
              <p className="text-sm text-slate-400 mt-1">Hi {candidateName}, please complete the form below.</p>
            )}
            {isOpenMode && (
              <p className="text-sm text-slate-400 mt-1">Fill in your details and upload your resume to apply.</p>
            )}
          </div>

          {isOpenMode ? (
            /* ── Open form — for external candidates (Indeed, Internshala etc.) ── */
            <form onSubmit={handleOpenSubmit} className="space-y-5">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Full Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your full name"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Email <span className="text-red-400">*</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Phone Number <span className="text-red-400">*</span>
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={e => setPhone(e.target.value)}
                  placeholder="+91 XXXXX XXXXX"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">LinkedIn Profile URL</label>
                <input
                  type="url"
                  value={linkedin}
                  onChange={e => setLinkedin(e.target.value)}
                  placeholder="https://linkedin.com/in/yourname"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Current CTC (LPA)</label>
                  <input
                    type="text"
                    value={currentCtc}
                    onChange={e => setCurrentCtc(e.target.value)}
                    placeholder="e.g. 6"
                    className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Expected CTC (LPA)</label>
                  <input
                    type="text"
                    value={expectedCtc}
                    onChange={e => setExpectedCtc(e.target.value)}
                    placeholder="e.g. 9"
                    className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Notice Period</label>
                <select
                  value={noticePeriod}
                  onChange={e => setNoticePeriod(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="">Select notice period</option>
                  <option value="Immediate">Immediate</option>
                  <option value="15 days">15 days</option>
                  <option value="30 days">30 days</option>
                  <option value="60 days">60 days</option>
                  <option value="90 days">90 days</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Resume (PDF/DOCX, max 5MB) <span className="text-red-400">*</span>
                </label>
                <label className="flex flex-col items-center justify-center gap-2 w-full h-32 bg-slate-900 border-2 border-dashed border-slate-700 rounded-xl cursor-pointer hover:border-blue-500 transition-colors">
                  <Upload size={20} className="text-slate-500" />
                  <span className="text-sm text-slate-400">
                    {resumeFile ? resumeFile.name : 'Click to upload resume'}
                  </span>
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx,application/pdf,application/msword"
                    className="hidden"
                    onChange={e => setResumeFile(e.target.files?.[0] || null)}
                  />
                </label>
              </div>

              {error && (
                <div className="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-300">{error}</div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                {submitting ? <><Loader size={16} className="animate-spin" /> Submitting...</> : 'Submit Application'}
              </button>
            </form>
          ) : (
            /* ── Existing candidate form — shortlisted candidates with video ── */
            <form onSubmit={handleExistingSubmit} className="space-y-5">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Aadhar Number <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={aadhar}
                  onChange={e => setAadhar(e.target.value)}
                  placeholder="12-digit Aadhar number"
                  maxLength={14}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">LinkedIn Profile URL</label>
                <input
                  type="url"
                  value={linkedin}
                  onChange={e => setLinkedin(e.target.value)}
                  placeholder="https://linkedin.com/in/yourname"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Alternate Phone Number</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={e => setPhone(e.target.value)}
                  placeholder="+91 XXXXX XXXXX"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Email <span className="text-red-400">*</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">Telegram Handle (optional)</label>
                <input
                  type="text"
                  value={telegram}
                  onChange={e => setTelegram(e.target.value)}
                  placeholder="@yourusername"
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Resume (PDF/DOCX) <span className="text-red-400">*</span>
                </label>
                <label className="flex flex-col items-center justify-center gap-2 w-full h-32 bg-slate-900 border-2 border-dashed border-slate-700 rounded-xl cursor-pointer hover:border-blue-500 transition-colors">
                  <Upload size={20} className="text-slate-500" />
                  <span className="text-sm text-slate-400">
                    {candidateResumeFile ? candidateResumeFile.name : 'Click to upload resume'}
                  </span>
                  <input
                    type="file"
                    accept=".pdf,.doc,.docx,application/pdf,application/msword"
                    className="hidden"
                    onChange={e => setCandidateResumeFile(e.target.files?.[0] || null)}
                  />
                </label>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">
                  Video Resume (MP4, max 5 min)
                </label>
                <label className="flex flex-col items-center justify-center gap-2 w-full h-32 bg-slate-900 border-2 border-dashed border-slate-700 rounded-xl cursor-pointer hover:border-blue-500 transition-colors">
                  <Upload size={20} className="text-slate-500" />
                  <span className="text-sm text-slate-400">
                    {videoFile ? videoFile.name : 'Click to upload video'}
                  </span>
                  <input
                    type="file"
                    accept="video/mp4,video/*"
                    className="hidden"
                    onChange={e => setVideoFile(e.target.files?.[0] || null)}
                  />
                </label>
              </div>

              {error && (
                <div className="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-300">{error}</div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                {submitting ? <><Loader size={16} className="animate-spin" /> Submitting...</> : 'Submit Form'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default CandidateForm;
