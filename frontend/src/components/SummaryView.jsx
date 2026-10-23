import React, { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { BookOpenCheck, Check, Lightbulb, PartyPopper, Sparkles } from 'lucide-react';
import Markdown from './Markdown';

/**
 * Splits AI summary markdown into the big idea (text before the first heading) and one
 * section per heading. "> Exam tip: ..." lines become the section's tip.
 */
export function parseSummary(markdown) {
  const overview = [];
  const sections = [];
  let current = null;

  for (const line of (markdown || '').replace(/\r/g, '').split('\n')) {
    const heading = line.match(/^#{1,4}\s+(.+)/);
    if (heading) {
      current = { title: heading[1].replace(/\*\*/g, '').trim(), body: [], tip: null };
      sections.push(current);
      continue;
    }
    const tip = line.match(/^>\s*\*{0,2}\s*exam tip\s*:?\s*\*{0,2}\s*:?\s*(.+)$/i);
    if (tip && current) {
      current.tip = tip[1].trim();
      continue;
    }
    (current ? current.body : overview).push(line);
  }

  return {
    overview: overview.join('\n').trim(),
    sections: sections
      .map((s) => ({ ...s, body: s.body.join('\n').trim() }))
      .filter((s) => s.body || s.tip),
  };
}

const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** A key term in the text: underlined, and shows its definition on hover, focus, or tap. */
function KeyTerm({ children, definition }) {
  return (
    <span className="group relative inline-block">
      <button
        type="button"
        className="font-semibold text-slate-900 underline decoration-amber-400 decoration-2 underline-offset-[3px] hover:decoration-amber-600 focus:outline-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-amber-400"
      >
        {children}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-20 mb-2 w-64 max-w-[80vw] -translate-x-1/2 translate-y-1 rounded-xl bg-slate-900 px-3.5 py-2.5 text-left text-xs font-normal leading-relaxed text-white opacity-0 shadow-xl transition duration-150 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100"
      >
        <span className="mb-0.5 block font-bold text-amber-200">{children}</span>
        {definition}
      </span>
    </span>
  );
}

const KEY_TERM_HREF = '#key-term-';
const KEY_TERM_LINK = /\[[^\]]*\]\(#key-term-\d+\)/g;

/**
 * Turns the first mention of each key term into a markdown link "[term](#key-term-N)",
 * which SectionBody renders as an interactive KeyTerm. Doing this on the text (not while
 * rendering) keeps the result the same no matter how often React re-renders.
 */
export function linkKeyTerms(markdown, keyTerms) {
  let text = markdown || '';
  const longestFirst = keyTerms.map((k, idx) => ({ ...k, idx })).sort((a, b) => b.term.length - a.term.length);
  for (const { term, idx } of longestFirst) {
    const pattern = new RegExp(String.raw`\b` + escapeRegex(term) + String.raw`\b`, 'i');
    // Only search outside links already inserted, so a short term never lands inside a longer one
    const pieces = text.split(KEY_TERM_LINK);
    const links = text.match(KEY_TERM_LINK) || [];
    const hit = pieces.findIndex((piece) => pattern.test(piece));
    if (hit === -1) continue;
    pieces[hit] = pieces[hit].replace(pattern, (match) => `[${match}](${KEY_TERM_HREF}${idx})`);
    text = pieces.reduce((acc, piece, i) => acc + piece + (links[i] || ''), '');
  }
  return text;
}

const sectionComponents = (keyTerms) => ({
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="space-y-2.5">{children}</ul>,
  ol: ({ children }) => <ol className="space-y-2.5 list-decimal pl-5">{children}</ol>,
  li: ({ children }) => (
    <li className="relative pl-5 before:absolute before:left-0 before:top-[0.6em] before:h-1.5 before:w-1.5 before:rounded-full before:bg-amber-400">
      {children}
    </li>
  ),
  strong: ({ children }) => (
    <strong className="rounded bg-amber-100 px-1 py-px font-semibold text-slate-900 [box-decoration-break:clone]">{children}</strong>
  ),
  blockquote: ({ children }) => <blockquote className="my-2 border-l-2 border-amber-300 pl-3 italic text-slate-600">{children}</blockquote>,
  a: ({ href, children }) => {
    if (href?.startsWith(KEY_TERM_HREF)) {
      const term = keyTerms[Number(href.slice(KEY_TERM_HREF.length))];
      if (term) return <KeyTerm definition={term.definition}>{children}</KeyTerm>;
      return <>{children}</>;
    }
    return (
      <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2 text-amber-700">
        {children}
      </a>
    );
  },
});

/** Markdown for one section, with bold text styled as highlighter marks and the first mention of each key term made interactive. */
function SectionBody({ children, keyTerms }) {
  const text = useMemo(() => linkKeyTerms(children, keyTerms), [children, keyTerms]);
  const components = useMemo(() => sectionComponents(keyTerms), [keyTerms]);
  return (
    <ReactMarkdown components={components} skipHtml>
      {text}
    </ReactMarkdown>
  );
}

export default function SummaryView({ summary, keyTerms = [], length, storageKey, onStartQuiz }) {
  const { overview, sections } = useMemo(() => parseSummary(summary), [summary]);
  const readMinutes = Math.max(1, Math.round((summary || '').split(/\s+/).filter(Boolean).length / 200));

  // Which sections the student has marked as reviewed; remembered per document and length
  const [reviewed, setReviewed] = useState([]);
  useEffect(() => {
    try {
      setReviewed(JSON.parse(localStorage.getItem(storageKey) || '[]'));
    } catch {
      setReviewed([]);
    }
  }, [storageKey]);

  const toggleReviewed = (title) => {
    setReviewed((prev) => {
      const next = prev.includes(title) ? prev.filter((t) => t !== title) : [...prev, title];
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // Storage can be unavailable (private mode); progress just won't persist
      }
      return next;
    });
  };

  const doneCount = sections.filter((s) => reviewed.includes(s.title)).length;
  const allDone = sections.length > 0 && doneCount === sections.length;

  // Older summaries saved before the structured format: show them as one readable card
  if (sections.length === 0) {
    return (
      <div className="view-enter rounded-2xl border border-slate-200 bg-white p-6 shadow-xs sm:p-8">
        <Markdown className="max-w-prose text-sm leading-relaxed text-slate-700 sm:text-[15px]">{summary}</Markdown>
        <p className="mt-5 border-t border-slate-100 pt-4 text-xs text-slate-500">
          This summary was saved in an older format. Click <span className="font-semibold">Regenerate Summary</span> for the card layout.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header + progress */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-black text-slate-900 sm:text-xl">Lesson summary</h2>
          <p className="text-xs text-slate-500">
            {sections.length} sections · about {readMinutes} min read · <span className="capitalize">{length}</span>
          </p>
        </div>
        <div className="w-full sm:w-64">
          <div className="mb-1 flex justify-between text-[11px] font-semibold text-slate-600">
            <span>Sections reviewed</span>
            <span>{doneCount} of {sections.length}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-amber-500 transition-[width] duration-500 ease-out"
              style={{ width: `${(doneCount / sections.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* The big idea */}
      {overview && (
        <div className="stagger-item relative overflow-hidden rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600 p-6 text-white shadow-md sm:p-7" style={{ '--i': 0 }}>
          <div className="mb-2 flex items-center gap-2 text-xs font-bold text-amber-100">
            <Sparkles className="h-4 w-4" />
            <span>The big idea</span>
          </div>
          <div className={`max-w-3xl font-semibold leading-snug ${overview.length < 260 ? 'text-lg sm:text-xl' : 'text-sm sm:text-base'}`}>
            <ReactMarkdown skipHtml components={{ p: ({ children }) => <p>{children}</p> }}>{overview}</ReactMarkdown>
          </div>
          <div className="pointer-events-none absolute -bottom-12 -right-10 h-40 w-40 rounded-full bg-white/10 blur-xl" />
        </div>
      )}

      {/* Section cards */}
      <ol className="grid items-start gap-4 md:grid-cols-2">
        {sections.map((section, idx) => {
          const isDone = reviewed.includes(section.title);
          return (
            <li
              key={section.title + idx}
              className={`stagger-item flex flex-col rounded-2xl border bg-white p-5 shadow-xs transition duration-200 hover:-translate-y-0.5 hover:shadow-md sm:p-6 ${
                isDone ? 'border-emerald-300 ring-1 ring-emerald-200' : 'border-slate-200'
              }`}
              style={{ '--i': idx + 1 }}
            >
              <div className="mb-3 flex items-start gap-3">
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-black transition-colors ${
                    isDone ? 'bg-emerald-500 text-white' : 'bg-amber-100 text-amber-900'
                  }`}
                >
                  {isDone ? <Check key="done" className="pop-in h-4 w-4" /> : idx + 1}
                </span>
                <h3 className="pt-1 text-sm font-extrabold leading-snug text-slate-900 sm:text-base">{section.title}</h3>
              </div>

              <div className="text-sm leading-relaxed text-slate-700">
                <SectionBody keyTerms={keyTerms}>{section.body}</SectionBody>
              </div>

              {section.tip && (
                <div className="mt-4 flex gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-950">
                  <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <div>
                    <span className="font-bold">Exam tip: </span>
                    <ReactMarkdown skipHtml components={{ p: ({ children }) => <span>{children}</span> }}>{section.tip}</ReactMarkdown>
                  </div>
                </div>
              )}

              <button
                type="button"
                onClick={() => toggleReviewed(section.title)}
                aria-pressed={isDone}
                className={`mt-4 inline-flex items-center gap-1.5 self-start rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  isDone
                    ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                    : 'border border-slate-200 text-slate-600 hover:border-amber-400 hover:text-slate-900'
                }`}
              >
                <BookOpenCheck className="h-3.5 w-3.5" />
                {isDone ? 'Reviewed' : 'Mark as reviewed'}
              </button>
            </li>
          );
        })}
      </ol>

      {allDone && (
        <div className="animate-in fade-in zoom-in-95 flex flex-col items-center justify-between gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-center sm:flex-row sm:text-left">
          <div className="flex items-center gap-3">
            <PartyPopper className="h-6 w-6 shrink-0 text-emerald-600" />
            <div>
              <p className="font-bold text-emerald-900">You've reviewed every section.</p>
              <p className="text-xs text-emerald-800">Test what stuck with a quick quiz.</p>
            </div>
          </div>
          {onStartQuiz && (
            <button
              type="button"
              onClick={onStartQuiz}
              className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-emerald-700"
            >
              Take a quiz
            </button>
          )}
        </div>
      )}

      {keyTerms.length > 0 && (
        <p className="text-center text-[11px] text-slate-500">
          Tip: underlined words are key terms. Hover or tap them for the definition.
        </p>
      )}
    </div>
  );
}
