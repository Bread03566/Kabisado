import React, { useCallback, useEffect, useState } from 'react';
import { ShieldCheck, Search, UserX, UserCheck } from 'lucide-react';
import { getAdminAudit, getAdminOverview, getAdminStudents, setStudentActive } from '../services/api';

const STATS = [
  ['students', 'Students'],
  ['active_students', 'Active'],
  ['disabled_students', 'Deactivated'],
  ['documents', 'Modules'],
  ['flashcards', 'Flashcards'],
  ['questions', 'Questions'],
  ['quiz_attempts', 'Quiz attempts'],
];

// The API sends UTC timestamps without a zone suffix.
const fmt = (iso) => (iso ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleString() : 'Never');

export default function AdminView({ showToast }) {
  const [overview, setOverview] = useState(null);
  const [students, setStudents] = useState([]);
  const [audit, setAudit] = useState([]);
  const [query, setQuery] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async (q) => {
    try {
      const [o, s, a] = await Promise.all([getAdminOverview(), getAdminStudents(q), getAdminAudit()]);
      setOverview(o);
      setStudents(s.students);
      setAudit(a.entries);
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(query), 300); // let typing settle before asking the server
    return () => clearTimeout(t);
  }, [query, load]);

  const toggle = async (student) => {
    const next = !student.is_active;
    if (!next && !window.confirm(`Deactivate ${student.display_name} (@${student.username})? They will be signed out everywhere and cannot log in until you reactivate them.`)) return;
    setBusyId(student.id);
    try {
      await setStudentActive(student.id, next);
      showToast?.('success', next ? 'Account reactivated.' : 'Account deactivated.');
      await load(query);
    } catch (e) {
      showToast?.('error', e.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      <div className="flex items-center gap-2">
        <ShieldCheck className="w-6 h-6 text-amber-600" />
        <h1 className="text-xl font-extrabold text-slate-900">Admin</h1>
      </div>

      {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      <section aria-label="Overview" className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {STATS.map(([key, label]) => (
          <div key={key} className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-2xl font-extrabold text-slate-900">{overview ? overview[key] : '–'}</p>
            <p className="text-xs font-semibold text-slate-500">{label}</p>
          </div>
        ))}
      </section>

      <section aria-label="Students" className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
          <h2 className="text-sm font-extrabold text-slate-900">Students</h2>
          <label className="relative block w-full sm:w-72">
            <span className="sr-only">Search students by username or name</span>
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={60}
              placeholder="Search username or name"
              className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
          </label>
        </div>
        <p className="text-xs text-slate-500 mb-3">Account details only. Study content is never shown here.</p>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-2 pr-3 font-semibold">Name</th>
                <th className="py-2 pr-3 font-semibold">Username</th>
                <th className="py-2 pr-3 font-semibold">Modules</th>
                <th className="py-2 pr-3 font-semibold">Last login</th>
                <th className="py-2 pr-3 font-semibold">Status</th>
                <th className="py-2 font-semibold"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id} className="border-t border-slate-100">
                  <td className="py-2 pr-3 font-semibold text-slate-800" translate="no">{s.display_name}</td>
                  <td className="py-2 pr-3 text-slate-600" translate="no">@{s.username}</td>
                  <td className="py-2 pr-3 text-slate-600">{s.document_count}</td>
                  <td className="py-2 pr-3 text-slate-600 whitespace-nowrap">{fmt(s.last_login_at)}</td>
                  <td className="py-2 pr-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${s.role === 'admin' ? 'bg-sky-100 text-sky-800' : s.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}`}>
                      {s.role === 'admin' ? 'Admin' : s.is_active ? 'Active' : 'Deactivated'}
                    </span>
                  </td>
                  <td className="py-2 text-right">
                    {s.role === 'student' && (
                      <button
                        type="button"
                        onClick={() => toggle(s)}
                        disabled={busyId === s.id}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        {s.is_active ? <UserX className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
                        {s.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {students.length === 0 && (
                <tr><td colSpan={6} className="py-6 text-center text-slate-500">No students found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-label="Audit log" className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
        <h2 className="text-sm font-extrabold text-slate-900 mb-1">Audit log</h2>
        <p className="text-xs text-slate-500 mb-3">Every admin change is recorded here. Newest first.</p>
        <ul className="space-y-1.5 text-sm">
          {audit.map((e) => (
            <li key={e.id} className="flex flex-wrap gap-x-2 text-slate-700">
              <span className="text-slate-500 whitespace-nowrap">{fmt(e.created_at)}</span>
              <span className="font-semibold" translate="no">@{e.actor}</span>
              <span>{e.action === 'student.deactivate' ? 'deactivated' : 'reactivated'} student</span>
              <span className="font-mono text-xs text-slate-500">{e.target.slice(0, 8)}</span>
            </li>
          ))}
          {audit.length === 0 && <li className="text-slate-500">No admin changes yet.</li>}
        </ul>
      </section>
    </div>
  );
}
