import React, { useEffect, useRef, useState } from 'react';
import { EyeOff, PawPrint } from 'lucide-react';
import { ANIMALS, ANIMAL_KEYS, PetFigure, setPetPrefs, subscribePointer, usePetPrefs } from './pets';

/*
 * The desk-buddy pet in the corner of the screen. It watches the cursor, naps when you go
 * idle, and purrs when petted. Its menu also picks the animal used as the app's mascot.
 */

const IDLE_MS = 25000;

export default function Companion() {
  const prefs = usePetPrefs();
  const [mood, setMood] = useState('open'); // open | happy | sleep
  const [menuOpen, setMenuOpen] = useState(false);
  const [bubble, setBubble] = useState(null);
  const [hearts, setHearts] = useState([]);
  const idleTimer = useRef(0);

  const animal = ANIMALS[prefs.animal];

  // Going idle puts the pet to sleep; any pointer movement wakes it
  useEffect(() => {
    if (prefs.hidden) return undefined;
    const resetIdle = () => {
      clearTimeout(idleTimer.current);
      idleTimer.current = setTimeout(() => setMood('sleep'), IDLE_MS);
    };
    const unsubscribe = subscribePointer(() => {
      setMood((m) => (m === 'sleep' ? 'open' : m));
      resetIdle();
    });
    resetIdle();
    return () => {
      unsubscribe();
      clearTimeout(idleTimer.current);
    };
  }, [prefs.hidden]);

  const handlePet = () => {
    setMood('happy');
    setBubble(animal.sounds[Math.floor(Math.random() * animal.sounds.length)]);
    const id = Date.now();
    setHearts((h) => [...h, ...[0, 1, 2].map((i) => ({ id: `${id}-${i}`, offset: (i - 1) * 16, delay: i * 90 }))]);
    setTimeout(() => setHearts((h) => h.filter((heart) => !heart.id.startsWith(String(id)))), 1300);
    setTimeout(() => setBubble(null), 2400);
    setTimeout(() => setMood((m) => (m === 'happy' ? 'open' : m)), 1200);
  };

  if (prefs.hidden) {
    return (
      <button
        type="button"
        onClick={() => setPetPrefs({ hidden: false })}
        className="animate-in fade-in zoom-in-95 fixed bottom-4 left-4 z-30 flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-md hover:text-slate-900"
        aria-label={`Show ${animal.name}`}
        title={`Show ${animal.name}`}
      >
        <PawPrint className="h-5 w-5" />
      </button>
    );
  }

  return (
    <div className="group/pet fixed bottom-3 left-3 z-30 select-none">
      {/* Speech bubble */}
      {bubble && (
        <div key={bubble} className="animate-in fade-in slide-in-from-bottom-2 absolute bottom-full left-2 mb-1 w-max max-w-[220px] rounded-2xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 shadow-md">
          {bubble}
        </div>
      )}

      {/* Floating hearts */}
      {hearts.map((h) => (
        <span
          key={h.id}
          className="pet-heart pointer-events-none absolute bottom-16 left-1/2 text-base text-rose-500"
          style={{ '--x': `${h.offset}px`, animationDelay: `${h.delay}ms` }}
          aria-hidden="true"
        >
          ♥
        </span>
      ))}

      <button
        type="button"
        onClick={handlePet}
        aria-label={`Pet the ${animal.name}`}
        title={mood === 'sleep' ? `${animal.name} is napping. Move to wake it.` : `Pet the ${animal.name}`}
        className="block h-20 w-20 sm:h-24 sm:w-24 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
      >
        <PetFigure animal={prefs.animal} mood={mood} track className="h-full w-full drop-shadow-md" />
      </button>

      {/* Switch animal / hide */}
      <button
        type="button"
        onClick={() => setMenuOpen((o) => !o)}
        aria-label="Choose a study buddy"
        aria-expanded={menuOpen}
        className={`absolute -right-1 -top-1 flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:text-slate-900 focus-visible:opacity-100 ${
          menuOpen ? 'opacity-100' : 'opacity-0 group-hover/pet:opacity-100 [@media(hover:none)]:opacity-100'
        }`}
      >
        <PawPrint className="h-3.5 w-3.5" />
      </button>

      {menuOpen && (
        <div className="animate-in fade-in zoom-in-95 absolute bottom-full left-0 mb-2 w-72 max-w-[calc(100vw-1.5rem)] rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl">
          <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-semibold text-slate-500">Your study buddy (shown across the app)</p>
          <div className="grid grid-cols-2 gap-0.5">
            {ANIMAL_KEYS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => {
                  setPetPrefs({ animal: key });
                  setMenuOpen(false);
                  setMood('open');
                }}
                aria-pressed={prefs.animal === key}
                className={`flex items-center gap-2 rounded-xl px-2 py-1.5 text-left text-xs font-semibold transition ${
                  prefs.animal === key ? 'bg-amber-100 text-slate-900 ring-1 ring-amber-300' : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                <PetFigure animal={key} mood="happy" className="h-7 w-7 shrink-0" />
                <span className="truncate">{ANIMALS[key].name}</span>
              </button>
            ))}
          </div>
          <div className="my-1 border-t border-slate-100" />
          <button
            type="button"
            onClick={() => {
              setPetPrefs({ hidden: true });
              setMenuOpen(false);
            }}
            className="flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left text-xs font-semibold text-slate-600 hover:bg-slate-100"
          >
            <EyeOff className="h-3.5 w-3.5" />
            Hide the corner buddy
          </button>
        </div>
      )}
    </div>
  );
}
