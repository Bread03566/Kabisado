import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  RotateCw, 
  Shuffle, 
  Plus, 
  Edit3, 
  Trash2, 
  Flag, 
  Sparkles, 
  ChevronLeft, 
  ChevronRight,
  BrainCircuit,
  Volume2
} from 'lucide-react';
import Mascot from '../components/Mascot';
import FlagModal from '../components/FlagModal';
import { 
  getFlashcards, 
  generateFlashcards, 
  createFlashcard, 
  updateFlashcard, 
  deleteFlashcard, 
  reviewFlashcard,
  getDueFlashcards
} from '../services/api';

export default function FlashcardStudyMode({ 
  documentId, 
  initialTopicId = null, 
  isDueMode = false,
  onBack, 
  showToast 
}) {
  const [cards, setCards] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const selectedTopicId = initialTopicId;
  const [isFinished, setIsFinished] = useState(false);
  
  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showFlagModal, setShowFlagModal] = useState(false);
  
  // Card form states
  const [formFront, setFormFront] = useState('');
  const [formBack, setFormBack] = useState('');
  const [formCardType, setFormCardType] = useState('term');

  // Load cards on mount
  useEffect(() => {
    loadCards();
  }, [documentId, selectedTopicId, isDueMode]);

  const speakText = (text, e) => {
    e?.stopPropagation();
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const loadCards = async () => {
    setIsLoading(true);
    try {
      let data = [];
      if (isDueMode) {
        data = await getDueFlashcards(documentId);
      } else {
        data = await getFlashcards(documentId, selectedTopicId);
      }
      setCards(data);
      setCurrentIndex(0);
      setIsFlipped(false);
      setIsFinished(false);
    } catch {
      showToast('error', 'Could not load flashcards.');
    } finally {
      setIsLoading(false);
    }
  };


  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (showAddModal || showEditModal || showFlagModal) return;
      if (e.code === 'Space') {
        e.preventDefault();
        setIsFlipped((prev) => !prev);
      } else if (e.code === 'ArrowRight' && currentIndex < cards.length - 1) {
        handleNextCard();
      } else if (e.code === 'ArrowLeft' && currentIndex > 0) {
        handlePrevCard();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentIndex, cards.length, showAddModal, showEditModal, showFlagModal]);

  const handleGenerateCards = async (count = 8) => {
    setIsGenerating(true);
    try {
      showToast('info', 'Making flashcards so you won\'t fail...');
      const newCards = await generateFlashcards(documentId, count, selectedTopicId);
      setCards((prev) => [...newCards, ...prev]);
      showToast('success', `Created ${newCards.length} new flashcards!`);
      setCurrentIndex(0);
      setIsFlipped(false);
      setIsFinished(false);
    } catch (err) {
      showToast('error', err.message || 'Failed to create flashcards.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleNextCard = () => {
    if (currentIndex < cards.length - 1) {
      setIsFlipped(false);
      setTimeout(() => setCurrentIndex((prev) => prev + 1), 150);
    } else {
      setIsFinished(true);
    }
  };

  const handlePrevCard = () => {
    if (currentIndex > 0) {
      setIsFlipped(false);
      setTimeout(() => setCurrentIndex((prev) => prev - 1), 150);
    }
  };

  const handleShuffle = () => {
    const shuffled = [...cards].sort(() => Math.random() - 0.5);
    setCards(shuffled);
    setCurrentIndex(0);
    setIsFlipped(false);
    setIsFinished(false);
    showToast('info', 'Deck shuffled!');
  };

  const handleRate = async (rating) => {
    const currentCard = cards[currentIndex];
    if (!currentCard) return;

    try {
      await reviewFlashcard(currentCard.id, rating);
      handleNextCard();
    } catch {
      handleNextCard();
    }
  };

  const handleAddCard = async (e) => {
    e.preventDefault();
    if (!formFront.trim() || !formBack.trim()) return;

    try {
      const newCard = await createFlashcard({
        document_id: documentId,
        topic_id: selectedTopicId,
        front: formFront.trim(),
        back: formBack.trim(),
        card_type: formCardType
      });
      setCards([newCard, ...cards]);
      setShowAddModal(false);
      setFormFront('');
      setFormBack('');
      showToast('success', 'New flashcard added!');
    } catch {
      showToast('error', 'Could not add the card.');
    }
  };

  const handleEditCard = async (e) => {
    e.preventDefault();
    const currentCard = cards[currentIndex];
    if (!currentCard || !formFront.trim() || !formBack.trim()) return;

    try {
      const updated = await updateFlashcard(currentCard.id, {
        front: formFront.trim(),
        back: formBack.trim(),
        card_type: formCardType
      });
      const newCards = [...cards];
      newCards[currentIndex] = updated;
      setCards(newCards);
      setShowEditModal(false);
      showToast('success', 'Flashcard updated!');
    } catch {
      showToast('error', 'Could not update the card.');
    }
  };

  const handleDeleteCard = async () => {
    const currentCard = cards[currentIndex];
    if (!currentCard) return;
    if (!window.confirm('Are you sure you want to delete this card?')) return;

    try {
      await deleteFlashcard(currentCard.id);
      const remaining = cards.filter((_, i) => i !== currentIndex);
      setCards(remaining);
      if (currentIndex >= remaining.length && remaining.length > 0) {
        setCurrentIndex(remaining.length - 1);
      }
      setIsFlipped(false);
      showToast('success', 'Flashcard deleted.');
    } catch {
      showToast('error', 'Failed to delete the card.');
    }
  };

  const openEditModal = () => {
    const currentCard = cards[currentIndex];
    if (!currentCard) return;
    setFormFront(currentCard.front);
    setFormBack(currentCard.back);
    setFormCardType(currentCard.card_type || 'term');
    setShowEditModal(true);
  };

  const currentCard = cards[currentIndex];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
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
              <BrainCircuit className="w-5 h-5 text-indigo-600" />
              <span>Flashcard Study Mode</span>
            </h1>
            <p className="text-xs text-slate-500">
              Click the card or press Spacebar to flip it.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => handleGenerateCards(8)}
            disabled={isGenerating}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-800 text-xs font-bold rounded-xl border border-indigo-200 transition disabled:opacity-50"
          >
            <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? 'Generating...' : 'Generate More'}</span>
          </button>

          <button
            onClick={() => {
              setFormFront('');
              setFormBack('');
              setFormCardType('term');
              setShowAddModal(true);
            }}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Add Card</span>
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-3xl border border-slate-200 p-16 text-center flex flex-col items-center justify-center space-y-4 shadow-sm">
          <Mascot mood="studying" size="lg" />
          <p className="text-sm font-bold text-slate-700 animate-pulse">
            Preparing flashcards...
          </p>
        </div>
      ) : cards.length === 0 ? (
        /* Empty State */
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center flex flex-col items-center justify-center space-y-4 shadow-sm">
          <Mascot mood="sleepy" size="lg" />
          <div className="max-w-md space-y-1">
            <h3 className="font-extrabold text-slate-900 text-lg">
              This lesson doesn't have any flashcards yet.
            </h3>
            <p className="text-xs text-slate-500">
              Let Kabi make memory-boosting cards for you, based on the module's actual content!
            </p>
          </div>
          <button
            onClick={() => handleGenerateCards(8)}
            disabled={isGenerating}
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            <span>Generate Flashcards with AI</span>
          </button>
        </div>
      ) : isFinished ? (
        /* Completion Screen */
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center flex flex-col items-center justify-center space-y-4 shadow-sm animate-in zoom-in-95">
          <Mascot mood="happy" size="xl" />
          <div className="space-y-1">
            <h2 className="text-2xl font-black text-slate-900">
              Nice! You finished the whole deck! 🦉🎉
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 max-w-md mx-auto">
              You reviewed all {cards.length} flashcards. Your spaced repetition intervals have been updated for your next review.
            </p>
          </div>
          <div className="flex items-center gap-3 pt-3">
            <button
              onClick={() => {
                setCurrentIndex(0);
                setIsFlipped(false);
                setIsFinished(false);
              }}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow transition"
            >
              Restart Deck
            </button>
            <button
              onClick={onBack}
              className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs sm:text-sm rounded-xl transition"
            >
              Back to Module
            </button>
          </div>
        </div>
      ) : (
        /* Active Flashcard Study View */
        <div className="space-y-6">
          {/* Deck Controls & Progress */}
          <div className="flex items-center justify-between text-xs text-slate-600 px-1">
            <div className="flex items-center gap-2 font-bold">
              <span className="bg-indigo-100 text-indigo-900 px-2.5 py-1 rounded-lg">
                Card {currentIndex + 1} of {cards.length}
              </span>
              {currentCard?.topic_title && (
                <span className="hidden sm:inline-block text-slate-400 font-medium truncate max-w-xs">
                  • {currentCard.topic_title}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleShuffle}
                title="Shuffle cards"
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition"
              >
                <Shuffle className="w-4 h-4" />
              </button>
              <button
                onClick={openEditModal}
                title="Edit this card"
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition"
              >
                <Edit3 className="w-4 h-4" />
              </button>
              <button
                onClick={handleDeleteCard}
                title="Delete this card"
                className="p-1.5 rounded-lg hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition"
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <button
                onClick={() => setShowFlagModal(true)}
                title="Flag this card"
                className="p-1.5 rounded-lg hover:bg-amber-50 text-slate-400 hover:text-amber-600 transition"
              >
                <Flag className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 3D Flip Card Container */}
          <div
            key={currentCard?.id}
            onClick={() => setIsFlipped(!isFlipped)}
            className="animate-in fade-in slide-in-from-right-4 perspective-1000 w-full min-h-[320px] sm:min-h-[360px] cursor-pointer select-none group"
          >
            <div
              className={`relative w-full h-full min-h-[320px] sm:min-h-[360px] transition-transform duration-500 transform-style-3d ${
                isFlipped ? 'rotate-y-180' : ''
              }`}
            >
              {/* FRONT OF CARD */}
              <div className="absolute inset-0 backface-hidden bg-white rounded-3xl border-2 border-slate-200 group-hover:border-indigo-300 p-8 sm:p-12 flex flex-col justify-between shadow-lg shadow-slate-200/50">
                <div className="flex items-center justify-between text-xs">
                  <span className="px-2.5 py-1 rounded-full font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-100">
                    {currentCard?.card_type === 'qa' ? 'Question' : 'Term'}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => speakText(currentCard?.front, e)}
                      title="Read aloud (Voice Mode)"
                      className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-indigo-600 transition"
                    >
                      <Volume2 className="w-4 h-4" />
                    </button>
                    <span className="text-slate-400 font-medium">Click to see the answer</span>
                  </div>
                </div>

                <div className="my-auto py-6 text-center">
                  <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900 leading-snug">
                    {currentCard?.front}
                  </h3>
                </div>

                <div className="flex items-center justify-center text-xs text-indigo-600 font-semibold gap-1 opacity-60 group-hover:opacity-100 transition">
                  <RotateCw className="w-3.5 h-3.5" />
                  <span>Flip card</span>
                </div>
              </div>

              {/* BACK OF CARD */}
              <div className="absolute inset-0 backface-hidden rotate-y-180 bg-gradient-to-br from-indigo-900 via-slate-900 to-indigo-950 text-white rounded-3xl p-8 sm:p-12 flex flex-col justify-between shadow-xl">
                <div className="flex items-center justify-between text-xs">
                  <span className="px-2.5 py-1 rounded-full font-bold uppercase tracking-wider bg-white/10 text-indigo-200 border border-white/10">
                    Answer / Definition
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={(e) => speakText(currentCard?.back, e)}
                      title="Read aloud"
                      className="p-1 rounded-lg hover:bg-white/10 text-indigo-200 hover:text-white transition"
                    >
                      <Volume2 className="w-4 h-4" />
                    </button>
                    <span className="text-indigo-300/70 font-medium">Click to flip back</span>
                  </div>
                </div>

                <div className="my-auto py-6 text-center">
                  <p className="text-base sm:text-xl font-medium leading-relaxed text-indigo-50">
                    {currentCard?.back}
                  </p>
                </div>

                <div className="text-center text-[11px] text-indigo-300/50">
                  Kabisado Spaced Repetition (SM-2)
                </div>
              </div>

            </div>
          </div>

          {/* Spaced Repetition Rating Buttons */}
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-slate-500 px-1">
              <span>How well do you know this?</span>
              <span className="text-[11px] font-normal text-slate-400 hidden sm:inline">
                The review interval adjusts automatically
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <button
                onClick={() => handleRate('again')}
                className="flex flex-col items-center justify-center py-3 px-2 rounded-xl bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-800 transition active:scale-95 group"
              >
                <span className="font-extrabold text-xs sm:text-sm">Again</span>
                <span className="text-[10px] text-rose-600 mt-0.5">Don't know it yet (1d)</span>
              </button>

              <button
                onClick={() => handleRate('hard')}
                className="flex flex-col items-center justify-center py-3 px-2 rounded-xl bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-800 transition active:scale-95 group"
              >
                <span className="font-extrabold text-xs sm:text-sm">Hard</span>
                <span className="text-[10px] text-amber-600 mt-0.5">Struggled a bit</span>
              </button>

              <button
                onClick={() => handleRate('good')}
                className="flex flex-col items-center justify-center py-3 px-2 rounded-xl bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-800 transition active:scale-95 group"
              >
                <span className="font-extrabold text-xs sm:text-sm">Good</span>
                <span className="text-[10px] text-blue-600 mt-0.5">Got it right</span>
              </button>

              <button
                onClick={() => handleRate('easy')}
                className="flex flex-col items-center justify-center py-3 px-2 rounded-xl bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-800 transition active:scale-95 group"
              >
                <span className="font-extrabold text-xs sm:text-sm">Easy</span>
                <span className="text-[10px] text-emerald-600 mt-0.5">Mastered it!</span>
              </button>
            </div>
          </div>

          {/* Navigation Controls */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={handlePrevCard}
              disabled={currentIndex === 0}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Previous</span>
            </button>

            <span className="text-xs font-medium text-slate-400">
              Shortcut: Spacebar (Flip) • Arrow Keys (Next/Prev)
            </span>

            <button
              onClick={handleNextCard}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 transition"
            >
              <span>{currentIndex === cards.length - 1 ? 'Finish' : 'Next'}</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ADD CARD MODAL */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-slate-900 text-base">Add Flashcard</h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={handleAddCard} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Card Type:</label>
                <div className="flex gap-2">
                  {['term', 'qa'].map((type) => (
                    <button
                      type="button"
                      key={type}
                      onClick={() => setFormCardType(type)}
                      className={`flex-1 py-1.5 text-xs font-bold rounded-lg border capitalize ${
                        formCardType === type
                          ? 'bg-indigo-50 border-indigo-400 text-indigo-800'
                          : 'border-slate-200 text-slate-600'
                      }`}
                    >
                      {type === 'term' ? 'Term / Definition' : 'Question / Answer'}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Card Front (Question or Term):
                </label>
                <textarea
                  value={formFront}
                  onChange={(e) => setFormFront(e.target.value)}
                  placeholder="Example: What was the purpose of La Solidaridad?"
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 h-20 resize-none outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Card Back (Answer or Definition):
                </label>
                <textarea
                  value={formBack}
                  onChange={(e) => setFormBack(e.target.value)}
                  placeholder="Example: To be the voice of the reformists and expose the abuses in the Philippines."
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 h-24 resize-none outline-none"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl"
                >
                  Save Card
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT CARD MODAL */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-slate-900 text-base">Edit Flashcard</h3>
              <button onClick={() => setShowEditModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={handleEditCard} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Card Front:
                </label>
                <textarea
                  value={formFront}
                  onChange={(e) => setFormFront(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 h-20 resize-none outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Card Back:
                </label>
                <textarea
                  value={formBack}
                  onChange={(e) => setFormBack(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 h-24 resize-none outline-none"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl"
                >
                  Update Card
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* FLAG CARD MODAL */}
      {showFlagModal && currentCard && (
        <FlagModal
          isOpen={showFlagModal}
          onClose={() => setShowFlagModal(false)}
          targetType="flashcard"
          targetId={currentCard.id}
          onSuccess={(msg) => showToast('success', msg)}
        />
      )}
    </div>
  );
}
