import React from 'react';
import { PetFigure, usePetPrefs } from './pets';

/**
 * Kabi, the app's mascot: whichever study-buddy animal the student picked (a tabby cat by default).
 * Moods: 'sleepy' | 'studying' | 'happy' | 'shocked'
 */
const MOODS = {
  sleepy: { mood: 'sleep' },
  studying: { mood: 'open', glasses: true },
  happy: { mood: 'happy' },
  shocked: { mood: 'shocked' },
};

export default function Mascot({ mood = 'sleepy', size = 'md', message = null, className = '' }) {
  const { animal } = usePetPrefs();
  const sizeClasses = {
    sm: 'w-12 h-12',
    md: 'w-20 h-20',
    lg: 'w-28 h-28',
    xl: 'w-36 h-36',
  };
  const look = MOODS[mood] || MOODS.studying;

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className={`relative shrink-0 ${sizeClasses[size] || sizeClasses.md} select-none ${size === 'sm' ? '' : 'mascot-bob'}`}>
        <PetFigure
          animal={animal}
          mood={look.mood}
          glasses={look.glasses}
          track={size !== 'sm'}
          className="w-full h-full drop-shadow-md"
        />
      </div>

      {message && (
        <div key={message} className="animate-in fade-in slide-in-from-left-4 relative bg-amber-50/90 border border-amber-200 text-amber-950 px-3.5 py-2 rounded-2xl shadow-sm text-xs sm:text-sm font-medium max-w-xs sm:max-w-md">
          <div className="absolute -left-1.5 top-1/2 -translate-y-1/2 w-3 h-3 bg-amber-50 border-l border-b border-amber-200 rotate-45"></div>
          {message}
        </div>
      )}
    </div>
  );
}
