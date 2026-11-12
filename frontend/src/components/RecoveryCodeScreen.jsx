import React, { useState } from 'react';
import { Copy, Download, KeyRound, ShieldAlert } from 'lucide-react';

/** Shows the recovery code exactly once. The student must confirm they saved it before continuing. */
export default function RecoveryCodeScreen({ code, username, onContinue, isReset = false }) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the code is selectable on screen */
    }
  };

  const download = () => {
    const text = `Kabisado recovery code\nUsername: ${username || ''}\nCode: ${code}\n\nKeep this somewhere safe. Anyone with this code can reset your password.\n`;
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kabisado-recovery-code.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-md mx-auto bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8">
      <div className="flex items-center gap-2 text-amber-700 mb-2">
        <KeyRound className="w-5 h-5" />
        <h2 className="text-lg font-extrabold">{isReset ? 'Bagong recovery code mo' : 'I-save ang recovery code mo'}</h2>
      </div>
      <p className="text-sm text-slate-600 mb-4">
        Ito lang ang paraan para makabawi kung makalimutan mo ang password. Makikita mo ito <strong>ngayon lang</strong>.
      </p>

      <div
        className="select-all rounded-2xl border-2 border-dashed border-amber-300 bg-amber-50 px-4 py-4 text-center font-mono text-base sm:text-lg font-bold tracking-wider text-amber-900 break-all"
        data-testid="recovery-code"
      >
        {code}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <button type="button" onClick={copy} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold hover:bg-slate-50">
          <Copy className="w-4 h-4" /> {copied ? 'Na-copy!' : 'Copy'}
        </button>
        <button type="button" onClick={download} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold hover:bg-slate-50">
          <Download className="w-4 h-4" /> I-download
        </button>
      </div>

      <div className="mt-4 flex gap-2 rounded-xl bg-red-50 border border-red-200 p-3 text-xs text-red-800">
        <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
        <p>
          Kapag nawala mo <strong>parehong</strong> ang password at ang code na ito, <strong>hindi na mababawi ang account</strong> —
          walang email o phone na pwedeng pagbalikan, at hindi ka rin matutulungan ng admin.
        </p>
      </div>

      <label className="mt-4 flex items-start gap-2 text-sm text-slate-800 cursor-pointer">
        <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} className="mt-1 h-4 w-4 accent-amber-500" />
        <span>Na-save ko na ang recovery code ko.</span>
      </label>

      <button
        type="button"
        disabled={!saved}
        onClick={onContinue}
        className="mt-4 w-full rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-bold text-white shadow-sm hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        Tuloy sa Kabisado
      </button>
    </div>
  );
}
