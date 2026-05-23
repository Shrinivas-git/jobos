import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API, getAuthHeaders } from '../utils/api';
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2, List, Plus, Type, Shield, ShieldOff, Globe, Clock, Users, Trash2, Link2 } from 'lucide-react';

const Jobs: React.FC = () => {
  const [mode, setMode] = useState<'upload' | 'form'>('upload');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);
  const [jds, setJds] = useState<any[]>([]);
  const [fetching, setFetching] = useState(true);

  // Form states
  const [title, setTitle] = useState('');
  const [clientEmail, setClientEmail] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  // Structured form states
  const [level, setLevel] = useState('');
  const [responsibilities, setResponsibilities] = useState('');
  const [kpis, setKpis] = useState('');
  const [skills, setSkills] = useState('');
  const [relevantExperience, setRelevantExperience] = useState(0);
  const [totalExperience, setTotalExperience] = useState(0);
  const [compRange, setCompRange] = useState('');
  const [workStructure, setWorkStructure] = useState('In-office');
  const [location, setLocation] = useState('');
  const [timeline, setTimeline] = useState('');
  const [urgency, setUrgency] = useState('Medium');
  const [numPositions, setNumPositions] = useState(1);
  const [obfuscate, setObfuscate] = useState(false);
  const [genderPreference, setGenderPreference] = useState('Any');
  const [collegePreference, setCollegePreference] = useState('');
  const [collegeExclusion, setCollegeExclusion] = useState('');
  const [preferredCompanyType, setPreferredCompanyType] = useState<string[]>([]);
  const [preferredTeamSize, setPreferredTeamSize] = useState('Any');
  const [roleType, setRoleType] = useState('Any');
  const [recruiterNotes, setRecruiterNotes] = useState('');
  const [linkedinJobId, setLinkedinJobId] = useState('');

  const [sourcingJd, setSourcingJd] = useState<string | null>(null);
  const [sourcingCount, setSourcingCount] = useState<Record<string, number>>({});
  const [deletingJd, setDeletingJd] = useState<string | null>(null);
  const [liEditingId, setLiEditingId] = useState<string | null>(null);
  const [liEditValue, setLiEditValue] = useState('');
  const [liSaving, setLiSaving] = useState(false);

  const deleteJd = async (jd_id: string) => {
    if (!window.confirm('Delete this JD? This cannot be undone.')) return;
    setDeletingJd(jd_id);
    try {
      await axios.delete(`${API}/jd/${jd_id}`, { headers: getAuthHeaders() });
      setJds(prev => prev.filter(j => j.jd_id !== jd_id));
    } catch (err) {
      console.error('Delete failed', err);
    } finally {
      setDeletingJd(null);
    }
  };

  const saveLinkedinJobId = async (jd_id: string) => {
    setLiSaving(true);
    try {
      await axios.patch(`${API}/jd/${jd_id}/linkedin-job-id`,
        { linkedin_job_id: liEditValue.trim() || null },
        { headers: getAuthHeaders() }
      );
      setJds(prev => prev.map(j => j.jd_id === jd_id ? { ...j, linkedin_job_id: liEditValue.trim() || null } : j));
      setLiEditingId(null);
    } catch (err) {
      console.error('Failed to save LinkedIn Job ID', err);
    } finally {
      setLiSaving(false);
    }
  };

  const triggerLinkedInSourcing = async (jd_id: string, count: number) => {
    setSourcingJd(jd_id);
    try {
      await axios.post(`${API}/jd/${jd_id}/source-linkedin?limit=${count}`, {}, { headers: getAuthHeaders() });
      await fetchJDs();
    } catch (err) {
      console.error('LinkedIn sourcing failed', err);
    } finally {
      setSourcingJd(null);
    }
  };

  const fetchJDs = async () => {
    try {
      const response = await axios.get(`${API}/jd/`, {
        headers: getAuthHeaders()
      });
      setJds(response.data);
    } catch (err) {
      console.error("Error fetching JDs", err);
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    fetchJDs();
  }, []);

  const resetForm = () => {
    setTitle('');
    setClientEmail('');
    setFile(null);
    setLevel('');
    setResponsibilities('');
    setKpis('');
    setSkills('');
    setRelevantExperience(0);
    setTotalExperience(0);
    setCompRange('');
    setWorkStructure('In-office');
    setLocation('');
    setTimeline('');
    setUrgency('Medium');
    setNumPositions(1);
    setObfuscate(false);
    setGenderPreference('Any');
    setCollegePreference('');
    setCollegeExclusion('');
    setPreferredCompanyType([]);
    setPreferredTeamSize('Any');
    setRoleType('Any');
    setRecruiterNotes('');
    setLinkedinJobId('');
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setStatus(null);

    const formData = new FormData();
    formData.append('title', title);
    formData.append('client_email', clientEmail);
    formData.append('file', file);
    formData.append('num_positions', numPositions.toString());
    formData.append('role_type', roleType);
    preferredCompanyType.forEach(t => formData.append('preferred_company_type', t));
    formData.append('college_preference', collegePreference);
    formData.append('college_exclusion', collegeExclusion);
    if (recruiterNotes.trim()) formData.append('recruiter_notes', recruiterNotes.trim());
    if (linkedinJobId.trim()) formData.append('linkedin_job_id', linkedinJobId.trim());

    try {
      await axios.post(`${API}/jd/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...getAuthHeaders(),
        }
      });
      setStatus({ type: 'success', message: 'Job Description uploaded successfully!' });
      resetForm();
      fetchJDs();
    } catch (err: any) {
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to upload JD' });
    } finally {
      setLoading(false);
    }
  };

  const handleStructuredSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatus(null);

    const payload = {
      title,
      level,
      client_email: clientEmail,
      responsibilities,
      kpis,
      skills: skills.split(',').map(s => s.trim()).filter(s => s),
      relevant_experience: relevantExperience,
      total_experience: totalExperience,
      compensation_range: compRange,
      work_structure: workStructure,
      location,
      hiring_timeline: timeline,
      urgency,
      num_positions: numPositions,
      obfuscate,
      gender_preference: genderPreference,
      college_preference: collegePreference,
      college_exclusion: collegeExclusion,
      preferred_company_type: preferredCompanyType,
      preferred_team_size: preferredTeamSize,
      role_type: roleType,
      ...(recruiterNotes.trim() ? { recruiter_notes: recruiterNotes.trim() } : {}),
      ...(linkedinJobId.trim() ? { linkedin_job_id: linkedinJobId.trim() } : {}),
    };

    try {
      await axios.post(`${API}/jd/create`, payload, {
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        }
      });
      setStatus({ type: 'success', message: 'Structured JD created successfully!' });
      resetForm();
      fetchJDs();
    } catch (err: any) {
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to create JD' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 max-w-[1600px] mx-auto">
      {/* Form Section */}
      <div className="xl:col-span-5 2xl:col-span-4 space-y-6">
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-6 md:p-8 shadow-xl">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-xl font-bold text-white flex items-center">
              <Plus size={20} className="mr-2 text-blue-400" />
              JD Intake
            </h3>
            <div className="bg-slate-900 p-1 rounded-xl border border-slate-800 flex">
              <button
                onClick={() => setMode('upload')}
                className={`px-4 py-2 text-[10px] font-black uppercase tracking-widest rounded-lg transition-all ${mode === 'upload' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
              >
                Upload
              </button>
              <button
                onClick={() => setMode('form')}
                className={`px-4 py-2 text-[10px] font-black uppercase tracking-widest rounded-lg transition-all ${mode === 'form' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
              >
                Direct
              </button>
            </div>
          </div>
          
          <form onSubmit={mode === 'upload' ? handleUploadSubmit : handleStructuredSubmit} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Job Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Senior Backend"
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                  required
                />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Client Email</label>
                <input
                  type="email"
                  value={clientEmail}
                  onChange={(e) => setClientEmail(e.target.value)}
                  placeholder="hr@fidelitus.com"
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                  required
                />
              </div>
            </div>

            {mode === 'upload' ? (
              <div className="space-y-5 animate-in fade-in duration-300">
                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">JD Attachment</label>
                  <div className="relative group">
                    <input
                      type="file"
                      onChange={(e) => setFile(e.target.files?.[0] || null)}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                      required
                    />
                    <div className={`w-full border-2 border-dashed ${file ? 'border-blue-500 bg-blue-500/5' : 'border-slate-700 group-hover:border-slate-600'} rounded-xl p-10 text-center transition-all`}>
                      <FileText size={40} className={`mx-auto mb-3 ${file ? 'text-blue-400' : 'text-slate-600'}`} />
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-tight">
                        {file ? file.name : 'Click or drag PDF/DOCX'}
                      </p>
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Preferred Company Type</label>
                  <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                    {['Fintech', 'Edtech', 'Ecommerce', 'Healthcare', 'Product', 'Services', 'Startup', 'Large Enterprise', 'Any'].map((option) => (
                      <label key={option} className="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={preferredCompanyType.includes(option)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setPreferredCompanyType([...preferredCompanyType, option]);
                            } else {
                              setPreferredCompanyType(preferredCompanyType.filter(t => t !== option));
                            }
                          }}
                          className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-0"
                        />
                        <span className="text-sm text-slate-300">{option}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Preferred Colleges</label>
                    <input
                      type="text"
                      value={collegePreference}
                      onChange={(e) => setCollegePreference(e.target.value)}
                      placeholder="e.g. IIT, NIT, BITS"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Restricted Colleges</label>
                    <input
                      type="text"
                      value={collegeExclusion}
                      onChange={(e) => setCollegeExclusion(e.target.value)}
                      placeholder="e.g. XYZ College"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Positions</label>
                    <input
                      type="number"
                      value={numPositions}
                      onChange={(e) => setNumPositions(parseInt(e.target.value) || 1)}
                      min="1"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Role Type</label>
                    <select
                      value={roleType}
                      onChange={(e) => setRoleType(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    >
                      <option value="Any">Any</option>
                      <option value="Individual Contributor">Individual Contributor</option>
                      <option value="50% IC + 50% Management">50% IC + 50% Management</option>
                      <option value="Team Lead">Team Lead</option>
                    </select>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-5 animate-in slide-in-from-top-2 duration-300">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Role Level</label>
                    <input
                      type="text"
                      value={level}
                      onChange={(e) => setLevel(e.target.value)}
                      placeholder="L3 / Senior"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Relevant Experience (Years)</label>
                    <input
                      type="number"
                      value={relevantExperience}
                      onChange={(e) => setRelevantExperience(parseInt(e.target.value) || 0)}
                      placeholder="Years of relevant domain experience required"
                      min="0"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Total Experience (Years)</label>
                    <input
                      type="number"
                      value={totalExperience}
                      onChange={(e) => setTotalExperience(parseInt(e.target.value) || 0)}
                      placeholder="Total years of work experience required"
                      min="0"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Location</label>
                    <input
                      type="text"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="Bangalore, IN"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Gender Preference</label>
                  <select
                    value={genderPreference}
                    onChange={(e) => setGenderPreference(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                  >
                    <option value="Any">Any</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Preferred Colleges</label>
                  <input
                    type="text"
                    value={collegePreference}
                    onChange={(e) => setCollegePreference(e.target.value)}
                    placeholder="e.g. IIT, NIT, BITS, VTU — leave blank for any"
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Restricted Colleges</label>
                  <input
                    type="text"
                    value={collegeExclusion}
                    onChange={(e) => setCollegeExclusion(e.target.value)}
                    placeholder="e.g. Students from XYZ College should not apply"
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Preferred Company Type</label>
                  <div className="space-y-2">
                    {['Fintech', 'Edtech', 'Ecommerce', 'Healthcare', 'Product', 'Services', 'Startup', 'Large Enterprise', 'Any'].map((option) => (
                      <label key={option} className="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={preferredCompanyType.includes(option)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setPreferredCompanyType([...preferredCompanyType, option]);
                            } else {
                              setPreferredCompanyType(preferredCompanyType.filter(t => t !== option));
                            }
                          }}
                          className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-0"
                        />
                        <span className="text-sm text-slate-300">{option}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Preferred Team Size</label>
                  <select
                    value={preferredTeamSize}
                    onChange={(e) => setPreferredTeamSize(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                  >
                    <option value="Any">Any</option>
                    <option value="Small (1-15)">Small (1-15)</option>
                    <option value="Medium (16-50)">Medium (16-50)</option>
                    <option value="Large (51-200)">Large (51-200)</option>
                    <option value="Enterprise (200+)">Enterprise (200+)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Role Type</label>
                  <select
                    value={roleType}
                    onChange={(e) => setRoleType(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                  >
                    <option value="Any">Any</option>
                    <option value="Individual Contributor">Individual Contributor</option>
                    <option value="50% IC + 50% Management">50% IC + 50% Management</option>
                    <option value="Team Lead">Team Lead</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Key Responsibilities</label>
                  <textarea
                    value={responsibilities}
                    onChange={(e) => setResponsibilities(e.target.value)}
                    rows={3}
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    placeholder="Enter key role expectations..."
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Skills (comma separated)</label>
                  <input
                    type="text"
                    value={skills}
                    onChange={(e) => setSkills(e.target.value)}
                    placeholder="React, TypeScript, Tailwind"
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Compensation</label>
                    <input
                      type="text"
                      value={compRange}
                      onChange={(e) => setCompRange(e.target.value)}
                      placeholder="12-18 LPA"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Work Structure</label>
                    <select
                      value={workStructure}
                      onChange={(e) => setWorkStructure(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors appearance-none"
                    >
                      <option>In-office</option>
                      <option>Hybrid</option>
                      <option>Remote</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Urgency</label>
                    <select
                      value={urgency}
                      onChange={(e) => setUrgency(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors appearance-none"
                    >
                      <option>Low</option>
                      <option>Medium</option>
                      <option>High</option>
                      <option>Critical</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">Positions</label>
                    <input
                      type="number"
                      value={numPositions}
                      onChange={(e) => setNumPositions(parseInt(e.target.value))}
                      min="1"
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                      required
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 bg-slate-900/50 rounded-2xl border border-slate-800">
                  <div className="flex items-center space-x-3">
                    {obfuscate ? <Shield size={18} className="text-blue-400" /> : <ShieldOff size={18} className="text-slate-500" />}
                    <div>
                      <p className="text-[10px] font-black text-white uppercase tracking-widest">Obfuscate Identity</p>
                      <p className="text-[9px] text-slate-500 font-bold uppercase tracking-tight">Hide client name on portals</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setObfuscate(!obfuscate)}
                    className={`w-12 h-6 rounded-full transition-all relative ${obfuscate ? 'bg-blue-600' : 'bg-slate-700'}`}
                  >
                    <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-all ${obfuscate ? 'left-7' : 'left-1'}`} />
                  </button>
                </div>
              </div>
            )}

            {/* LinkedIn Job ID — shared between Upload and Direct tabs */}
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">
                LinkedIn Job ID <span className="text-slate-500 normal-case font-normal">(Optional)</span>
              </label>
              <input
                type="text"
                value={linkedinJobId}
                onChange={(e) => setLinkedinJobId(e.target.value)}
                placeholder="e.g. 4227631788 — paste from LinkedIn job URL"
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Recruiter Notes — shared between Upload and Direct tabs */}
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 ml-1">
                Recruiter Notes <span className="text-slate-500 normal-case font-normal">(Optional)</span>
              </label>
              <textarea
                value={recruiterNotes}
                onChange={(e) => setRecruiterNotes(e.target.value)}
                rows={3}
                placeholder="Describe the ideal candidate in your own words — personality, specific expectations, deal-breakers, or anything the JD doesn't capture..."
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors resize-none placeholder-slate-600"
              />
            </div>

            {status && (
              <div className={`p-4 rounded-xl flex items-center space-x-3 ${status.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                {status.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                <p className="text-xs font-bold uppercase tracking-tight">{status.message}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white font-bold py-4 rounded-xl transition-all shadow-lg shadow-blue-500/20 flex items-center justify-center space-x-2 active:scale-[0.98]"
            >
              {loading ? <Loader2 size={18} className="animate-spin" /> : (mode === 'upload' ? <Upload size={18} /> : <CheckCircle2 size={18} />)}
              <span>{loading ? 'Ingesting...' : (mode === 'upload' ? 'Upload JD' : 'Create JD')}</span>
            </button>
          </form>
        </div>
      </div>

      {/* JD List Section */}
      <div className="xl:col-span-7 2xl:col-span-8 space-y-6">
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-3xl p-6 md:p-8 shadow-xl min-h-[600px] flex flex-col">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-xl font-bold text-white flex items-center">
              <List size={20} className="mr-2 text-blue-400" />
              Active Job Requirements
            </h3>
            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest bg-slate-900 px-3 py-1 rounded-full border border-slate-800">
              {jds.filter((jd: any) => (jd.num_positions || 1) > (jd.joined_count || 0)).length} Active
            </span>
          </div>

          {fetching ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="animate-spin text-blue-500" size={32} />
            </div>
          ) : jds.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center">
              <div className="bg-slate-900/50 p-8 rounded-full mb-4">
                <Briefcase size={56} className="text-slate-700" />
              </div>
              <p className="text-slate-400 font-medium max-w-xs">No job descriptions found. Start by uploading one or check the email intake address.</p>
            </div>
          ) : (() => {
            const isFilled = (jd: any) => (jd.num_positions || 1) <= (jd.joined_count || 0);
            const activeJds = jds.filter(jd => !isFilled(jd));
            const filledJds = jds.filter(jd => isFilled(jd));

            const renderCard = (jd: any, i: number) => {
              const filled = isFilled(jd);
              return (
                <div key={i} className={`flex flex-col p-6 rounded-2xl border transition-all group relative overflow-hidden ${filled ? 'bg-slate-900/20 border-slate-800/30 opacity-75' : 'bg-slate-900/40 border-slate-800/50 hover:border-slate-700'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className={`p-3 rounded-xl border ${filled ? 'bg-slate-800/50 text-slate-500 border-slate-700/50' : 'bg-slate-800 text-blue-400 border-slate-700'}`}>
                      <FileText size={20} />
                    </div>
                    <div className="flex items-center gap-2">
                      {filled && (
                        <span className="text-[9px] font-black uppercase tracking-widest px-3 py-1 rounded-full border text-emerald-400 border-emerald-500/30 bg-emerald-500/10">
                          ✓ Filled
                        </span>
                      )}
                      <div className={`text-[9px] font-black uppercase tracking-widest px-3 py-1 rounded-full border ${
                        jd.status === 'received' ? 'text-blue-400 border-blue-500/20 bg-blue-500/5' : 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5'
                      }`}>
                        {jd.status}
                      </div>
                      <button
                        onClick={() => deleteJd(jd.jd_id)}
                        disabled={deletingJd === jd.jd_id}
                        className="p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Delete JD"
                      >
                        {deletingJd === jd.jd_id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                      </button>
                    </div>
                  </div>

                  <h5 className={`font-bold mb-2 truncate pr-4 ${filled ? 'text-slate-400' : 'text-white group-hover:text-blue-400'} transition-colors`}>{jd.title}</h5>

                  {/* Positions progress */}
                  {jd.num_positions && (
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${filled ? 'bg-emerald-500' : 'bg-blue-500'}`}
                          style={{ width: `${Math.min(100, ((jd.joined_count || 0) / jd.num_positions) * 100)}%` }}
                        />
                      </div>
                      <span className="text-[9px] text-slate-400 font-bold shrink-0">{jd.joined_count || 0}/{jd.num_positions} joined</span>
                    </div>
                  )}

                  {jd.quality_flag && (
                    <div className="flex items-center space-x-1.5 px-3 py-1.5 bg-yellow-500/10 border border-yellow-500/30 rounded-lg mt-2 mb-2">
                      <span className="text-yellow-400 text-xs font-bold">⚠ Review JD — {jd.quality_flag}</span>
                    </div>
                  )}


                  {/* LinkedIn Job ID inline edit */}
                  <div className="mt-2 mb-2">
                    {liEditingId === jd.jd_id ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={liEditValue}
                          onChange={e => setLiEditValue(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') saveLinkedinJobId(jd.jd_id); if (e.key === 'Escape') setLiEditingId(null); }}
                          placeholder="e.g. 4227631788"
                          autoFocus
                          className="flex-1 bg-slate-900 border border-blue-500/50 rounded-lg px-2 py-1 text-xs text-white focus:outline-none"
                        />
                        <button onClick={() => saveLinkedinJobId(jd.jd_id)} disabled={liSaving} className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-2 py-1 rounded-lg font-bold">
                          {liSaving ? '...' : 'Save'}
                        </button>
                        <button onClick={() => setLiEditingId(null)} className="text-xs text-slate-500 hover:text-slate-300 px-1">✕</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setLiEditingId(jd.jd_id); setLiEditValue(jd.linkedin_job_id || ''); }}
                        className={`flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest px-2 py-1 rounded-lg border transition-colors ${jd.linkedin_job_id ? 'text-blue-400 border-blue-500/30 bg-blue-500/5 hover:bg-blue-500/10' : 'text-slate-400 border-slate-600 hover:text-white hover:border-slate-500'}`}
                      >
                        <Link2 size={10} />
                        {jd.linkedin_job_id ? jd.linkedin_job_id : 'Set LinkedIn Job ID'}
                      </button>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2 mt-auto">
                    <div className="flex items-center space-x-1.5 bg-slate-900 px-2 py-1 rounded-lg border border-slate-800">
                      <span className="text-[9px] font-black text-slate-500 uppercase">{jd.jd_id}</span>
                    </div>
                    <div className="flex items-center space-x-1.5 bg-slate-900 px-2 py-1 rounded-lg border border-slate-800">
                      {jd.source.includes('structured') ? <Type size={10} className="text-emerald-400" /> : <Upload size={10} className="text-blue-400" />}
                      <span className="text-[9px] font-bold text-slate-400 uppercase tracking-tight">
                        {jd.source.split('_').pop()}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1.5 bg-slate-900 px-2 py-1 rounded-lg border border-slate-800 ml-auto">
                      <Clock size={10} className="text-slate-500" />
                      <span className="text-[9px] text-slate-500 font-bold">
                        {new Date(jd.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  {jd.structured_data?.obfuscate && (
                    <div className="absolute top-2 right-12">
                      <Shield size={12} className="text-blue-500/50" />
                    </div>
                  )}
                </div>
              );
            };

            return (
              <div className="space-y-6">
                {/* Active JDs */}
                {activeJds.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {activeJds.map((jd, i) => renderCard(jd, i))}
                  </div>
                )}

                {/* Filled JDs */}
                {filledJds.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="h-px flex-1 bg-slate-700/50" />
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Filled Positions ({filledJds.length})</span>
                      <div className="h-px flex-1 bg-slate-700/50" />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {filledJds.map((jd, i) => renderCard(jd, i))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
};

// Placeholder icons missing from lucide-react if any
const Briefcase = ({ size, className }: any) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
  </svg>
);

export default Jobs;
