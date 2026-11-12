import React from 'react';
import { ArrowLeft } from 'lucide-react';

const Section = ({ title, children }) => (
  <section className="mt-5">
    <h2 className="text-sm font-extrabold text-slate-900">{title}</h2>
    <div className="mt-1 text-sm text-slate-600 space-y-1">{children}</div>
  </section>
);

export default function PrivacyView({ onBack }) {
  return (
    <div className="max-w-2xl mx-auto bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-800">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>
      <h1 className="mt-3 text-xl font-extrabold text-slate-900">Privacy: what we store</h1>
      <p className="mt-1 text-sm text-slate-600">Short and plain. No ads, no tracking, and we do not sell your data.</p>

      <Section title="What is stored">
        <ul className="list-disc pl-5 space-y-1">
          <li>Your <strong>username</strong> and <strong>display name</strong>.</li>
          <li>A <strong>password hash</strong> and a <strong>recovery-code hash</strong>, not the password or code themselves. We cannot read them.</li>
          <li><strong>Session information</strong>: when you signed in and which browser (hashed), so you can be signed out of other devices.</li>
          <li>Your <strong>study content</strong>: the modules you upload, summaries, flashcards, quizzes, scores and progress.</li>
        </ul>
        <p>We do not ask for an email address, phone number or Gmail account.</p>
      </Section>

      <Section title="Why">
        <p>So you can sign in, keep your data separate from everyone else&apos;s, and continue studying another day.</p>
      </Section>

      <Section title="How long">
        <p>Sign-in and session records are deleted after <strong>30 days</strong>. Your study content stays until you delete your account.</p>
      </Section>

      <Section title="Who runs the app (processors)">
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Render</strong> hosts the server.</li>
          <li><strong>Supabase</strong> stores the database.</li>
          <li><strong>GitHub</strong> hosts the code and the wake-up page.</li>
        </ul>
      </Section>

      <Section title="AI (Gemini)">
        <p><strong>Gemini is switched off.</strong> None of your module content is sent to any AI service. The app uses a simple offline version of summaries, flashcards and quizzes.</p>
      </Section>

      <Section title="Deleting your account">
        <p>Open your account menu and enter your password to <strong>delete your account</strong>. Your account and all the study content attached to it are removed immediately. You can also <strong>deactivate</strong> it first, which stops anyone signing in. Deletion cannot be undone.</p>
      </Section>
    </div>
  );
}
