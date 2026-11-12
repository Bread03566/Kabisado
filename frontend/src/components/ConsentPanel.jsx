import React, { useEffect, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { getConsent, giveGeminiConsent, withdrawGeminiConsent } from '../services/api';

/** "Gemini AI (optional)" settings. Off unless the site has Gemini enabled AND the student opts in. */
export default function ConsentPanel() {
  const [state, setState] = useState(null);
  const [adult, setAdult] = useState(false);
  const [accept, setAccept] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    getConsent().then((s) => live && setState(s)).catch(() => live && setError('Could not load this setting.'));
    return () => { live = false; };
  }, []);

  const act = async (fn) => {
    setBusy(true);
    setError('');
    try {
      await fn();
      setState(await getConsent());
      setAdult(false);
      setAccept(false);
    } catch (e) {
      setError(e.message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label="Gemini AI settings" className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
      <h3 className="flex items-center gap-1.5 text-sm font-extrabold text-slate-900">
        <Sparkles className="w-4 h-4 text-amber-600" /> Gemini AI (optional)
      </h3>

      {!state && !error && <p className="mt-2 text-slate-500">Loading…</p>}
      {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}

      {state && !state.gemini_available && (
        <p className="mt-2">
          <strong>Not available.</strong> Gemini AI is switched off on this site, so none of your content is sent to any
          AI service. Summaries, flashcards, quizzes and chat use Kabisado&apos;s built-in offline mode.
        </p>
      )}

      {state?.gemini_available && state.consent && (
        <div className="mt-2 space-y-2">
          <p><strong>On.</strong> The text of the sections you ask about, and your chat questions, are sent to Google&apos;s Gemini.</p>
          <p className="text-slate-500">
            Turning it off works immediately. Anything already sent cannot be recalled or deleted by Kabisado, and
            deleting a module here does not delete what Google received. Study material already made is kept.
          </p>
          <button type="button" disabled={busy} onClick={() => act(withdrawGeminiConsent)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-bold hover:bg-slate-100 disabled:opacity-50">
            {busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Turn off Gemini AI
          </button>
        </div>
      )}

      {state?.gemini_available && !state.consent && (
        <div className="mt-2 space-y-2">
          {state.needs_reaccept && <p className="font-bold text-amber-800">The notice below changed. Please read it again to keep using Gemini.</p>}
          <p>Off by default. If you turn it on, these are sent to Google&apos;s Gemini:</p>
          <ul className="list-disc pl-5 space-y-0.5">
            <li>the text of the sections being summarised, turned into flashcards or quizzes, or asked about;</li>
            <li>your chat questions and your recent chat messages.</li>
          </ul>
          <p>Never sent: your username, display name, password, other modules or other people&apos;s data.</p>
          <ul className="list-disc pl-5 space-y-0.5">
            <li>For unpaid use, Google&apos;s terms say content may be used to provide, improve and develop its products, and human reviewers may read it.</li>
            <li>Google asks users not to submit sensitive, confidential or personal information.</li>
            <li>The terms do not say how long unpaid-use content is kept.</li>
            <li>Kabisado cannot take back or delete content after it is sent.</li>
          </ul>
          <label className="flex items-start gap-2">
            <input type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} className="mt-0.5 h-4 w-4 accent-amber-500" />
            <span>I am 18 or older.</span>
          </label>
          <label className="flex items-start gap-2">
            <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="mt-0.5 h-4 w-4 accent-amber-500" />
            <span>I have read the above and I choose to turn on Gemini AI.</span>
          </label>
          <button type="button" disabled={busy || !adult || !accept}
            onClick={() => act(() => giveGeminiConsent(state.policy_version))}
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 font-bold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-slate-300">
            {busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Turn on Gemini AI
          </button>
        </div>
      )}
    </section>
  );
}
