import React, { useState, useEffect, useRef } from 'react';
import { 
  ArrowLeft, 
  HelpCircle, 
  Sparkles, 
  CheckCircle2, 
  XCircle, 
  Flag, 
  RotateCcw, 
  ArrowRight, 
  BrainCircuit, 
  Award,
  Clock,
  Volume2,
  AlertTriangle,
  Timer
} from 'lucide-react';
import confetti from 'canvas-confetti';
import Mascot from '../components/Mascot';
import FlagModal from '../components/FlagModal';
import { getQuestions, generateQuiz, submitQuizAttempt, generateWeakSpotQuiz } from '../services/api';

export default function QuizMode({ 
  documentId, 
  initialTopicId = null, 
  isWeakSpotMode = false,
  onBack, 
  onGoToFlashcards,
  showToast 
}) {
  const [questions, setQuestions] = useState([]); // the quiz being taken right now
  const [savedQuestions, setSavedQuestions] = useState([]); // every question made for this module
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [hasAnsweredCurrent, setHasAnsweredCurrent] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [quizResult, setQuizResult] = useState(null);

  // Setup options
  const [targetCount, setTargetCount] = useState(5);
  const [selectedDifficulty, setSelectedDifficulty] = useState('medium');
  const [showFlagModal, setShowFlagModal] = useState(false);

  // Phase 4: Exam Mode with Timer
  const [isExamMode, setIsExamMode] = useState(false);
  const [timerDuration, setTimerDuration] = useState(10); // in minutes
  const [secondsRemaining, setSecondsRemaining] = useState(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (isWeakSpotMode) {
      handleGenerateWeakSpots();
    } else {
      loadQuestions();
    }
  }, [documentId, initialTopicId, isWeakSpotMode]);

  // Exam Timer Effect: tick once a second, auto-submit when time runs out
  useEffect(() => {
    if (secondsRemaining === null || quizResult) return;
    if (secondsRemaining <= 0) {
      handleFinishQuiz();
      return;
    }
    const tick = setTimeout(() => setSecondsRemaining((prev) => prev - 1), 1000);
    return () => clearTimeout(tick);
  }, [secondsRemaining, quizResult]);

  const loadQuestions = async () => {
    setIsLoading(true);
    try {
      const data = await getQuestions(documentId, initialTopicId);
      setSavedQuestions(data);
      setQuestions([]);
      resetQuizState();
    } catch {
      showToast('error', 'Could not load quiz questions.');
    } finally {
      setIsLoading(false);
    }
  };

  const resetQuizState = () => {
    setCurrentIndex(0);
    setSelectedAnswers({});
    setHasAnsweredCurrent(false);
    setQuizResult(null);
    setSecondsRemaining(null);
  };

  const startQuiz = (quizQuestions) => {
    setQuestions(quizQuestions);
    resetQuizState();
    if (isExamMode) {
      setSecondsRemaining(timerDuration * 60);
    }
  };

  const handlePracticeSaved = () => {
    const picked = [...savedQuestions].sort(() => Math.random() - 0.5).slice(0, targetCount);
    startQuiz(picked);
  };

  const handleGenerateQuestions = async () => {
    setIsGenerating(true);
    try {
      showToast('info', 'Kabi is preparing some killer quiz questions...');
      const newQuestions = await generateQuiz(
        documentId, 
        targetCount, 
        initialTopicId, 
        selectedDifficulty
      );
      setSavedQuestions((prev) => [...newQuestions, ...prev]);
      startQuiz(newQuestions);
      showToast('success', `${newQuestions.length} questions are ready for you!`);
    } catch (err) {
      showToast('error', err.message || 'Failed to create quiz questions.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateWeakSpots = async () => {
    setIsGenerating(true);
    try {
      showToast('info', 'Building a Weak-Spot Quiz from the topics you struggle with...');
      const weakQuestions = await generateWeakSpotQuiz(documentId);
      setSavedQuestions((prev) => [...weakQuestions, ...prev]);
      startQuiz(weakQuestions);
      showToast('success', 'Your Weak-Spot Quiz is ready! Let\'s go!');
    } catch (err) {
      showToast('error', err.message || 'Failed to create the weak-spot quiz.');
    } finally {
      setIsGenerating(false);
      setIsLoading(false);
    }
  };

  const handleSelectChoice = (choiceIndex) => {
    if (hasAnsweredCurrent) return;

    const currentQ = questions[currentIndex];
    setSelectedAnswers((prev) => ({
      ...prev,
      [currentQ.id]: choiceIndex
    }));
    setHasAnsweredCurrent(true);
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      const nextQ = questions[currentIndex + 1];
      setHasAnsweredCurrent(selectedAnswers[nextQ?.id] !== undefined);
    } else {
      handleFinishQuiz();
    }
  };

  const handleFinishQuiz = async () => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSecondsRemaining(null);
    setIsSubmitting(true);
    try {
      const answersPayload = questions.map((q) => ({
        question_id: q.id,
        selected_index: selectedAnswers[q.id] !== undefined ? selectedAnswers[q.id] : -1
      }));

      const result = await submitQuizAttempt(
        documentId, 
        answersPayload, 
        selectedDifficulty, 
        initialTopicId
      );
      setQuizResult(result);

      if (result.percentage >= 80) {
        confetti({
          particleCount: 120,
          spread: 80,
          origin: { y: 0.6 }
        });
      }
    } catch {
      showToast('error', 'There was a problem submitting your quiz results.');
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  // Voice Mode: Read question aloud (Phase 4)
  const speakQuestion = (text) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const currentQ = questions[currentIndex];
  const userChoice = currentQ ? selectedAnswers[currentQ.id] : undefined;

  const formatTimer = (seconds) => {
    if (seconds === null) return null;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-black text-slate-900 flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-emerald-600" />
              <span>{isWeakSpotMode ? 'Weak-Spot Quiz' : isExamMode ? 'Timed Exam Mode ⏱️' : 'Kabisado Quiz Mode'}</span>
            </h1>
            <p className="text-xs text-slate-500">
              One question at a time, with instant grounded feedback.
            </p>
          </div>
        </div>

        {/* Exam Timer Display */}
        {secondsRemaining !== null && !quizResult && (
          <div className={`px-3 py-1.5 rounded-xl border flex items-center gap-2 font-mono font-bold text-xs ${
            secondsRemaining < 60
              ? 'bg-rose-100 border-rose-300 text-rose-800 animate-pulse'
              : 'bg-amber-50 border-amber-200 text-amber-900'
          }`}>
            <Clock className="w-4 h-4" />
            <span>{formatTimer(secondsRemaining)}</span>
          </div>
        )}

        {questions.length > 0 && !quizResult && (
          <button
            onClick={() => setShowFlagModal(true)}
            title="Flag this question"
            className="p-2 rounded-xl border border-slate-200 hover:bg-amber-50 text-slate-400 hover:text-amber-600 transition"
          >
            <Flag className="w-4 h-4" />
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="bg-white rounded-3xl border border-slate-200 p-16 text-center flex flex-col items-center justify-center space-y-4 shadow-sm">
          <Mascot mood="studying" size="lg" />
          <p className="text-sm font-bold text-slate-700 animate-pulse">
            Preparing the quiz...
          </p>
        </div>
      ) : questions.length === 0 ? (
        /* Setup / Configuration Form */
        <div className="bg-white rounded-3xl border border-slate-200 p-8 sm:p-12 text-center flex flex-col items-center justify-center space-y-6 shadow-sm">
          <Mascot mood="sleepy" size="lg" />
          <div className="max-w-md space-y-1">
            <h2 className="text-xl font-extrabold text-slate-900">
              Choose Your Quiz Settings
            </h2>
            <p className="text-xs text-slate-500">
              Practice before the real exam:
            </p>
          </div>

          <div className="w-full max-w-sm space-y-4 text-left">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Number of Questions:
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[5, 10, 15].map((cnt) => (
                  <button
                    key={cnt}
                    type="button"
                    onClick={() => setTargetCount(cnt)}
                    className={`py-2 text-xs font-bold rounded-xl border transition ${
                      targetCount === cnt
                        ? 'bg-emerald-50 border-emerald-400 text-emerald-800 shadow-xs'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {cnt} Questions
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Difficulty:
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { id: 'easy', label: 'Easy' },
                  { id: 'medium', label: 'Medium' },
                  { id: 'hard', label: 'Hard' },
                  { id: 'mixed', label: 'Mixed' }
                ].map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setSelectedDifficulty(d.id)}
                    className={`py-2 text-xs font-bold rounded-xl border transition capitalize ${
                      selectedDifficulty === d.id
                        ? 'bg-emerald-50 border-emerald-400 text-emerald-800 shadow-xs'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Exam Mode with Timer Toggle (Phase 4) */}
            <div className="pt-2 border-t border-slate-100">
              <label className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-slate-50/70 cursor-pointer hover:bg-slate-100/70 transition">
                <div className="flex items-center gap-2.5">
                  <Timer className="w-5 h-5 text-amber-600" />
                  <div>
                    <span className="font-bold text-xs text-slate-900 block">Exam Mode with Timer</span>
                    <span className="text-[10px] text-slate-500">A countdown timer that tests your speed</span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={isExamMode}
                  onChange={(e) => setIsExamMode(e.target.checked)}
                  className="w-4 h-4 accent-amber-600 rounded"
                />
              </label>

              {isExamMode && (
                <div className="mt-2.5 flex items-center justify-between text-xs px-1">
                  <span className="font-semibold text-slate-600">Exam Time:</span>
                  <div className="flex gap-1.5">
                    {[5, 10, 15].map((mins) => (
                      <button
                        key={mins}
                        type="button"
                        onClick={() => setTimerDuration(mins)}
                        className={`px-2.5 py-1 rounded-lg border font-bold text-[11px] ${
                          timerDuration === mins
                            ? 'bg-amber-500 text-white border-amber-600'
                            : 'bg-white border-slate-200 text-slate-600'
                        }`}
                      >
                        {mins}m
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="w-full max-w-sm space-y-2">
            <button
              onClick={handleGenerateQuestions}
              disabled={isGenerating}
              className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <Sparkles className={`w-4 h-4 ${isGenerating ? 'animate-spin' : ''}`} />
              <span>{isGenerating ? 'Generating Questions...' : 'Start Quiz'}</span>
            </button>

            <button
              onClick={handleGenerateWeakSpots}
              disabled={isGenerating}
              className="w-full py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-800 border border-rose-200 font-bold text-xs rounded-xl transition flex items-center justify-center gap-1.5"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
              <span>Try the Weak-Spot Quiz</span>
            </button>

            {savedQuestions.length > 0 && (
              <button
                onClick={handlePracticeSaved}
                disabled={isGenerating}
                className="w-full py-2.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 font-bold text-xs rounded-xl transition flex items-center justify-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>
                  Practice {Math.min(targetCount, savedQuestions.length)} saved questions ({savedQuestions.length} in total)
                </span>
              </button>
            )}
          </div>
        </div>
      ) : quizResult ? (
        /* QUIZ SCORE REPORT & RESULTS */
        <div className="space-y-6 animate-in zoom-in-95">
          <div className="bg-white rounded-3xl border border-slate-200 p-8 sm:p-10 text-center shadow-lg space-y-4">
            <Mascot 
              mood={quizResult.percentage >= 80 ? "happy" : quizResult.percentage >= 50 ? "studying" : "shocked"} 
              size="xl" 
            />
            
            <div className="space-y-1">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">
                {quizResult.grade_message}
              </span>
              <h2 className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight pt-2">
                {quizResult.score} / {quizResult.total_questions}
              </h2>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                {quizResult.percentage}% Score
              </p>
            </div>

            <div className="max-w-md mx-auto p-4 rounded-2xl bg-amber-50/80 border border-amber-200 text-amber-950 text-xs sm:text-sm font-semibold leading-relaxed">
              "{quizResult.roast_or_praise}"
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-4 border-t border-slate-100">
              <button
                onClick={() => startQuiz(questions)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Retake Quiz</span>
              </button>

              <button
                onClick={() => {
                  setQuestions([]);
                  resetQuizState();
                }}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs sm:text-sm rounded-xl border border-slate-200 transition"
              >
                <Sparkles className="w-4 h-4" />
                <span>New Quiz</span>
              </button>

              <button
                onClick={() => onGoToFlashcards(documentId)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-800 font-bold text-xs sm:text-sm rounded-xl border border-indigo-200 transition"
              >
                <BrainCircuit className="w-4 h-4" />
                <span>Review with Flashcards</span>
              </button>

              <button
                onClick={onBack}
                className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs sm:text-sm rounded-xl transition"
              >
                Back to Module
              </button>
            </div>
          </div>

          {/* Detailed Question Review List */}
          <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-6">
            <h3 className="font-bold text-slate-900 text-base sm:text-lg flex items-center gap-2">
              <Award className="w-5 h-5 text-amber-500" />
              <span>Question-by-Question Review ({quizResult.results.length})</span>
            </h3>

            <div className="space-y-4">
              {quizResult.results.map((item, idx) => (
                <div
                  key={idx}
                  className={`p-4 sm:p-5 rounded-2xl border text-xs sm:text-sm space-y-3 ${
                    item.is_correct
                      ? 'bg-emerald-50/30 border-emerald-200'
                      : 'bg-rose-50/30 border-rose-200'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-extrabold text-slate-900">
                      {idx + 1}. {item.question_text}
                    </span>
                    {item.is_correct ? (
                      <span className="shrink-0 flex items-center gap-1 text-emerald-700 font-bold text-xs bg-emerald-100 px-2.5 py-1 rounded-full">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Correct</span>
                      </span>
                    ) : (
                      <span className="shrink-0 flex items-center gap-1 text-rose-700 font-bold text-xs bg-rose-100 px-2.5 py-1 rounded-full">
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Wrong</span>
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 rounded-xl bg-white border border-slate-200">
                      <span className="text-[11px] font-bold text-slate-400 block mb-0.5">Your answer:</span>
                      <span className={item.is_correct ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                        {item.selected_index >= 0 ? item.choices[item.selected_index] : 'No answer (Timeout)'}
                      </span>
                    </div>

                    {!item.is_correct && (
                      <div className="p-2.5 rounded-xl bg-white border border-emerald-300">
                        <span className="text-[11px] font-bold text-emerald-600 block mb-0.5">Correct answer:</span>
                        <span className="text-emerald-800 font-bold">
                          {item.choices[item.correct_index]}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-white/80 border border-slate-200 text-xs text-slate-600 leading-relaxed">
                    <span className="font-bold text-slate-800 block mb-0.5">Kabi's Explanation:</span>
                    {item.explanation}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* ACTIVE QUESTION SCREEN (One at a time) */
        <div className="space-y-6">
          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-slate-600">
              <span>Question {currentIndex + 1} of {questions.length}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => speakQuestion(currentQ?.question_text)}
                  title="Read the question aloud"
                  className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
                >
                  <Volume2 className="w-4 h-4" />
                </button>
                <span className={`px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wider font-extrabold ${
                  currentQ?.difficulty === 'easy' ? 'bg-emerald-100 text-emerald-800' :
                  currentQ?.difficulty === 'hard' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'
                }`}>
                  {currentQ?.difficulty || 'Medium'}
                </span>
              </div>
            </div>
            <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
              />
            </div>
          </div>

          {/* Question Card */}
          <div key={currentQ?.id} className="animate-in fade-in slide-in-from-right-4 bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-md space-y-6">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
                Choose one correct answer
              </span>
              {currentQ?.topic_title && (
                <span className="truncate max-w-[200px]">
                  Topic: {currentQ.topic_title}
                </span>
              )}
            </div>

            <h2 className="text-lg sm:text-xl font-black text-slate-900 leading-snug">
              {currentQ?.question_text}
            </h2>

            {/* 4 Multiple Choice Options */}
            <div className="space-y-3">
              {currentQ?.choices.map((choiceText, cIdx) => {
                const isSelected = userChoice === cIdx;
                const isCorrect = cIdx === currentQ.correct_index;

                let btnStyle = 'border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 text-slate-800';
                let letterStyle = 'bg-slate-100 text-slate-700';

                if (hasAnsweredCurrent) {
                  if (isCorrect) {
                    btnStyle = 'border-emerald-500 bg-emerald-50 text-emerald-950 font-bold ring-2 ring-emerald-500/30';
                    letterStyle = 'bg-emerald-600 text-white';
                  } else if (isSelected) {
                    btnStyle = 'border-rose-400 bg-rose-50 text-rose-950 font-bold';
                    letterStyle = 'bg-rose-600 text-white';
                  } else {
                    btnStyle = 'border-slate-100 text-slate-400 opacity-60';
                  }
                } else if (isSelected) {
                  btnStyle = 'border-emerald-500 bg-emerald-50 text-emerald-950 font-bold';
                  letterStyle = 'bg-emerald-600 text-white';
                }

                // Right answer pulses, a wrong pick shakes
                const feedbackAnim = hasAnsweredCurrent ? (isCorrect ? 'answer-correct' : isSelected ? 'answer-wrong' : '') : '';
                const letters = ['A', 'B', 'C', 'D'];

                return (
                  <button
                    key={cIdx}
                    onClick={() => handleSelectChoice(cIdx)}
                    disabled={hasAnsweredCurrent}
                    className={`w-full p-4 rounded-2xl border text-left transition flex items-center justify-between gap-3 text-xs sm:text-sm select-none ${btnStyle} ${feedbackAnim}`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 transition ${letterStyle}`}>
                        {letters[cIdx]}
                      </span>
                      <span className="leading-relaxed">{choiceText}</span>
                    </div>

                    {hasAnsweredCurrent && (
                      <div className="shrink-0">
                        {isCorrect ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                        ) : isSelected ? (
                          <XCircle className="w-5 h-5 text-rose-600" />
                        ) : null}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Instant Grounded Explanation Card */}
            {hasAnsweredCurrent && (
              <div className="p-4 sm:p-5 rounded-2xl bg-slate-50 border border-slate-200 animate-in fade-in slide-in-from-top-2 duration-200 space-y-1.5">
                <div className="flex items-center gap-2 font-bold text-xs text-slate-900">
                  <Sparkles className="w-4 h-4 text-amber-500" />
                  <span>Kabi's Explanation:</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {currentQ?.explanation}
                </p>
              </div>
            )}
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-end">
            <button
              onClick={handleNext}
              disabled={!hasAnsweredCurrent || isSubmitting}
              className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition disabled:opacity-40"
            >
              <span>
                {isSubmitting ? 'Scoring your quiz...' : currentIndex === questions.length - 1 ? 'View Score Report' : 'Next Question'}
              </span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* FLAG QUESTION MODAL */}
      {showFlagModal && currentQ && (
        <FlagModal
          isOpen={showFlagModal}
          onClose={() => setShowFlagModal(false)}
          targetType="question"
          targetId={currentQ.id}
          onSuccess={(msg) => showToast('success', msg)}
        />
      )}
    </div>
  );
}
