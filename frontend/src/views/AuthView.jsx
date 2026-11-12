import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import authClient from '../services/authClient';
import PasswordField from '../components/PasswordField';
import Mascot from '../components/Mascot';
import { fieldForError } from '../services/fieldErrors';


function TextField({ label, value, onChange, error, autoComplete, maxLength, hint }) {
  const id = `f-${label.replace(/\W+/g, '').toLowerCase()}`;
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-bold text-slate-700 mb-1">{label}</label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        maxLength={maxLength}
        aria-invalid={Boolean(error)}
        className={`w-full rounded-xl border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 ${
          error ? 'border-red-400 bg-red-50' : 'border-slate-300 bg-white'
        }`}
      />
      {error ? <p role="alert" className="mt-1 text-xs text-red-600">{error}</p> : hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

/** Login / register tabs. `gate` lets us keep the app hidden until a new recovery code has been saved. */
export default function AuthView({ gate, onRecover, onPrivacy }) {
  const [mode, setMode] = useState('login');
  const [displayName, setDisplayName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const isRegister = mode === 'register';

  const switchMode = (next) => {
    setMode(next);
    setErrors({});
    setPassword('');
    setConfirm('');
  };

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    const local = {};
    if (isRegister && password !== confirm) local.confirm = 'The two passwords do not match.';
    if (isRegister && !displayName.trim()) local.displayName = 'Please enter your name.';
    if (Object.keys(local).length) return setErrors(local);

    setBusy(true);
    setErrors({});
    if (isRegister) gate.hold(true); // keep the app hidden until the recovery code is saved
    try {
      if (isRegister) {
        const { recoveryCode } = await authClient.register({ displayName, username, password, confirmPassword: confirm });
        gate.showRecoveryCode(recoveryCode, username.trim().toLowerCase());
      } else {
        await authClient.login({ username, password });
      }
    } catch (err) {
      if (isRegister) gate.hold(false);
      const wait = err.status === 429 && err.retryAfter ? ` Try again in ${err.retryAfter} seconds.` : '';
      setErrors({ [fieldForError(err)]: err.message + (err.status === 429 ? wait : '') });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto">
      <div className="flex flex-col items-center text-center mb-5">
        <Mascot mood="happy" size="lg" />
        <h1 translate="no" className="notranslate mt-2 text-2xl font-extrabold text-slate-900">Kabisado</h1>
        <p className="text-sm text-slate-500 italic">Study today, pass tomorrow.</p>
      </div>

      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8">
        <div role="tablist" className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1 mb-5">
          {[['login', 'Log in'], ['register', 'Create account']].map(([key, text]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={mode === key}
              onClick={() => switchMode(key)}
              className={`rounded-lg px-3 py-2 text-xs sm:text-sm font-bold transition ${mode === key ? 'bg-white text-amber-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
            >
              {text}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-4" noValidate>
          {isRegister && (
            <TextField label="Name" value={displayName} onChange={setDisplayName} error={errors.displayName} autoComplete="name" maxLength={60} />
          )}
          <TextField
            label="Username"
            value={username}
            onChange={setUsername}
            error={errors.username}
            autoComplete="username"
            maxLength={64}
            hint={isRegister ? '3–32 characters: letters, numbers, _ or .' : undefined}
          />
          <PasswordField
            label="Password"
            value={password}
            onChange={setPassword}
            error={errors.password}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            hint={isRegister ? 'At least 10 characters. Longer is safer.' : undefined}
          />
          {isRegister && (
            <PasswordField label="Confirm password" value={confirm} onChange={setConfirm} error={errors.confirm} autoComplete="new-password" />
          )}

          {errors.form && <p role="alert" className="rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">{errors.form}</p>}

          <button
            type="submit"
            disabled={busy}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-bold text-white shadow-sm hover:bg-amber-600 disabled:opacity-60"
          >
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            {isRegister ? 'Create account' : 'Log in'}
          </button>
        </form>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          {isRegister ? (
            <p>
              By signing up you agree to read the{' '}
              <button type="button" onClick={onPrivacy} className="font-semibold text-amber-700 underline">privacy notice</button>.
            </p>
          ) : (
            <>
              <button type="button" onClick={onRecover} className="font-semibold text-amber-700 underline">Forgot your password?</button>
              <button type="button" onClick={onPrivacy} className="underline">Privacy</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
