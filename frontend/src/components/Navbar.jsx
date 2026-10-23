import React, { useState } from 'react';
import { BookOpen, Sparkles, Key, HelpCircle, Layers, CheckCircle2, AlertCircle, BarChart3 } from 'lucide-react';
import Mascot from './Mascot';

export default function Navbar({ activeTab, onSelectTab, currentDoc, aiConfigured }) {
  const [showKeyInfo, setShowKeyInfo] = useState(false);

  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand & Mascot */}
        <div 
          onClick={() => onSelectTab('library')}
          className="flex items-center gap-3 cursor-pointer select-none group"
        >
          <Mascot mood="sleepy" size="sm" />
          <div>
            <div className="flex items-center gap-2">
              <span translate="no" className="notranslate font-extrabold text-xl tracking-tight text-slate-900 group-hover:text-amber-600 transition">
                Kabisado
              </span>
              <span className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 rounded-full border border-amber-200">
                AI Reviewer
              </span>
            </div>
            <p className="text-[11px] font-medium text-slate-500 italic">
              "Study today, pass tomorrow."
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1.5 sm:gap-2">
          <button
            onClick={() => onSelectTab('library')}
            className={`px-3 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-semibold rounded-xl transition flex items-center gap-1.5 ${
              activeTab === 'library'
                ? 'bg-amber-500 text-white shadow-sm shadow-amber-200'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Library</span>
          </button>

          <button
            onClick={() => onSelectTab('dashboard')}
            className={`px-3 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-semibold rounded-xl transition flex items-center gap-1.5 ${
              activeTab === 'dashboard'
                ? 'bg-amber-500 text-white shadow-sm shadow-amber-200'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Dashboard</span>
          </button>


          {currentDoc && (
            <button
              onClick={() => onSelectTab('document')}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-semibold rounded-xl transition flex items-center gap-1.5 max-w-[140px] sm:max-w-[200px] truncate ${
                activeTab === 'document' || activeTab === 'flashcards' || activeTab === 'quiz'
                  ? 'bg-amber-500 text-white shadow-sm shadow-amber-200'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
              title={currentDoc.title}
            >
              <Layers className="w-4 h-4 shrink-0" />
              <span className="truncate">{currentDoc.title}</span>
            </button>
          )}

          {/* AI Status Badge / Modal trigger */}
          <button
            onClick={() => setShowKeyInfo(!showKeyInfo)}
            className={`px-2.5 py-1.5 rounded-xl border text-[11px] font-medium transition flex items-center gap-1.5 ${
              aiConfigured
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800 hover:bg-emerald-100'
                : 'bg-indigo-50 border-indigo-200 text-indigo-800 hover:bg-indigo-100'
            }`}
            title="Check AI engine status"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span className="hidden md:inline">
              {aiConfigured ? 'Claude 3.5 Active' : 'Grounded Engine'}
            </span>
            <span className="md:hidden">
              {aiConfigured ? 'Claude' : 'Active'}
            </span>
          </button>
        </nav>
      </div>

      {/* AI Key Info Modal / Dropdown */}
      {showKeyInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2 text-slate-800 font-bold">
                <Sparkles className="w-5 h-5 text-amber-500" />
                <span>Kabisado AI Engine Info</span>
              </div>
              <button
                onClick={() => setShowKeyInfo(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                ✕
              </button>
            </div>

            <div className="py-4 space-y-3 text-xs sm:text-sm text-slate-600">
              <div className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-50 border border-slate-200">
                {aiConfigured ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
                )}
                <div>
                  <p className="font-semibold text-slate-800">
                    Status: {aiConfigured ? 'Anthropic Claude API Connected' : 'Grounded Local Engine Active'}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {aiConfigured
                      ? 'Using Claude 3.5 Sonnet for in-depth summaries, flashcards, and analysis.'
                      : 'Running in grounded NLP mode. Add an ANTHROPIC_API_KEY to backend/.env for full Claude power!'}
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-amber-50/60 border border-amber-200/80 text-amber-900 text-xs">
                <p className="font-semibold mb-1">How do I add a Claude API key?</p>
                <ol className="list-decimal pl-4 space-y-1">
                  <li>Open the file <code className="bg-amber-100 px-1 py-0.5 rounded font-mono">backend/.env</code></li>
                  <li>Add your key: <code className="bg-amber-100 px-1 py-0.5 rounded font-mono">ANTHROPIC_API_KEY=sk-ant-...</code></li>
                  <li>Restart the backend server if it's already running.</li>
                </ol>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowKeyInfo(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition"
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
