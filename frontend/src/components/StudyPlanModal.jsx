import React, { useState } from 'react';
import { 
  Calendar, 
  X, 
  Sparkles 
} from 'lucide-react';
import Mascot from './Mascot';

// "YYYY-MM-DD" in the student's local calendar (toISOString would use UTC and can be a day off)
const toDateInputValue = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export default function StudyPlanModal({ isOpen, onClose, documentTitle, topics = [] }) {
  const [examDate, setExamDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 5);
    return toDateInputValue(d);
  });
  const [hoursPerDay, setHoursPerDay] = useState(2);
  const [plan, setPlan] = useState(null);

  if (!isOpen) return null;

  const handleGeneratePlan = (e) => {
    e.preventDefault();
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const [year, month, day] = examDate.split('-').map(Number);
    const target = new Date(year, month - 1, day);
    const daysLeft = Math.max(1, Math.round((target - today) / (1000 * 60 * 60 * 24)));

    // Generate daily itinerary
    const daysPlan = [];
    for (let day = 1; day <= daysLeft; day++) {
      if (day === 1) {
        daysPlan.push({
          day: 1,
          title: "Introduction & Building the Foundation",
          tasks: [
            "Read the Detailed Summary of the whole module.",
            "Memorize the first set of Key Terms.",
            `Spend ${hoursPerDay} hour${hoursPerDay > 1 ? 's' : ''} understanding the core concepts.`
          ]
        });
      } else if (day === daysLeft) {
        daysPlan.push({
          day: daysLeft,
          title: "Final Prep & Rest (Exam Eve)",
          tasks: [
            "Just do a quick review of the Brief summary.",
            "Review the difficult flashcards you flagged.",
            "Sleep early! Don't stay up late so your mind is fresh tomorrow."
          ]
        });
      } else if (day === daysLeft - 1) {
        daysPlan.push({
          day: day,
          title: "Mock Exam & Weak-Spot Drill",
          tasks: [
            "Take a Weak-Spot Quiz on the topics you're unsure about.",
            "Try Timed Exam Mode to get used to the pace.",
            "Review the explanation for every wrong answer."
          ]
        });
      } else {
        daysPlan.push({
          day: day,
          title: `Deep Study - Day ${day}`,
          tasks: [
            "Clear the Due Flashcards in the Spaced Repetition queue.",
            "Try a 10-item Quiz at Medium to Hard difficulty.",
            "Use the 'Ask Kabisado' chat to clear up anything confusing."
          ]
        });
      }
    }

    // Spread the module's topics over the study days, so every topic gets a day before the mock exam
    const lastStudyDay = Math.max(1, daysLeft - 2);
    const studyDays = daysPlan.filter((d) => d.day <= lastStudyDay);
    const topicTitles = topics.map((t) => t.title);
    studyDays.forEach((d, i) => {
      const start = Math.floor((i * topicTitles.length) / studyDays.length);
      const end = Math.floor(((i + 1) * topicTitles.length) / studyDays.length);
      const focus = topicTitles.slice(start, end);
      if (focus.length) d.tasks.unshift(`Focus topics: ${focus.join('; ')}`);
    });

    setPlan({
      daysLeft,
      hoursPerDay,
      totalHours: daysLeft * hoursPerDay,
      itinerary: daysPlan
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 my-8 animate-in zoom-in-95">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-100 text-amber-800 rounded-xl">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-extrabold text-slate-900 text-lg">
                Study Plan by Exam Date 📅
              </h2>
              <p className="text-xs text-slate-500">
                Kabi will build a schedule for {documentTitle || 'your module'} so you don't have to cram!
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
                Pick your exam date so we can work out how many days and hours to spend on each topic.
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                When is your exam?
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
                How many hours can you study each day?
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
                    {hr} {hr === 1 ? 'hour' : 'hours'} / day
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
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow-md transition flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>Create Study Plan</span>
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
                <h3 className="text-2xl font-black">{plan.daysLeft} {plan.daysLeft === 1 ? 'Day' : 'Days'} Left!</h3>
                <p className="text-xs text-amber-100 mt-0.5">
                  {plan.totalHours} total study hours ({plan.hoursPerDay} hrs/day)
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
                ← Adjust Date / Hours
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow transition"
              >
                Start Day 1!
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
