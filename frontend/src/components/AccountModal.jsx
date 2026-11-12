import React, { useState } from 'react';
import { Loader2, X } from 'lucide-react';
import PasswordField from './PasswordField';
import authClient from '../services/authClient';
import { changePassword, deactivateAccount, deleteAccount } from '../services/api';

/** Change password, deactivate, or delete the account. Each action re-asks for the current password. */
export default function AccountModal({ user, onClose }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [action, setAction] = useState('password'); // 'password' | 'deactivate' | 'delete'
  const [error, setError] = useState('');
  const [done, setDone] = useState('');
  const [busy, setBusy] = useState(false);

  const run = async (e) => {
    e.preventDefault();
    if (busy) return;
    setError('');
    setDone('');
    if (action === 'password' && next !== confirm) return setError('Hindi magkapareho ang dalawang bagong password.');
    setBusy(true);
    try {
      if (action === 'password') {
        await changePassword(current, next, confirm);
        setCurrent(''); setNext(''); setConfirm('');
        setDone('Napalitan na ang password. Na-log out ang ibang device.');
      } else if (action === 'deactivate') {
        await deactivateAccount(current);
        await authClient.logout();
      } else {
        await deleteAccount(current);
        await authClient.logout();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const tabs = [['password', 'Palitan ang password'], ['deactivate', 'I-deactivate'], ['delete', 'Burahin ang account']];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" role="dialog" aria-modal="true" aria-label="Account">
      <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-extrabold text-slate-900">{user.display_name}</h2>
            <p className="text-xs text-slate-500">@{user.username}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Isara" className="rounded-lg p-1.5 hover:bg-slate-100"><X className="w-5 h-5" /></button>
        </div>

        <div role="tablist" className="mt-4 grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1">
          {tabs.map(([key, text]) => (
            <button key={key} type="button" role="tab" aria-selected={action === key}
              onClick={() => { setAction(key); setError(''); setDone(''); }}
              className={`rounded-lg px-2 py-1.5 text-[11px] sm:text-xs font-bold ${action === key ? 'bg-white text-amber-700 shadow-sm' : 'text-slate-500'}`}>
              {text}
            </button>
          ))}
        </div>

        <form onSubmit={run} className="mt-4 space-y-3" noValidate>
          {action === 'deactivate' && <p className="text-xs text-slate-600">Hindi ka na makakapag-login hanggang hindi na-re-activate ng admin. Hindi nabubura ang data mo.</p>}
          {action === 'delete' && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800">Mabubura ang account mo at <strong>lahat ng module, flashcards, quizzes at progress</strong>. Hindi ito mababawi.</p>}
          <PasswordField label={action === 'password' ? 'Kasalukuyang password' : 'Password mo'} value={current} onChange={setCurrent} autoComplete="current-password" />
          {action === 'password' && (
            <>
              <PasswordField label="Bagong password" value={next} onChange={setNext} autoComplete="new-password" />
              <PasswordField label="Ulitin ang bagong password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
            </>
          )}
          {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}
          {done && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">{done}</p>}
          <button type="submit" disabled={busy || !current}
            className={`w-full inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50 ${action === 'delete' ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-500 hover:bg-amber-600'}`}>
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            {tabs.find(([k]) => k === action)[1]}
          </button>
        </form>
      </div>
    </div>
  );
}
