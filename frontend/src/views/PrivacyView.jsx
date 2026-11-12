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
        <ArrowLeft className="w-4 h-4" /> Bumalik
      </button>
      <h1 className="mt-3 text-xl font-extrabold text-slate-900">Privacy: ano ang sine-save namin</h1>
      <p className="mt-1 text-sm text-slate-600">Maikli at diretso. Walang ads, walang tracking, at hindi namin ibinebenta ang data mo.</p>

      <Section title="Ano ang naka-store">
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Username</strong> at <strong>display name</strong> mo.</li>
          <li>Ang <strong>password hash</strong> at <strong>recovery-code hash</strong> — hindi ang mismong password o code. Hindi namin sila mababasa.</li>
          <li><strong>Session info</strong>: kailan ka nag-login at anong browser (naka-hash), para ma-log out ka sa ibang device.</li>
          <li>Ang <strong>study content mo</strong>: mga module na ina-upload mo, summaries, flashcards, quizzes, scores at progress.</li>
        </ul>
        <p>Walang email, phone number, o Gmail na hinihingi.</p>
      </Section>

      <Section title="Bakit">
        <p>Para makapag-login ka, mahiwalay ang data mo sa iba, at maipagpatuloy mo ang pag-aaral sa ibang araw.</p>
      </Section>

      <Section title="Gaano katagal">
        <p>Ang login at session metadata ay binubura pagkalipas ng <strong>30 araw</strong>. Ang study content mo ay nananatili hangga&apos;t hindi mo binubura ang account.</p>
      </Section>

      <Section title="Sino ang nagpapatakbo ng app (processors)">
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Render</strong> — nagho-host ng server.</li>
          <li><strong>Supabase</strong> — nag-iimbak ng database.</li>
          <li><strong>GitHub</strong> — nagho-host ng code at ng wake-up page.</li>
        </ul>
      </Section>

      <Section title="AI (Gemini)">
        <p><strong>Naka-off ang Gemini.</strong> Walang laman ng module mo na ipinapadala sa anumang AI service. Gumagamit ang app ng simpleng offline na bersyon ng summaries, flashcards at quizzes.</p>
      </Section>

      <Section title="Pagbura ng account">
        <p>Mula sa account settings, ilagay ang password mo para <strong>burahin ang account</strong>; agad nabubura ang account mo at lahat ng study content na nakakabit dito. Pwede mo rin itong i-<strong>deactivate</strong> muna para hindi ka makapag-login. Hindi ito mababawi.</p>
      </Section>
    </div>
  );
}
