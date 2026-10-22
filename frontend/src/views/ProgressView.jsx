import React, { useState, useEffect } from 'react';
import { 
  Flame, 
  Clock, 
  Target, 
  Layers, 
  AlertTriangle, 
  CheckCircle2, 
  BrainCircuit, 
  HelpCircle, 
  Sparkles, 
  ArrowRight,
  TrendingUp,
  BarChart3,
  Calendar,
  RotateCcw
} from 'lucide-react';
import Mascot from '../components/Mascot';
import { getDashboardStats } from '../services/api';

export default function ProgressView({ 
  onStartDueCards, 
  onStartWeakSpotQuiz, 
  onSelectTopicQuiz, 
  showToast 
}) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    setIsLoading(true);
    try {
      const data = await getDashboardStats();
      setStats(data);
    } catch (err) {
      showToast('error', 'Hindi ma-load ang dashboard stats.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-20 text-center flex flex-col items-center justify-center space-y-4">
        <Mascot mood="studying" size="lg" />
        <p className="text-sm font-bold text-slate-700 animate-pulse">
          Kinakalkula ni Kabi ang iyong progress...
        </p>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header & Mascot Motivation */}
      <div className="bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 rounded-3xl p-6 sm:p-8 text-white shadow-lg flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="space-y-2 text-center sm:text-left max-w-xl">
          <span className="inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-white/20 backdrop-blur-md">
            📊 Talaan ng Kaalaman
          </span>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">
            Ang Iyong Kabisado Dashboard
          </h1>
          <p className="text-amber-100 text-xs sm:text-sm leading-relaxed">
            Subaybayan ang iyong study streak, mastery rate bawat paksa, at mga dapat balikang aralin para siguradong pasa sa exam.
          </p>
        </div>

        <Mascot 
          mood={stats.mascot_mood || "studying"} 
          size="lg" 
          message={stats.mascot_message}
        />
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Streak */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Study Streak
            </span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-3xl font-black text-slate-900">
                {stats.streak_days}
              </span>
              <span className="text-xs font-bold text-slate-500">araw</span>
            </div>
            <p className="text-[11px] text-amber-600 font-semibold mt-1">
              {stats.streak_days > 0 ? "🔥 Tuloy-tuloy ang aral!" : "Simulan ang streak ngayon!"}
            </p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <Flame className="w-6 h-6" />
          </div>
        </div>

        {/* Cards Due Today */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Due Flashcards
            </span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-3xl font-black text-indigo-600">
                {stats.cards_due_today}
              </span>
              <span className="text-xs font-bold text-slate-400">/ {stats.total_cards}</span>
            </div>
            {stats.cards_due_today > 0 ? (
              <button
                onClick={onStartDueCards}
                className="text-[11px] text-indigo-600 font-bold hover:underline flex items-center gap-1 mt-1"
              >
                <span>Aralin na ngayon</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            ) : (
              <p className="text-[11px] text-emerald-600 font-semibold mt-1">
                ✓ Tapos na ang due cards!
              </p>
            )}
          </div>
          <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Clock className="w-6 h-6" />
          </div>
        </div>

        {/* Overall Accuracy */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Quiz Accuracy
            </span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-3xl font-black text-emerald-600">
                {stats.overall_accuracy}%
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-semibold mt-1">
              {stats.total_quizzes_taken} quizzes na-submit
            </p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Target className="w-6 h-6" />
          </div>
        </div>

        {/* Total Modules Mastered */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Topics Tracked
            </span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-3xl font-black text-slate-900">
                {stats.topic_mastery?.length || 0}
              </span>
              <span className="text-xs font-bold text-slate-500">paksa</span>
            </div>
            <p className="text-[11px] text-slate-500 font-semibold mt-1">
              {stats.topic_mastery?.filter((t) => t.status === "mastered").length || 0} kabisado na
            </p>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center">
            <Layers className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* WEAK SPOTS SECTION (PHASE 3 HIGHLIGHT) */}
      {stats.weak_topics && stats.weak_topics.length > 0 && (
        <div className="bg-rose-50/60 border border-rose-200 rounded-3xl p-6 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-rose-100 text-rose-700 rounded-xl">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h2 className="font-extrabold text-slate-900 text-base sm:text-lg">
                  Mga Mahihinang Paksa (Weak Topics)
                </h2>
                <p className="text-xs text-rose-800">
                  Dito ka pinakamadalas magkamali o hindi pa nasusubukan. Tutukan natin ito!
                </p>
              </div>
            </div>

            <button
              onClick={() => onStartWeakSpotQuiz(stats.weak_topics[0]?.document_id)}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition active:scale-95"
            >
              <Sparkles className="w-4 h-4" />
              <span>Mag-Quiz sa Mahihinang Paksa (Weak-Spot Quiz)</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
            {stats.weak_topics.slice(0, 3).map((w, idx) => (
              <div
                key={idx}
                className="bg-white rounded-2xl border border-rose-200 p-4 shadow-xs space-y-2 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-bold text-rose-700 uppercase tracking-wide text-[10px] bg-rose-100 px-2 py-0.5 rounded-full">
                      {w.status === "untested" ? "Di pa nasusubukan" : `${w.mastery_percent}% Mastery`}
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      {w.correct_count}/{w.total_answered} tama
                    </span>
                  </div>
                  <h3 className="font-bold text-slate-900 text-xs sm:text-sm line-clamp-2">
                    {w.topic_title}
                  </h3>
                </div>

                <div className="pt-2 border-t border-slate-100">
                  <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                    <div 
                      className="bg-rose-500 h-full rounded-full" 
                      style={{ width: `${w.mastery_percent}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PER-TOPIC MASTERY BREAKDOWN */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-amber-500" />
              <span>Antas ng Pagkabisado Bawat Paksa</span>
            </h2>
            <p className="text-xs text-slate-500">
              Computed mastery batay sa iyong quiz attempts at flashcard reviews.
            </p>
          </div>
        </div>

        {(!stats.topic_mastery || stats.topic_mastery.length === 0) ? (
          <div className="p-8 text-center text-xs text-slate-500">
            Wala pang datos para sa topics. Mag-take muna ng quiz para makita ang stats!
          </div>
        ) : (
          <div className="space-y-4">
            {stats.topic_mastery.map((topic, index) => {
              const isMastered = topic.status === "mastered";
              const isReviewing = topic.status === "reviewing";
              const isUntested = topic.status === "untested";

              let badgeColor = "bg-rose-50 text-rose-700 border-rose-200";
              let barColor = "bg-rose-500";
              let label = "Medyo Sabaw / Reviewhin";

              if (isMastered) {
                badgeColor = "bg-emerald-50 text-emerald-800 border-emerald-200";
                barColor = "bg-emerald-500";
                label = "Kabisado Na!";
              } else if (isReviewing) {
                badgeColor = "bg-amber-50 text-amber-800 border-amber-200";
                barColor = "bg-amber-500";
                label = "Nangangailangan ng Kembot";
              } else if (isUntested) {
                badgeColor = "bg-slate-50 text-slate-600 border-slate-200";
                barColor = "bg-slate-300";
                label = "Wala pang Quiz";
              }

              return (
                <div
                  key={index}
                  className="p-4 rounded-2xl bg-slate-50/60 border border-slate-200 hover:border-slate-300 transition space-y-2.5"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-slate-900 text-xs sm:text-sm">
                        {topic.topic_title}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeColor}`}>
                        {label}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>{topic.correct_count} sa {topic.total_answered} tama</span>
                      <span className="font-bold text-slate-900">{topic.mastery_percent}%</span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${barColor}`} 
                      style={{ width: `${topic.mastery_percent}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* QUIZ SCORE TIMELINE & RECENT ACTIVITY */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-5">
        <h2 className="text-lg sm:text-xl font-bold text-slate-900 flex items-center gap-2">
          <Calendar className="w-5 h-5 text-indigo-500" />
          <span>Kasaysayan ng mga Pagsusulit (Recent Attempts)</span>
        </h2>

        {(!stats.quiz_history || stats.quiz_history.length === 0) ? (
          <div className="p-8 text-center text-xs text-slate-500">
            Wala ka pang nasasagutang quiz. Subukan mo na ang unang pagsusulit sa module mo!
          </div>
        ) : (
          <div className="space-y-3">
            {stats.quiz_history.map((att, idx) => (
              <div
                key={idx}
                className="p-3.5 sm:p-4 rounded-2xl border border-slate-200 flex items-center justify-between hover:bg-slate-50 transition"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl font-black text-xs flex items-center justify-center shrink-0 ${
                    att.percentage >= 80 ? 'bg-emerald-100 text-emerald-800' :
                    att.percentage >= 50 ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'
                  }`}>
                    {att.percentage}%
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-xs sm:text-sm">
                      {att.document_title}
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      {att.completed_at ? new Date(att.completed_at).toLocaleDateString() : 'Kamakailan'} • Antas: {att.difficulty}
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <span className="font-bold text-xs text-slate-900 block">
                    {att.score} / {att.total_questions}
                  </span>
                  <span className="text-[10px] text-slate-400">Marka</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
