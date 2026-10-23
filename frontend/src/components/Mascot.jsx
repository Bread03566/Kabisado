import React from 'react';

/**
 * Kabi the Sleepy Owl Mascot 🦉
 * Moods: 'sleepy' | 'studying' | 'happy' | 'shocked'
 */
export default function Mascot({ mood = 'sleepy', size = 'md', message = null, className = '' }) {
  const sizeClasses = {
    sm: 'w-12 h-12',
    md: 'w-20 h-20',
    lg: 'w-28 h-28',
    xl: 'w-36 h-36',
  };

  const getEyeExpression = () => {
    switch (mood) {
      case 'happy':
        return (
          <>
            {/* Sparkly happy open eyes */}
            <circle cx="36" cy="48" r="10" fill="#fef08a" stroke="#713f12" strokeWidth="2.5" />
            <circle cx="64" cy="48" r="10" fill="#fef08a" stroke="#713f12" strokeWidth="2.5" />
            <circle cx="38" cy="46" r="4.5" fill="#1e293b" />
            <circle cx="66" cy="46" r="4.5" fill="#1e293b" />
            <circle cx="40" cy="44" r="1.5" fill="#ffffff" />
            <circle cx="68" cy="44" r="1.5" fill="#ffffff" />
          </>
        );
      case 'shocked':
        return (
          <>
            {/* Wide shocked eyes */}
            <circle cx="36" cy="48" r="12" fill="#ffffff" stroke="#713f12" strokeWidth="3" />
            <circle cx="64" cy="48" r="12" fill="#ffffff" stroke="#713f12" strokeWidth="3" />
            <circle cx="36" cy="48" r="5" fill="#0f172a" />
            <circle cx="64" cy="48" r="5" fill="#0f172a" />
            <circle cx="38" cy="46" r="1.5" fill="#ffffff" />
            <circle cx="66" cy="46" r="1.5" fill="#ffffff" />
          </>
        );
      case 'studying':
        return (
          <>
            {/* Focused eyes with reading glasses */}
            <circle cx="36" cy="48" r="9" fill="#fef08a" stroke="#713f12" strokeWidth="2.5" />
            <circle cx="64" cy="48" r="9" fill="#fef08a" stroke="#713f12" strokeWidth="2.5" />
            <circle cx="36" cy="49" r="4" fill="#0f172a" />
            <circle cx="64" cy="49" r="4" fill="#0f172a" />
            {/* Round spectacle frames */}
            <circle cx="36" cy="48" r="11" fill="none" stroke="#0284c7" strokeWidth="2.5" />
            <circle cx="64" cy="48" r="11" fill="none" stroke="#0284c7" strokeWidth="2.5" />
            <line x1="47" y1="48" x2="53" y2="48" stroke="#0284c7" strokeWidth="2.5" />
          </>
        );
      case 'sleepy':
      default:
        return (
          <>
            {/* Heavy droopy sleepy eyes */}
            <circle cx="36" cy="48" r="9.5" fill="#fef08a" stroke="#713f12" strokeWidth="2.5" />
            <circle cx="64" cy="48" r="9.5" fill="#fef08a" stroke="#713f12" strokeWidth="2.5" />
            {/* Droopy heavy eyelids */}
            <path d="M 26 44 Q 36 52 46 44 Z" fill="#78350f" />
            <path d="M 54 44 Q 64 52 74 44 Z" fill="#78350f" />
            {/* Visible lower pupil */}
            <circle cx="36" cy="51" r="3.5" fill="#0f172a" />
            <circle cx="64" cy="51" r="3.5" fill="#0f172a" />
            {/* Sleepy eye creases */}
            <path d="M 24 43 Q 36 38 48 43" stroke="#451a03" strokeWidth="2.5" fill="none" strokeLinecap="round" />
            <path d="M 52 43 Q 64 38 76 43" stroke="#451a03" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          </>
        );
    }
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className={`relative shrink-0 ${sizeClasses[size] || sizeClasses.md} select-none`}>
        <svg viewBox="0 0 100 100" className="w-full h-full drop-shadow-md">
          {/* Owl Body */}
          <ellipse cx="50" cy="55" rx="36" ry="38" fill="#92400e" stroke="#451a03" strokeWidth="3" />
          {/* Belly Feather patch */}
          <ellipse cx="50" cy="62" rx="24" ry="26" fill="#fed7aa" />
          {/* Belly feather texture */}
          <path d="M 44 58 Q 50 63 56 58" stroke="#d97706" strokeWidth="2" fill="none" strokeLinecap="round" />
          <path d="M 40 67 Q 50 72 60 67" stroke="#d97706" strokeWidth="2" fill="none" strokeLinecap="round" />
          <path d="M 44 76 Q 50 81 56 76" stroke="#d97706" strokeWidth="2" fill="none" strokeLinecap="round" />

          {/* Ear Tufts */}
          <path d="M 22 30 L 32 12 L 40 24 Z" fill="#78350f" stroke="#451a03" strokeWidth="2" />
          <path d="M 78 30 L 68 12 L 60 24 Z" fill="#78350f" stroke="#451a03" strokeWidth="2" />

          {/* Nightcap / Study Hat (Purple with pom-pom) */}
          <path d="M 30 22 Q 50 14 70 22 Q 55 5 45 4 Z" fill="#D9D28B" stroke="#6A795D" strokeWidth="2" />
          <circle cx="43" cy="4" r="4.5" fill="#fbbf24" stroke="#d97706" strokeWidth="1.5" />

          {/* Eyes (rendered dynamically) */}
          {getEyeExpression()}

          {/* Beak */}
          <path d="M 46 54 L 54 54 L 50 63 Z" fill="#f59e0b" stroke="#b45309" strokeWidth="2" />

          {/* Feet / Talons */}
          <ellipse cx="40" cy="92" rx="6" ry="3" fill="#f59e0b" />
          <ellipse cx="60" cy="92" rx="6" ry="3" fill="#f59e0b" />

          {/* Sleepy Zzz animation if sleepy */}
          {mood === 'sleepy' && (
            <g className="animate-pulse">
              <text x="76" y="22" fill="#6A795D" fontSize="12" fontWeight="bold">Z</text>
              <text x="86" y="14" fill="#8E9162" fontSize="9" fontWeight="bold">z</text>
            </g>
          )}
        </svg>
      </div>

      {message && (
        <div className="relative bg-amber-50/90 border border-amber-200 text-amber-950 px-3.5 py-2 rounded-2xl shadow-sm text-xs sm:text-sm font-medium max-w-xs sm:max-w-md">
          <div className="absolute -left-1.5 top-1/2 -translate-y-1/2 w-3 h-3 bg-amber-50 border-l border-b border-amber-200 rotate-45"></div>
          {message}
        </div>
      )}
    </div>
  );
}
