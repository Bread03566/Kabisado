import React, { useState } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import authClient from '../services/authClient';
import PasswordField from '../components/PasswordField';
import { fieldForError } from '../services/fieldErrors';

export default function RecoverView({ gate, onBack }) {
  const [username, setUsername] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    if (password !== confirm) return setErrors({ confirm: 'The two passwords do not match.' });
    setBusy(true);
    setErrors({});
    gate.hold(true);
    try {
      const { recoveryCode } = await authClient.recover({
        username, recoveryCode: code, newPassword: password, confirmPassword: confirm,
      });
      gate.showRecoveryCode(recoveryCode, username.trim().toLowerCase(), true);
    } catch (err) {
      gate.hold(false);
      const key = err.status === 401 ? 'form' : fieldForError(err) === 'password' ? 'password' : 'form';
      setErrors({ [key]: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-800">
        <ArrowLeft className="w-4 h-4" /> Back to log in
      </button>
      <h1 className="mt-3 text-xl font-extrabold text-slate-900">Reset your password</h1>
      <p className="mt-1 text-sm text-slate-600">Enter your username and the recovery code you saved when you created your account.</p>

      <form onSubmit={submit} className="mt-5 space-y-4" noValidate>
        <div>
          <label htmlFor="rec-username" className="block text-xs font-bold text-slate-700 mb-1">Username</label>
          <input id="rec-username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" maxLength={64}
            className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400" />
        </div>
        <div>
          <label htmlFor="rec-code" className="block text-xs font-bold text-slate-700 mb-1">Recovery code</label>
          <input id="rec-code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" maxLength={64} spellCheck={false}
            placeholder="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XX"
            className="w-full rounded-xl border border-slate-300 px-3 py-2.5 font-mono text-sm uppercase focus:outline-none focus:ring-2 focus:ring-amber-400" />
        </div>
        <PasswordField label="New password" value={password} onChange={setPassword} error={errors.password} autoComplete="new-password" />
        <PasswordField label="Confirm new password" value={confirm} onChange={setConfirm} error={errors.confirm} autoComplete="new-password" />

        {errors.form && <p role="alert" className="rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">{errors.form}</p>}

        <button type="submit" disabled={busy}
          className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-bold text-white shadow-sm hover:bg-amber-600 disabled:opacity-60">
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} Reset your password
        </button>
      </form>
    </div>
  );
}
