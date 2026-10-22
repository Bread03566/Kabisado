import React, { useState } from 'react';
import { 
  Calendar, 
  Clock, 
  CheckCircle2, 
  X, 
  Sparkles, 
  BookOpen, 
  BrainCircuit, 
  HelpCircle,
  AlertCircle
} from 'lucide-react';
import Mascot from './Mascot';

export default function StudyPlanModal({ isOpen, onClose, documentTitle, topicsCount = 4 }) {
  const [examDate, setExamDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 5);
    return d.toISOString().split('T')[0];
  });
  const [hoursPerDay, setHoursPerDay] = useState(2);
  const [plan, setPlan] = useState(null);

  if (!isOpen) return null;

  const handleGeneratePlan = (e) => {
    e.preventDefault();
    const today = new Date();
    const target = new Date(examDate);
    const diffTime = target.getTime() - today.getTime();
    const daysLeft = Math.max(1, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));

    // Generate daily itinerary
    const daysPlan = [];
    for (let day = 1; day <= daysLeft; day++) {
      if (day === 1) {
        daysPlan.push({
          day: 1,
          title: "Panimula at Pagbuo ng Foundation",
          tasks: [
            "Basahin ang Detalyadong Buod ng buong module.",
            "Kabisaduhin ang unang set ng Key Terms.",
            `Mag-laan ng ${hoursPerDay} oras sa pag-unawa ng mga pangunahing konsepto.`
          ]
        });
      } else if (day === daysLeft) {
        daysPlan.push({
          day: daysLeft,
          title: "Huling Paghahanda & Pahinga (Exam Eve)",
          tasks: [
            "Mabilisan (Brief) summary review na lang.",
            "Reviewhin ang mga na-flag mong mahihirap na flashcards.",
            "Matulog nang maaga! Wag nang mag-puyat para presko ang utak bukas."
          ]
        });
      } else if (day === daysLeft - 1) {
        daysPlan.push({
          day: day,
          title: "Mock Exam at Weak-Spot Drill",
          tasks: [
            "Kumuha ng Weak-Spot Quiz para sa mga paksang alanganin.",
            "Subukan ang Timed Exam Mode para masanay sa bilis.",
            "I-review ang mga paliwanag sa bawat maling sagot."
          ]
        });
      } else {
        daysPlan.push({
          day: day,
          title: `Malalimang Aral - Araw ${day}`,
          tasks: [
            "I-clear ang Due Flashcards sa Spaced Repetition queue.",
            "Subukan ang 10-item Quiz na may Medium to Hard difficulty.",
            "Gamitin ang 'Ask Kabisado' chat para linawin ang mga di maintindihan."
          ]
        });
      }
    }

    setPlan({
      daysLeft,
      hoursPerDay,
      totalHours: daysLeft * hoursPerDay,
      itinerary: daysPlan
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 my-8 animate-in zoom-in-95">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-100 text-amber-800 rounded-xl">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-extrabold text-slate-900 text-lg">
                Study Plan ayon sa Araw ng Exam 📅
              </h2>
              <p className="text-xs text-slate-500">
                Awtomatikong gagawa si Kabi ng iskedyul para hindi ka mag-cram!
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {!plan ? (
          <form onSubmit={handleGeneratePlan} className="py-6 space-y-4">
            <div className="bg-amber-50/70 border border-amber-200 rounded-2xl p-4 flex items-center gap-3">
              <Mascot mood="studying" size="sm" />
              <p className="text-xs text-amber-900 font-medium">
                Piliin kung kailan ang exam para ma-compute natin kung ilang araw at oras ang dapat mong ilaan bawat paksa.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Kailan ang iyong Exam Date?
              </label>
              <input
                type="date"
                value={examDate}
                onChange={(e) => setExamDate(e.target.value)}
                required
                className="w-full text-xs sm:text-sm p-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 font-semibold text-slate-800"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Ilang oras ang kaya mong aralin bawat araw?
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[1, 2, 3, 4].map((hr) => (
                  <button
                    key={hr}
                    type="button"
                    onClick={() => setHoursPerDay(hr)}
                    className={`py-2 text-xs font-bold rounded-xl border transition ${
                      hoursPerDay === hr
                        ? 'bg-amber-500 text-white border-amber-600 shadow-xs'
                        : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {hr} Oras / araw
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Kanselahin
              </button>
              <button
                type="submit"
                className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow-md transition flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>Gumawa ng Study Plan</span>
              </button>
            </div>
          </form>
        ) : (
          <div className="py-6 space-y-6">
            {/* Plan Header Summary */}
            <div className="bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-2xl p-5 flex items-center justify-between shadow-sm">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-amber-100">
                  Target Exam
                </span>
                <h3 className="text-2xl font-black">{plan.daysLeft} Araw Na Lang!</h3>
                <p className="text-xs text-amber-100 mt-0.5">
                  Kabuuang {plan.totalHours} oras ng aral ({plan.hoursPerDay} oras/araw)
                </p>
              </div>
              <Mascot mood="happy" size="md" />
            </div>

            {/* Daily Roadmap Timeline */}
            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {plan.itinerary.map((item) => (
                <div
                  key={item.day}
                  className="p-4 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-2 hover:border-amber-300 transition"
                >
                  <div className="flex items-center justify-between text-xs font-extrabold text-slate-900">
                    <span className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded-lg bg-amber-100 text-amber-900 flex items-center justify-center text-[11px]">
                        {item.day}
                      </span>
                      <span>{item.title}</span>
                    </span>
                    <span className="text-[10px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                      Day {item.day} of {plan.daysLeft}
                    </span>
                  </div>

                  <ul className="space-y-1.5 pl-8 text-xs text-slate-600 list-disc">
                    {item.tasks.map((task, tIdx) => (
                      <li key={tIdx} className="leading-relaxed">
                        {task}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setPlan(null)}
                className="text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                ← I-adjust ang Petsa / Oras
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow transition"
              >
                Simulan ang Araw 1!
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
