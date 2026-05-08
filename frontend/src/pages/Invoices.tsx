import React, { useEffect, useState } from 'react';
import { API, getAuthHeaders } from '../utils/api';
import { CheckCircle, Clock, Filter, RefreshCw } from 'lucide-react';

interface Invoice {
  invoice_id: string;
  jd_id: string;
  candidate_id: string;
  candidate_name: string;
  jd_title: string;
  client_email: string;
  amount: number;
  placement_date: string;
  generated_at: string;
  sent_at: string | null;
  email_status: string;
  payment_status: string | null;
  paid_at: string | null;
}

const fmt = (iso: string | null) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
};

const Invoices: React.FC = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'unpaid' | 'paid'>('all');
  const [updating, setUpdating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const url = filter === 'all' ? `${API}/invoices/` : `${API}/invoices/?status=${filter}`;
      const r = await fetch(url, { headers: getAuthHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setInvoices(await r.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filter]);

  const markPaid = async (invoice_id: string) => {
    setUpdating(invoice_id);
    try {
      const r = await fetch(`${API}/invoices/${invoice_id}/mark-paid`, {
        method: 'PATCH',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setInvoices(prev => prev.map(inv =>
        inv.invoice_id === invoice_id ? { ...inv, payment_status: 'paid', paid_at: new Date().toISOString() } : inv
      ));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUpdating(null);
    }
  };

  const markUnpaid = async (invoice_id: string) => {
    setUpdating(invoice_id);
    try {
      const r = await fetch(`${API}/invoices/${invoice_id}/mark-unpaid`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setInvoices(prev => prev.map(inv =>
        inv.invoice_id === invoice_id ? { ...inv, payment_status: 'unpaid', paid_at: null } : inv
      ));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUpdating(null);
    }
  };

  const totalAmount = invoices.reduce((s, i) => s + (i.amount || 0), 0);
  const paidAmount = invoices.filter(i => i.payment_status === 'paid').reduce((s, i) => s + (i.amount || 0), 0);
  const unpaidAmount = invoices.filter(i => i.payment_status !== 'paid').reduce((s, i) => s + (i.amount || 0), 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Invoices</h1>
          <p className="text-sm text-slate-400 mt-0.5">Track all placement invoices and payment status</p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-2 bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg border border-slate-600/50 transition-colors">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Invoiced', value: `₹${totalAmount.toLocaleString('en-IN')}`, color: 'text-white' },
          { label: 'Collected', value: `₹${paidAmount.toLocaleString('en-IN')}`, color: 'text-emerald-400' },
          { label: 'Pending', value: `₹${unpaidAmount.toLocaleString('en-IN')}`, color: 'text-red-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-800/40 border border-slate-700/50 rounded-2xl px-5 py-4">
            <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">{label}</p>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <Filter size={14} className="text-slate-400" />
        {(['all', 'unpaid', 'paid'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg capitalize transition-colors ${
              filter === f ? 'bg-blue-600 text-white' : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'
            }`}
          >
            {f === 'all' ? 'All' : f === 'unpaid' ? 'Unpaid' : 'Paid'}
          </button>
        ))}
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {loading ? (
        <div className="text-center py-16 text-slate-400">Loading...</div>
      ) : invoices.length === 0 ? (
        <div className="text-center py-16 text-slate-500">No invoices found</div>
      ) : (
        <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700/50">
                {['Candidate', 'Role', 'Client', 'Amount', 'Sent', 'Paid On', 'Status', 'Action'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-bold text-slate-400 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => {
                const isPaid = inv.payment_status === 'paid';
                const sentDate = inv.sent_at ? new Date(inv.sent_at) : null;
                const daysAgo = sentDate ? Math.floor((Date.now() - sentDate.getTime()) / 86400000) : null;
                const isOverdue = !isPaid && daysAgo !== null && daysAgo >= 30;
                return (
                  <tr key={inv.invoice_id} className="border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors">
                    <td className="px-4 py-3">
                      <p className="text-sm font-semibold text-white">{inv.candidate_name}</p>
                      <p className="text-[10px] text-slate-500">{inv.candidate_id}</p>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-300">{inv.jd_title}</td>
                    <td className="px-4 py-3 text-sm text-slate-400">{inv.client_email}</td>
                    <td className="px-4 py-3 text-sm font-bold text-white">₹{(inv.amount || 0).toLocaleString('en-IN')}</td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-slate-300">{fmt(inv.sent_at)}</p>
                      {isOverdue && <p className="text-[10px] text-red-400 font-bold">{daysAgo}d overdue</p>}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-400">{fmt(inv.paid_at)}</td>
                    <td className="px-4 py-3">
                      {isPaid ? (
                        <span className="flex items-center gap-1 px-2 py-1 bg-emerald-500/15 text-emerald-400 text-[10px] font-bold rounded-lg w-fit">
                          <CheckCircle size={10} /> Paid
                        </span>
                      ) : (
                        <span className={`flex items-center gap-1 px-2 py-1 text-[10px] font-bold rounded-lg w-fit ${isOverdue ? 'bg-red-500/15 text-red-400' : 'bg-yellow-500/15 text-yellow-400'}`}>
                          <Clock size={10} /> {isOverdue ? 'Overdue' : 'Unpaid'}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {isPaid ? (
                        <button
                          disabled={updating === inv.invoice_id}
                          onClick={() => markUnpaid(inv.invoice_id)}
                          className="px-3 py-1.5 text-[10px] font-bold bg-slate-700/50 hover:bg-slate-700 text-slate-400 rounded-lg transition-colors disabled:opacity-40"
                        >
                          {updating === inv.invoice_id ? '...' : 'Mark Unpaid'}
                        </button>
                      ) : (
                        <button
                          disabled={updating === inv.invoice_id}
                          onClick={() => markPaid(inv.invoice_id)}
                          className="px-3 py-1.5 text-[10px] font-bold bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 rounded-lg border border-emerald-500/20 transition-colors disabled:opacity-40"
                        >
                          {updating === inv.invoice_id ? '...' : 'Mark Paid'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Invoices;
