import React, { useState } from 'react';
import { Flag, X, Send, AlertTriangle } from 'lucide-react';
import { submitFlag } from '../services/api';

export default function FlagModal({ isOpen, onClose, targetType, targetId, onSuccess }) {
  const [reason, setReason] = useState('Maling impormasyon o factual error');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const defaultReasons = [
    'Maling impormasyon o factual error',
    'Malabo o nakakalito ang pagkakagawa',
    'Maling choices o maling sagot',
    'Typo o formatting issue',
    'Iba pang dahilan (specify sa baba)',
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await submitFlag(targetType, targetId, reason, notes);
      onSuccess?.('Salamat sa pag-flag! Naitala na namin ito para maayos.');
      onClose();
    } catch (err) {
      setError(err.message || 'May problema sa pag-save ng flag.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2 text-amber-600 font-semibold text-lg">
            <Flag className="w-5 h-5" />
            <span>I-flag ang {targetType === 'flashcard' ? 'Flashcard' : 'Tanong'}</span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-slate-500 mt-3">
          May napansing mali o nakakalito? Tulungan natin si Kabi na mas maging tumpak ang reviewer!
        </p>

        {error && (
          <div className="mt-3 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Ano ang problema?
            </label>
            <div className="space-y-1.5">
              {defaultReasons.map((r) => (
                <label
                  key={r}
                  className={`flex items-center gap-2.5 p-2 rounded-lg border text-xs cursor-pointer transition ${
                    reason === r
                      ? 'bg-amber-50/80 border-amber-300 font-medium text-amber-950'
                      : 'border-slate-200 hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="reason"
                    value={r}
                    checked={reason === r}
                    onChange={(e) => setReason(e.target.value)}
                    className="accent-amber-600"
                  />
                  <span>{r}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Karagdagang paliwanag (Optional):
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Halimbawa: Ayon sa page 4 ng module, hindi si Aguinaldo kundi si Bonifacio..."
              className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 outline-none h-20 resize-none"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-xl hover:bg-slate-100 transition"
            >
              Kanselahin
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-xl shadow-sm transition flex items-center gap-1.5 disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{isSubmitting ? 'Isinusumite...' : 'Ipadala ang Flag'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
