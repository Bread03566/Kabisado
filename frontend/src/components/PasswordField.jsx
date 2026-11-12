import React, { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

/** Labelled password input with a show/hide toggle and an inline error message. */
export default function PasswordField({ label, value, onChange, error, autoComplete, hint, name }) {
  const id = useId();
  const [shown, setShown] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-bold text-slate-700 mb-1">{label}</label>
      <div className="relative">
        <input
          id={id}
          name={name}
          type={shown ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          maxLength={128}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined}
          className={`w-full rounded-xl border px-3 py-2.5 pr-11 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 ${
            error ? 'border-red-400 bg-red-50' : 'border-slate-300 bg-white'
          }`}
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          aria-label={shown ? 'Itago ang password' : 'Ipakita ang password'}
          aria-pressed={shown}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 rounded-lg text-slate-500 hover:bg-slate-100"
        >
          {shown ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
      {error ? (
        <p id={`${id}-err`} role="alert" className="mt-1 text-xs text-red-600">{error}</p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}
