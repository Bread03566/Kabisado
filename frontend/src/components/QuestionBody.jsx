import React, { useMemo, useState } from 'react';
import { CheckCircle2, XCircle, Check, X, Loader2, CornerDownLeft, GripVertical, Undo2 } from 'lucide-react';

/*
 * The answer area for one quiz question, for every question type:
 *   multiple_choice, true_false  -> pick a choice
 *   identification               -> type the answer
 *   matching                     -> drag terms onto descriptions (or tap a term, then a slot)
 *
 * `answer` is undefined until the student answers; afterwards it holds their response plus
 * `is_correct` (and `correct_answer` for typed answers), and the component shows feedback.
 */

export const QUESTION_TYPE_LABELS = {
  multiple_choice: 'Choose one correct answer',
  true_false: 'True or false?',
  identification: 'Type your answer',
  matching: 'Drag each term onto its match, or tap a term and then a slot',
};

function ChoiceAnswer({ question, answer, onAnswer }) {
  const answered = answer !== undefined;
  const isTrueFalse = question.question_type === 'true_false';
  const letters = ['A', 'B', 'C', 'D'];

  return (
    <div className={isTrueFalse ? 'grid grid-cols-2 gap-3' : 'space-y-3'}>
      {question.choices.map((choiceText, idx) => {
        const isSelected = answer?.selected_index === idx;
        const isCorrect = idx === question.correct_index;

        let style = 'border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 text-slate-800';
        let badge = 'bg-slate-100 text-slate-700';
        if (answered) {
          if (isCorrect) {
            style = 'border-emerald-500 bg-emerald-50 text-emerald-950 font-bold ring-2 ring-emerald-500/30';
            badge = 'bg-emerald-600 text-white';
          } else if (isSelected) {
            style = 'border-rose-400 bg-rose-50 text-rose-950 font-bold';
            badge = 'bg-rose-600 text-white';
          } else {
            style = 'border-slate-100 text-slate-400 opacity-60';
          }
        }
        // Right answer pulses, a wrong pick shakes
        const feedback = answered ? (isCorrect ? 'answer-correct' : isSelected ? 'answer-wrong' : '') : '';

        if (isTrueFalse) {
          const Icon = idx === 0 ? Check : X;
          return (
            <button
              key={idx}
              onClick={() => onAnswer({ selected_index: idx })}
              disabled={answered}
              className={`flex flex-col items-center justify-center gap-2 rounded-2xl border p-5 text-sm font-bold transition ${style} ${feedback}`}
            >
              <span className={`flex h-10 w-10 items-center justify-center rounded-full ${badge}`}>
                <Icon className="h-5 w-5" />
              </span>
              {choiceText}
            </button>
          );
        }

        return (
          <button
            key={idx}
            onClick={() => onAnswer({ selected_index: idx })}
            disabled={answered}
            className={`w-full p-4 rounded-2xl border text-left transition flex items-center justify-between gap-3 text-xs sm:text-sm select-none ${style} ${feedback}`}
          >
            <div className="flex items-center gap-3">
              <span className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 transition ${badge}`}>
                {letters[idx]}
              </span>
              <span className="leading-relaxed">{choiceText}</span>
            </div>
            {answered && (isCorrect ? <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600" /> : isSelected ? <XCircle className="w-5 h-5 shrink-0 text-rose-600" /> : null)}
          </button>
        );
      })}
    </div>
  );
}

function IdentificationAnswer({ answer, onAnswer, checking }) {
  const [text, setText] = useState('');
  const answered = answer !== undefined;

  const submit = (value) => {
    if (answered || checking) return;
    onAnswer({ text_answer: value });
  };

  if (answered) {
    return (
      <div className="space-y-3">
        <div
          className={`flex items-center gap-3 rounded-2xl border p-4 text-sm font-bold ${
            answer.is_correct ? 'answer-correct border-emerald-500 bg-emerald-50 text-emerald-950' : 'answer-wrong border-rose-400 bg-rose-50 text-rose-950'
          }`}
        >
          {answer.is_correct ? <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" /> : <XCircle className="h-5 w-5 shrink-0 text-rose-600" />}
          <span>{answer.text_answer?.trim() ? answer.text_answer : 'No answer given'}</span>
        </div>
        {!answer.is_correct && (
          <div className="rounded-2xl border border-emerald-300 bg-white p-4 text-sm">
            <span className="block text-[11px] font-bold text-emerald-600">Correct answer</span>
            <span className="font-bold text-emerald-800">{answer.correct_answer}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) submit(text);
      }}
      className="space-y-2"
    >
      <div className="flex gap-2">
        <input
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type the answer..."
          aria-label="Your answer"
          maxLength={300}
          className="min-w-0 flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
        />
        <button
          type="submit"
          disabled={!text.trim() || checking}
          className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-4 text-sm font-bold text-white transition hover:bg-emerald-700 disabled:opacity-40"
        >
          {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <CornerDownLeft className="h-4 w-4" />}
          Check
        </button>
      </div>
      <div className="flex items-center justify-between text-[11px] text-slate-500">
        <span>Spelling slips are okay; capital letters don't matter.</span>
        <button type="button" onClick={() => submit('')} disabled={checking} className="font-semibold underline underline-offset-2 hover:text-slate-800">
          I don't know
        </button>
      </div>
    </form>
  );
}

// Same shuffle every time for a given question, so re-renders don't reorder the terms
function seededShuffle(items, seed) {
  const out = items.map((item, i) => ({ item, i }));
  let s = seed || 1;
  for (let i = out.length - 1; i > 0; i -= 1) {
    s = (s * 9301 + 49297) % 233280;
    const j = Math.floor((s / 233280) * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  // Never show the terms already in the right order
  if (out.length > 1 && out.every((o, idx) => o.i === idx)) out.push(out.shift());
  return out;
}

function MatchingAnswer({ question, answer, onAnswer }) {
  const pairs = question.answer_data?.pairs || [];
  const terms = useMemo(() => seededShuffle(pairs.map((p) => p.term), question.id), [pairs, question.id]);
  const [placed, setPlaced] = useState(() => pairs.map(() => null)); // slot i -> pair index of the term placed there
  const [selected, setSelected] = useState(null); // pair index of a tapped term waiting for a slot
  const [dragOver, setDragOver] = useState(null);
  const answered = answer !== undefined;
  const result = answered ? answer.matching : placed;

  const place = (slot, termIdx) => {
    if (answered || termIdx === null || termIdx === undefined) return;
    setPlaced((prev) => prev.map((t, i) => (i === slot ? termIdx : t === termIdx ? prev[slot] : t)));
    setSelected(null);
  };
  const unplace = (slot) => !answered && setPlaced((prev) => prev.map((t, i) => (i === slot ? null : t)));
  const pool = terms.filter(({ i }) => !placed.includes(i));
  const complete = placed.every((t) => t !== null);

  return (
    <div className="space-y-4">
      {!answered && (
        <div className="flex min-h-12 flex-wrap gap-2 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-2.5">
          {pool.length === 0 ? (
            <span className="px-1 py-1.5 text-xs text-slate-500">All terms placed. Check your matches below.</span>
          ) : (
            pool.map(({ item, i }) => (
              <button
                key={i}
                type="button"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('text/plain', String(i));
                  e.dataTransfer.effectAllowed = 'move';
                }}
                onClick={() => setSelected(selected === i ? null : i)}
                aria-pressed={selected === i}
                className={`inline-flex cursor-grab items-center gap-1 rounded-xl border px-3 py-2 text-xs font-bold shadow-xs transition active:cursor-grabbing ${
                  selected === i ? 'border-amber-500 bg-amber-500 text-white' : 'border-slate-200 bg-white text-slate-800 hover:border-amber-400'
                }`}
              >
                <GripVertical className="h-3.5 w-3.5 opacity-50" />
                {item}
              </button>
            ))
          )}
        </div>
      )}

      <ol className="space-y-2.5">
        {pairs.map((pair, slot) => {
          const termIdx = result?.[slot];
          const hasTerm = termIdx !== null && termIdx !== undefined;
          const right = answered && termIdx === slot;
          return (
            <li
              key={slot}
              onDragOver={(e) => {
                if (answered) return;
                e.preventDefault();
                setDragOver(slot);
              }}
              onDragLeave={() => setDragOver((d) => (d === slot ? null : d))}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(null);
                place(slot, Number(e.dataTransfer.getData('text/plain')));
              }}
              className={`flex flex-col gap-2 rounded-2xl border p-3 transition sm:flex-row sm:items-center ${
                answered
                  ? right
                    ? 'answer-correct border-emerald-400 bg-emerald-50'
                    : 'answer-wrong border-rose-300 bg-rose-50'
                  : dragOver === slot
                  ? 'border-amber-400 bg-amber-50'
                  : 'border-slate-200 bg-white'
              }`}
            >
              <button
                type="button"
                disabled={answered}
                onClick={() => (selected !== null ? place(slot, selected) : hasTerm && unplace(slot))}
                aria-label={hasTerm ? `Matched with ${pairs[termIdx].term}. Tap to remove.` : 'Empty slot. Tap after choosing a term.'}
                className={`flex min-h-10 w-full shrink-0 items-center justify-center gap-1.5 rounded-xl border-2 px-3 py-2 text-xs font-bold transition sm:w-44 ${
                  hasTerm
                    ? answered
                      ? right
                        ? 'border-emerald-500 bg-white text-emerald-800'
                        : 'border-rose-400 bg-white text-rose-800'
                      : 'border-amber-500 bg-amber-100 text-slate-900 hover:bg-amber-200'
                    : selected !== null
                    ? 'animate-pulse border-dashed border-amber-500 text-amber-700'
                    : 'border-dashed border-slate-300 text-slate-400'
                }`}
              >
                {hasTerm ? (
                  <>
                    {answered && (right ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />)}
                    {pairs[termIdx].term}
                    {!answered && <Undo2 className="h-3 w-3 opacity-50" />}
                  </>
                ) : (
                  'Drop a term here'
                )}
              </button>
              <div className="text-xs leading-relaxed text-slate-700 sm:text-sm">
                {pair.definition}
                {answered && !right && <span className="mt-1 block text-[11px] font-bold text-emerald-700">Answer: {pair.term}</span>}
              </div>
            </li>
          );
        })}
      </ol>

      {!answered && (
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => {
              setPlaced(pairs.map(() => null));
              setSelected(null);
            }}
            className="text-xs font-semibold text-slate-500 underline underline-offset-2 hover:text-slate-800"
          >
            Reset
          </button>
          <button
            type="button"
            disabled={!complete}
            onClick={() => onAnswer({ matching: placed })}
            className="rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-40 sm:text-sm"
          >
            {complete ? 'Check matches' : `Place ${placed.filter((t) => t === null).length} more`}
          </button>
        </div>
      )}
    </div>
  );
}

export default function QuestionBody({ question, answer, onAnswer, checking }) {
  switch (question.question_type) {
    case 'identification':
      return <IdentificationAnswer key={question.id} answer={answer} onAnswer={onAnswer} checking={checking} />;
    case 'matching':
      return <MatchingAnswer key={question.id} question={question} answer={answer} onAnswer={onAnswer} />;
    default:
      return <ChoiceAnswer question={question} answer={answer} onAnswer={onAnswer} />;
  }
}
