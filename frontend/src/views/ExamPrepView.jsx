import React, { useState } from 'react';
import { CalendarDays, GraduationCap, Loader2, ClipboardCheck } from 'lucide-react';
import { getExamPlan, getExamPractice, submitExam } from '../services/api';

const STATUS_STYLE = {
  weak: 'bg-red-100 text-red-800',
  reviewing: 'bg-amber-100 text-amber-800',
  mastered: 'bg-emerald-100 text-emerald-800',
  untested: 'bg-slate-200 text-slate-700',
};

function PlanDays({ plan }) {
  return (
    <ol className="space-y-3">
      {plan.days.map((d) => (
        <li key={d.day} className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-extrabold text-slate-900">
              Day {d.day}{d.final_review ? ' · Final review & practice exam' : ''}
            </h3>
            <span className="text-xs text-slate-500">about {d.minutes} min</span>
          </div>
          {d.topics.length === 0 ? (
            <p className="mt-2 text-xs text-slate-500">Light day. Rest, or redo flashcards you missed.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {d.topics.map((t) => (
                <li key={`${d.day}-${t.topic_id}`} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${STATUS_STYLE[t.status]}`}>{t.status}</span>
                  <span className="font-semibold text-slate-800">{t.title}</span>
                  <span className="text-xs text-slate-500">{t.document_title} · {t.minutes} min</span>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  );
}

function Question({ q, value, onChange }) {
  const idName = `q-${q.id}`;
  return (
    <fieldset className="rounded-2xl border border-slate-200 bg-white p-4">
      <legend className="px-1 text-sm font-bold text-slate-900">{q.question_text}</legend>
      <p className="text-[11px] text-slate-500 mb-2">{q.topic_title}</p>
      {q.question_type === 'identification' ? (
        <input
          type="text"
          maxLength={300}
          value={value?.text_answer || ''}
          onChange={(e) => onChange({ text_answer: e.target.value })}
          aria-label="Your answer"
          className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
        />
      ) : (
        <div className="space-y-1.5">
          {q.choices.map((c, i) => (
            <label key={i} className="flex items-start gap-2 text-sm cursor-pointer">
              <input type="radio" name={idName} checked={value?.selected_index === i}
                onChange={() => onChange({ selected_index: i })} className="mt-1 h-4 w-4 accent-amber-500" />
              <span>{c}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

export default function ExamPrepView({ documents, showToast }) {
  const [selected, setSelected] = useState([]);
  const [days, setDays] = useState(7);
  const [plan, setPlan] = useState(null);
  const [exam, setExam] = useState(null);
  const [answers, setAnswers] = useState({});
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState('');

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const run = async (label, fn) => {
    setBusy(label);
    try { await fn(); } catch (e) { showToast?.('error', e.message); } finally { setBusy(''); }
  };

  const buildPlan = () => run('plan', async () => {
    setReport(null); setExam(null);
    setPlan(await getExamPlan(selected, Number(days)));
  });
  const startExam = () => run('exam', async () => {
    setReport(null); setAnswers({});
    const res = await getExamPractice(selected, 15);
    if (!res.questions.length) { showToast?.('error', res.note); setExam(null); return; }
    setExam(res.questions);
  });
  const finish = () => run('submit', async () => {
    const payload = exam.map((q) => ({ question_id: q.id, ...(answers[q.id] || {}) }))
      .filter((a) => a.selected_index !== undefined || a.text_answer);
    if (!payload.length) { showToast?.('error', 'Answer at least one question first.'); return; }
    setReport(await submitExam(payload));
    setExam(null);
    setPlan(await getExamPlan(selected, Number(days))); // the plan now reflects what the exam showed
  });

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-5">
      <div className="flex items-center gap-2">
        <GraduationCap className="w-6 h-6 text-amber-600" />
        <h1 className="text-xl font-extrabold text-slate-900">Exam Prep</h1>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3" aria-label="Choose modules">
        <h2 className="text-sm font-extrabold text-slate-900">1. Pick the modules for your exam</h2>
        {documents.length === 0 && <p className="text-sm text-slate-500">Add a module in the Library first.</p>}
        <div className="space-y-1.5">
          {documents.map((d) => (
            <label key={d.id} className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} className="h-4 w-4 accent-amber-500" />
              <span translate="no">{d.title}</span>
            </label>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm">
          <CalendarDays className="w-4 h-4 text-slate-500" />
          Days until the exam
          <input type="number" min={1} max={60} value={days} onChange={(e) => setDays(e.target.value)}
            className="w-20 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
        </label>
        <button type="button" onClick={buildPlan} disabled={!selected.length || busy === 'plan' || days < 1 || days > 60}
          className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-2 text-sm font-bold text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-slate-300">
          {busy === 'plan' && <Loader2 className="w-4 h-4 animate-spin" />} Build my plan
        </button>
      </section>

      {plan && (
        <section className="space-y-3" aria-label="Study plan">
          <h2 className="text-sm font-extrabold text-slate-900">2. Your plan</h2>
          <p className="text-xs text-slate-600">
            {plan.summary.topics} topics: {plan.summary.weak} weak, {plan.summary.reviewing} need review,
            {' '}{plan.summary.untested} not tested yet, {plan.summary.mastered} mastered. Weak and important topics come first.
          </p>
          <PlanDays plan={plan} />
          <button type="button" onClick={startExam} disabled={busy === 'exam'}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-800 hover:bg-slate-50">
            {busy === 'exam' ? <Loader2 className="w-4 h-4 animate-spin" /> : <ClipboardCheck className="w-4 h-4" />} Start practice exam
          </button>
        </section>
      )}

      {exam && (
        <section className="space-y-3" aria-label="Practice exam">
          <h2 className="text-sm font-extrabold text-slate-900">3. Practice exam ({exam.length} questions)</h2>
          {exam.map((q) => (
            <Question key={q.id} q={q} value={answers[q.id]} onChange={(v) => setAnswers((a) => ({ ...a, [q.id]: v }))} />
          ))}
          <button type="button" onClick={finish} disabled={busy === 'submit'}
            className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-2 text-sm font-bold text-white hover:bg-amber-600 disabled:opacity-50">
            {busy === 'submit' && <Loader2 className="w-4 h-4 animate-spin" />} Finish and see my report
          </button>
        </section>
      )}

      {report && (
        <section className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3" aria-label="Exam report" role="status">
          <h2 className="text-sm font-extrabold text-slate-900">Your report</h2>
          <p className="text-2xl font-extrabold text-slate-900">{report.percentage}% <span className="text-base font-bold text-amber-700">· {report.readiness}</span></p>
          <p className="text-xs text-slate-500">{report.score} of {report.total} correct. Weakest topics first:</p>
          <ul className="space-y-1 text-sm">
            {report.topics.map((t) => (
              <li key={`${t.document_title}-${t.topic_title}`} className="flex justify-between gap-3">
                <span>{t.topic_title} <span className="text-xs text-slate-500">({t.document_title})</span></span>
                <span className="font-bold">{t.correct}/{t.total}</span>
              </li>
            ))}
          </ul>
          <details className="text-sm">
            <summary className="cursor-pointer font-bold text-slate-700">Review each answer</summary>
            <ul className="mt-2 space-y-2">
              {report.results.map((r) => (
                <li key={r.question_id} className={`rounded-xl border p-3 ${r.is_correct ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
                  <p className="font-semibold">{r.question_text}</p>
                  <p className="text-xs">Your answer: {r.your_answer || '(blank)'} · Correct: {r.correct_answer}</p>
                  {!r.is_correct && <p className="text-xs text-slate-600">{r.explanation}</p>}
                </li>
              ))}
            </ul>
          </details>
        </section>
      )}
    </div>
  );
}
