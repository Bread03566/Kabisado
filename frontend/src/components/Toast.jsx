import React, { useEffect } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export default function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      onClose();
    }, 4500);
    return () => clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  const typeConfig = {
    success: {
      bg: 'bg-emerald-50 border-emerald-300 text-emerald-900',
      icon: <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />,
    },
    error: {
      bg: 'bg-rose-50 border-rose-300 text-rose-900',
      icon: <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />,
    },
    info: {
      bg: 'bg-indigo-50 border-indigo-300 text-indigo-900',
      icon: <Info className="w-5 h-5 text-indigo-600 shrink-0" />,
    },
  };

  const config = typeConfig[toast.type] || typeConfig.info;

  return (
    <div className="fixed bottom-5 right-5 z-50 max-w-sm animate-bounce-short">
      <div className={`flex items-start gap-3 p-3.5 rounded-xl border shadow-lg ${config.bg}`}>
        {config.icon}
        <div className="flex-1 text-sm font-medium pr-1">
          {toast.message}
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-700 transition p-0.5 rounded"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
