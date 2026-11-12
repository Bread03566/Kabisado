import React, { useState } from 'react';
import { BookOpen, Layers, BarChart3, LogOut, UserRound, ShieldCheck } from 'lucide-react';
import { useAuth } from './AuthGate';
import AccountModal from './AccountModal';
import Mascot from './Mascot';

export default function Navbar({ activeTab, onSelectTab, currentDoc }) {
  const { user, logout } = useAuth();
  const [accountOpen, setAccountOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2 md:py-0 md:h-16 flex flex-wrap md:flex-nowrap items-center justify-between gap-x-4 gap-y-2">
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
            <p className="hidden sm:block text-[11px] font-medium text-slate-500 italic">
              "Study today, pass tomorrow."
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1.5 sm:gap-2 w-full md:w-auto overflow-x-auto pb-0.5">
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


          {user?.role === 'admin' && (
            <button
              onClick={() => onSelectTab('admin')}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-semibold rounded-xl transition flex items-center gap-1.5 ${
                activeTab === 'admin'
                  ? 'bg-amber-500 text-white shadow-sm shadow-amber-200'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Admin</span>
            </button>
          )}

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

          <div className="ml-auto md:ml-2 flex items-center gap-1 shrink-0">
            <button
              onClick={() => setAccountOpen(true)}
              className="px-2.5 py-1.5 text-xs sm:text-sm font-semibold rounded-xl text-slate-600 hover:bg-slate-100 flex items-center gap-1.5 max-w-[130px]"
              title="Account"
            >
              <UserRound className="w-4 h-4 shrink-0" />
              <span className="truncate" translate="no">{user?.display_name}</span>
            </button>
            <button
              onClick={logout}
              className="px-2.5 py-1.5 text-xs sm:text-sm font-semibold rounded-xl text-slate-600 hover:bg-slate-100 flex items-center gap-1.5"
              title="Log out"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </nav>
      </div>

      {accountOpen && user && <AccountModal user={user} onClose={() => setAccountOpen(false)} />}
    </header>
  );
}
