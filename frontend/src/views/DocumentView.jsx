import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  FileText, 
  Sparkles, 
  BrainCircuit, 
  HelpCircle, 
  Layers, 
  CheckCircle2, 
  RefreshCw, 
  BookMarked,
  Clock,
  ListFilter,
  MessageSquare,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import Mascot from '../components/Mascot';
import { summarizeDocument, getDocument } from '../services/api';

import StudyPlanModal from '../components/StudyPlanModal';

export default function DocumentView({
  documentId,
  onBack,
  onStartFlashcards,
  onStartQuiz,
  onStartChat,
  onStartWeakSpotQuiz,
  showToast
}) {
  const [doc, setDoc] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('summary'); // 'summary' | 'topics' | 'chat'
  const [showStudyPlanModal, setShowStudyPlanModal] = useState(false);
  
  // Summarizer states
  const [summaryLength, setSummaryLength] = useState('standard');
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [currentSummary, setCurrentSummary] = useState('');
  const [keyTerms, setKeyTerms] = useState([]);
  const [expandedTopic, setExpandedTopic] = useState(null);

  useEffect(() => {
    loadDocumentDetails();
  }, [documentId]);

  const loadDocumentDetails = async () => {
    setIsLoading(true);
    try {
      const data = await getDocument(documentId);
      setDoc(data);
      if (data.summary_standard) {
        setCurrentSummary(data.summary_standard);
      } else if (data.summary_brief) {
        setCurrentSummary(data.summary_brief);
      } else if (data.summary_detailed) {
        setCurrentSummary(data.summary_detailed);
      }
      if (data.key_terms) {
        setKeyTerms(data.key_terms);
      }
    } catch (err) {
      showToast('error', err.message || 'Could not load the document.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateSummary = async (length = summaryLength) => {
    setIsSummarizing(true);
    try {
      showToast('info', 'Kabi is summarizing the lesson... Just a moment!');
      const res = await summarizeDocument(documentId, length);
      setCurrentSummary(res.summary);
      setKeyTerms(res.key_terms || []);
      setSummaryLength(length);
      showToast('success', 'Summary and key terms are ready!');
    } catch (err) {
      showToast('error', err.message || 'Summarizing failed.');
    } finally {
      setIsSummarizing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-20 text-center flex flex-col items-center justify-center space-y-4">
        <Mascot mood="studying" size="lg" />
        <p className="text-sm font-semibold text-slate-700 animate-pulse">
          Kabi is flipping through your module...
        </p>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4">
        <p className="text-slate-600">Document not found.</p>
        <button
          onClick={onBack}
          className="px-4 py-2 bg-amber-500 text-white rounded-xl text-xs font-semibold"
        >
          Back to Library
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Top Navigation & Action Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition"
            title="Back to Library"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                doc.file_type === 'pdf' ? 'bg-red-100 text-red-800' :
                doc.file_type === 'docx' ? 'bg-blue-100 text-blue-800' : 'bg-emerald-100 text-emerald-800'
              }`}>
                {doc.file_type}
              </span>
              <span className="text-xs text-slate-400">
                {doc.topics?.length || 0} Topics • {doc.raw_text?.split(/\s+/).filter(Boolean).length || 0} Words
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-black text-slate-900 mt-0.5">
              {doc.title}
            </h1>
          </div>
        </div>

        {/* Study Mode Triggers */}
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <button
            onClick={() => onStartFlashcards(doc.id)}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-xs transition active:scale-95"
          >
            <BrainCircuit className="w-4 h-4" />
            <span>Flashcards</span>
          </button>

          <button
            onClick={() => onStartQuiz(doc.id)}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-xs transition active:scale-95"
          >
            <HelpCircle className="w-4 h-4" />
            <span>Quiz</span>
          </button>

          <button
            onClick={() => onStartChat(doc.id)}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs rounded-xl shadow-xs transition active:scale-95"
          >
            <Sparkles className="w-4 h-4" />
            <span>Ask Kabi</span>
          </button>

          <button
            onClick={() => setShowStudyPlanModal(true)}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-xl transition"
          >
            <span>Plan 📅</span>
          </button>
        </div>
      </div>


      {/* Tabs Switcher */}
      <div className="flex border-b border-slate-200 gap-2">
        <button
          onClick={() => setActiveTab('summary')}
          className={`pb-3 px-4 text-xs sm:text-sm font-bold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'summary'
              ? 'border-amber-500 text-amber-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <BookMarked className="w-4 h-4" />
          <span>Summary & Key Terms</span>
        </button>
        <button
          onClick={() => setActiveTab('topics')}
          className={`pb-3 px-4 text-xs sm:text-sm font-bold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'topics'
              ? 'border-amber-500 text-amber-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Sections / Topics ({doc.topics?.length || 0})</span>
        </button>
        <button
          onClick={() => setActiveTab('chat')}
          className={`pb-3 px-4 text-xs sm:text-sm font-bold border-b-2 transition flex items-center gap-2 ${
            activeTab === 'chat'
              ? 'border-amber-500 text-amber-700'
              : 'border-transparent text-slate-400 hover:text-slate-600'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          <span>Ask Kabisado (Chat)</span>
          <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-medium">Phase 3</span>
        </button>
      </div>

      {/* TAB 1: SUMMARY & KEY TERMS */}
      {activeTab === 'summary' && (
        <div className="space-y-6">
          {/* Summary Control Bar */}
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-700">Summary Length:</span>
              <div className="inline-flex bg-slate-100 p-1 rounded-xl">
                {[
                  { id: 'brief', label: 'Brief' },
                  { id: 'standard', label: 'Standard' },
                  { id: 'detailed', label: 'Detailed' },
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      setSummaryLength(item.id);
                      handleGenerateSummary(item.id);
                    }}
                    className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
                      summaryLength === item.id
                        ? 'bg-white text-amber-800 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={() => handleGenerateSummary()}
              disabled={isSummarizing}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-xl transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSummarizing ? 'animate-spin' : ''}`} />
              <span>{isSummarizing ? 'Generating Summary...' : 'Regenerate Summary'}</span>
            </button>
          </div>

          {/* Loading or Summary Output */}
          {isSummarizing ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center flex flex-col items-center justify-center space-y-3">
              <Mascot mood="studying" size="lg" />
              <p className="text-sm font-bold text-slate-800">
                Kabi is summarizing the lesson...
              </p>
              <p className="text-xs text-slate-500 max-w-sm">
                Finding the most important concepts so you can master them fast!
              </p>
            </div>
          ) : !currentSummary ? (
            /* No summary yet state */
            <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center space-y-4">
              <Mascot mood="sleepy" size="md" />
              <div>
                <h3 className="font-bold text-slate-800 text-base">
                  This module doesn't have a summary yet.
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Click the button below to have Kabi summarize the key parts.
                </p>
              </div>
              <button
                onClick={() => handleGenerateSummary('standard')}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs rounded-xl shadow-md transition"
              >
                <Sparkles className="w-4 h-4" />
                <span>Generate Summary & Key Terms</span>
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Formatted Summary Box */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs">
                <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
                  <div className="flex items-center gap-2 text-slate-900 font-bold text-base sm:text-lg">
                    <FileText className="w-5 h-5 text-amber-500" />
                    <span>Lesson Summary</span>
                  </div>
                  <span className="text-xs font-semibold px-2.5 py-1 bg-amber-50 text-amber-800 rounded-lg border border-amber-200 capitalize">
                    {summaryLength}
                  </span>
                </div>

                <div className="prose prose-slate max-w-none text-xs sm:text-sm leading-relaxed whitespace-pre-wrap text-slate-700">
                  {currentSummary}
                </div>
              </div>

              {/* Key Terms Section */}
              {keyTerms.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-4">
                  <div className="flex items-center gap-2 text-slate-900 font-bold text-base sm:text-lg">
                    <Sparkles className="w-5 h-5 text-indigo-500" />
                    <span>Key Terms</span>
                  </div>
                  <p className="text-xs text-slate-500">
                    Memorize these definitions; they come up on exams all the time:
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                    {keyTerms.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-indigo-300 transition hover:bg-indigo-50/20"
                      >
                        <h4 className="font-bold text-slate-900 text-xs sm:text-sm text-indigo-950 flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
                          <span>{item.term}</span>
                        </h4>
                        <p className="text-xs text-slate-600 mt-1.5 leading-relaxed pl-3.5">
                          {item.definition}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: TOPICS / SECTIONS */}
      {activeTab === 'topics' && (
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Kabi automatically split your module into {doc.topics?.length || 0} sections so you can study one topic at a time:
          </p>

          <div className="space-y-3">
            {doc.topics?.map((topic, index) => {
              const isExpanded = expandedTopic === topic.id;
              const wordCount = topic.content.split(/\s+/).filter(Boolean).length;

              return (
                <div
                  key={topic.id}
                  className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs"
                >
                  <div
                    onClick={() => setExpandedTopic(isExpanded ? null : topic.id)}
                    className="p-4 sm:p-5 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-7 h-7 rounded-xl bg-amber-100 text-amber-900 font-bold text-xs flex items-center justify-center shrink-0">
                        {index + 1}
                      </span>
                      <div>
                        <h3 className="font-bold text-slate-900 text-xs sm:text-sm">
                          {topic.title}
                        </h3>
                        <p className="text-[11px] text-slate-400">
                          {wordCount} words
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onStartFlashcards(doc.id, topic.id);
                        }}
                        className="hidden sm:inline-flex items-center gap-1 px-3 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg transition"
                      >
                        <BrainCircuit className="w-3.5 h-3.5" />
                        <span>Flashcards</span>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onStartQuiz(doc.id, topic.id);
                        }}
                        className="hidden sm:inline-flex items-center gap-1 px-3 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-semibold rounded-lg transition"
                      >
                        <HelpCircle className="w-3.5 h-3.5" />
                        <span>Quiz</span>
                      </button>

                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="p-5 pt-0 border-t border-slate-100 text-xs text-slate-700 space-y-4">
                      <div className="bg-slate-50 p-4 rounded-xl font-mono text-[11px] leading-relaxed max-h-80 overflow-y-auto whitespace-pre-wrap">
                        {topic.content}
                      </div>

                      <div className="flex items-center justify-end gap-2 sm:hidden">
                        <button
                          onClick={() => onStartFlashcards(doc.id, topic.id)}
                          className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-semibold rounded-lg"
                        >
                          Study Flashcards
                        </button>
                        <button
                          onClick={() => onStartQuiz(doc.id, topic.id)}
                          className="px-3 py-1.5 bg-emerald-600 text-white text-xs font-semibold rounded-lg"
                        >
                          Take Quiz
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: CHAT (ASK KABISADO) */}
      {activeTab === 'chat' && (
        <div className="bg-white rounded-3xl border border-slate-200 p-10 text-center space-y-4 shadow-xs">
          <Mascot mood="studying" size="lg" />
          <div className="max-w-md mx-auto space-y-1">
            <h3 className="font-extrabold text-slate-900 text-lg">
              Ask Kabisado (Explainer Chat) 🦉💬
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Confused by a concept? Ask Kabi! Every answer is grounded in your module and cites the chapter it came from.
            </p>
          </div>
          <button
            onClick={() => onStartChat(doc.id)}
            className="inline-flex items-center gap-2 px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition"
          >
            <Sparkles className="w-4 h-4" />
            <span>Start Chatting with Kabi</span>
          </button>
        </div>
      )}

      {/* Study Plan Modal */}
      {showStudyPlanModal && (
        <StudyPlanModal
          isOpen={showStudyPlanModal}
          onClose={() => setShowStudyPlanModal(false)}
          documentTitle={doc.title}
          topicsCount={doc.topics?.length || 1}
        />
      )}
    </div>
  );
}

