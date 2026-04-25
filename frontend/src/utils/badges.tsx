import React from 'react';

export const recommendationBadge = (rec?: string): React.ReactElement | null => {
  if (!rec) return null;
  const map: Record<string, { label: string; cls: string }> = {
    shortlist: { label: 'Shortlist', cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
    hold:      { label: 'Hold',      cls: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
    reject:    { label: 'Reject',    cls: 'bg-red-500/20 text-red-400 border-red-500/30' },
  };
  const style = map[rec] ?? { label: rec, cls: 'bg-slate-500/20 text-slate-400 border-slate-500/30' };
  return (
    <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border ${style.cls}`}>
      {style.label}
    </span>
  );
};
