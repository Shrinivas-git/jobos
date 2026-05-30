import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CheckCircle, XCircle } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || '/api';

interface OfferDetails {
  jd_id: string;
  jd_title: string;
  candidate_id: string;
  candidate_name: string;
  joining_date: string | null;
  already_responded: boolean;
  candidate_response: {
    response: string;
    reason: string | null;
    preferred_joining_date: string | null;
    responded_at: string;
  } | null;
}

const OfferResponse: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [offer, setOffer] = useState<OfferDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<'accept' | 'reject' | null>(null);
  const [postponeNote, setPostponeNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API}/pipeline/offer-response/${token}`);
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail ?? `HTTP ${res.status}`);
        }
        const data: OfferDetails = await res.json();
        setOffer(data);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    if (token) load();
  }, [token]);

  const handleSubmit = async () => {
    if (!selected || !token) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch(`${API}/pipeline/offer-response/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          response: selected,
          reason: selected === 'reject' ? (postponeNote.trim() || 'Candidate chose postpone/not interested') : null,
          preferred_joining_date: null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail ?? `HTTP ${res.status}`);
      }
      setSubmitted(true);
    } catch (e: any) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-6">
        <div className="bg-[#1e293b] border border-red-500/20 rounded-2xl p-8 max-w-md w-full text-center">
          <XCircle size={40} className="text-red-400 mx-auto mb-4" />
          <h2 className="text-white font-bold text-lg mb-2">Link Not Found</h2>
          <p className="text-slate-400 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!offer) return null;

  const alreadyResponded = offer.already_responded || submitted;
  const responseLabel = submitted ? selected : offer.candidate_response?.response;

  return (
    <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-6 font-sans">
      <div className="max-w-lg w-full space-y-4">
        {/* Header */}
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-6">
          <p className="text-blue-400 font-bold text-xl mb-1">JobOS</p>
          <p className="text-slate-400 text-xs uppercase tracking-widest">Offer Letter</p>
        </div>

        {/* Offer details */}
        <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-6 space-y-3">
          <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Position</p>
            <p className="text-white font-bold text-lg">{offer.jd_title}</p>
          </div>
          <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Candidate</p>
            <p className="text-slate-200 text-sm">{offer.candidate_name}</p>
          </div>
          {offer.joining_date && (
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Proposed Joining Date</p>
              <p className="text-slate-200 text-sm">{offer.joining_date}</p>
            </div>
          )}
        </div>

        {/* Response section */}
        {alreadyResponded ? (
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-6 text-center">
            {responseLabel === 'accept' ? (
              <>
                <CheckCircle size={40} className="text-emerald-400 mx-auto mb-3" />
                <p className="font-bold text-lg text-emerald-400">Agreed to Join</p>
                <p className="text-slate-400 text-sm mt-2">Thank you! Our recruiter will reach out with next steps shortly.</p>
              </>
            ) : (
              <>
                <XCircle size={40} className="text-slate-400 mx-auto mb-3" />
                <p className="font-bold text-lg text-slate-300">Response Recorded</p>
                <p className="text-slate-400 text-sm mt-2">Thank you for letting us know. Our recruiter will be in touch.</p>
              </>
            )}
          </div>
        ) : (
          <div className="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-6 space-y-4">
            <p className="text-[10px] text-slate-500 uppercase tracking-widest">Your Response</p>

            {/* Two choice buttons */}
            <div className="grid grid-cols-1 gap-3">
              <button
                onClick={() => setSelected('accept')}
                className={`py-4 rounded-xl border font-bold text-sm transition-all text-left px-5 ${
                  selected === 'accept'
                    ? 'border-emerald-500 bg-emerald-500/20 text-emerald-300 ring-2 ring-emerald-500/30'
                    : 'border-emerald-500/30 bg-emerald-500/5 text-emerald-400 hover:bg-emerald-500/15'
                }`}
              >
                <div className="flex items-center gap-3">
                  <CheckCircle size={18} />
                  <div>
                    <p className="font-bold">I agree to the joining date</p>
                    <p className="text-xs font-normal opacity-70 mt-0.5">I confirm I will join on the proposed date</p>
                  </div>
                </div>
              </button>

              <button
                onClick={() => setSelected('reject')}
                className={`py-4 rounded-xl border font-bold text-sm transition-all text-left px-5 ${
                  selected === 'reject'
                    ? 'border-red-500 bg-red-500/20 text-red-300 ring-2 ring-red-500/30'
                    : 'border-red-500/30 bg-red-500/5 text-red-400 hover:bg-red-500/15'
                }`}
              >
                <div className="flex items-center gap-3">
                  <XCircle size={18} />
                  <div>
                    <p className="font-bold">Postpone / Not interested</p>
                    <p className="text-xs font-normal opacity-70 mt-0.5">I need to postpone or I am not available to join</p>
                  </div>
                </div>
              </button>
            </div>

            {/* Optional note for postpone/not interested */}
            {selected === 'reject' && (
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">
                  Note <span className="text-slate-500">(optional — let us know your situation)</span>
                </label>
                <textarea
                  rows={3}
                  value={postponeNote}
                  onChange={e => setPostponeNote(e.target.value)}
                  placeholder="e.g. I need more time, I have another offer, family reasons..."
                  className="w-full bg-slate-900/50 border border-slate-700/50 text-white text-sm rounded-xl px-4 py-3 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
            )}

            {submitError && (
              <p className="text-xs text-red-400">{submitError}</p>
            )}

            <button
              onClick={handleSubmit}
              disabled={!selected || submitting}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-bold text-sm rounded-xl transition-colors"
            >
              {submitting ? 'Submitting…' : 'Confirm My Response'}
            </button>
          </div>
        )}

        <p className="text-center text-[11px] text-slate-600">
          JobOS · Recruitment Operating System · This link is unique to you
        </p>
      </div>
    </div>
  );
};

export default OfferResponse;
