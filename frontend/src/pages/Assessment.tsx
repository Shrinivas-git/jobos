import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Question {
  id: number;
  question: string;
}

interface AssessmentData {
  assessment_id: string;
  jd_title: string;
  status: string;
  questions: Question[];
}

const Assessment: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<AssessmentData | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/assessments/${id}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 404 ? 'Assessment not found.' : `Error ${res.status}`);
        return res.json();
      })
      .then((d: AssessmentData) => {
        setData(d);
        setAnswers(Array(d.questions.length).fill(''));
        if (d.status === 'completed') setSubmitted(true);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSubmit = async () => {
    if (!data || submitting) return;
    if (answers.some((a) => !a.trim())) {
      setError('Please answer all questions before submitting.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API}/assessments/${id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Submission failed (${res.status})`);
      }
      const result = await res.json();
      setScore(result.score ?? null);
      setSubmitted(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const allAnswered = answers.length > 0 && answers.every((a) => a.trim().length > 0);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 max-w-md w-full text-center">
          <p className="text-red-400 text-lg font-semibold mb-2">Unable to load assessment</p>
          <p className="text-slate-400 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-10 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="text-white text-2xl font-bold mb-2">
            {score !== null ? 'Assessment Submitted' : 'Already Completed'}
          </h1>
          {score !== null && (
            <div className="my-6">
              <p className="text-slate-400 text-sm mb-1">Your score</p>
              <p className="text-5xl font-bold text-blue-400">{score}<span className="text-2xl text-slate-500">/100</span></p>
            </div>
          )}
          <p className="text-slate-400 text-sm leading-relaxed">
            Thank you for completing the assessment for <span className="text-white font-medium">{data?.jd_title}</span>.
            Our recruitment team will review your results and be in touch.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 mb-6">
          <p className="text-blue-400 font-bold text-lg mb-1">JobOS</p>
          <h1 className="text-white text-xl font-semibold">{data?.jd_title}</h1>
          <p className="text-slate-400 text-sm mt-1">Skill Assessment · {data?.questions.length} questions · ~15 minutes</p>
        </div>

        <p className="text-slate-400 text-sm mb-6 leading-relaxed">
          Please answer each question thoughtfully. There are no trick questions — we're looking for practical understanding.
          Write as much or as little as you need to answer well.
        </p>

        {/* Questions */}
        <div className="space-y-6">
          {data?.questions.map((q, idx) => (
            <div key={q.id} className="bg-slate-800 border border-slate-700 rounded-xl p-6">
              <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-3">
                Question {idx + 1} of {data.questions.length}
              </p>
              <p className="text-white font-medium mb-4 leading-relaxed">{q.question}</p>
              <textarea
                rows={5}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-slate-200 text-sm
                           placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-y"
                placeholder="Type your answer here..."
                value={answers[idx] || ''}
                onChange={(e) => {
                  const updated = [...answers];
                  updated[idx] = e.target.value;
                  setAnswers(updated);
                }}
              />
            </div>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 bg-red-900/20 border border-red-500/40 rounded-lg px-4 py-3">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Submit */}
        <div className="mt-8 flex items-center justify-between">
          <p className="text-slate-500 text-sm">
            {answers.filter((a) => a.trim()).length} / {data?.questions.length} answered
          </p>
          <button
            onClick={handleSubmit}
            disabled={!allAnswered || submitting}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500
                       text-white font-semibold px-8 py-3 rounded-lg transition-colors"
          >
            {submitting ? 'Submitting…' : 'Submit Assessment'}
          </button>
        </div>

        <p className="text-center text-slate-600 text-xs mt-8">
          JobOS · Recruitment Operating System
        </p>
      </div>
    </div>
  );
};

export default Assessment;
