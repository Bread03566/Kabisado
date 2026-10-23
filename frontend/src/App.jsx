import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Toast from './components/Toast';
import Companion from './components/Companion';
import UploadLibraryView from './views/UploadLibraryView';
import DocumentView from './views/DocumentView';
import FlashcardStudyMode from './views/FlashcardStudyMode';
import QuizMode from './views/QuizMode';
import ProgressView from './views/ProgressView';
import ChatView from './views/ChatView';
import { CloudOff, X } from 'lucide-react';
import { getDocuments, checkHealth } from './services/api';
import { usePetEmoji } from './components/pets';

export default function App() {
  const petEmoji = usePetEmoji();

  // The browser tab icon shows the chosen study buddy
  useEffect(() => {
    const icon = document.querySelector('link[rel="icon"]');
    if (icon) {
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">${petEmoji}</text></svg>`;
      icon.href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
    }
  }, [petEmoji]);

  const [activeView, setActiveView] = useState('library'); // 'library' | 'dashboard' | 'document' | 'flashcards' | 'quiz' | 'chat'
  const [documents, setDocuments] = useState([]);
  const [currentDoc, setCurrentDoc] = useState(null);
  const [activeTopicId, setActiveTopicId] = useState(null);
  const [isDueCardsMode, setIsDueCardsMode] = useState(false);
  const [isWeakSpotQuizMode, setIsWeakSpotQuizMode] = useState(false);
  const [aiConfigured, setAiConfigured] = useState(null); // null until the health check answers
  const [offlineNoticeDismissed, setOfflineNoticeDismissed] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    fetchHealthAndDocs();
  }, []);

  const fetchHealthAndDocs = async () => {
    try {
      const health = await checkHealth();
      setAiConfigured(Boolean(health.ai_configured));
    } catch {
      // Backend unreachable: other errors already say so, so don't also claim the AI is off
      setAiConfigured(null);
    }

    try {
      const docs = await getDocuments();
      setDocuments(docs);
      // Keep the open document if it still exists; otherwise fall back to the newest one
      setCurrentDoc((prev) => docs.find((d) => d.id === prev?.id) || docs[0] || null);
    } catch (err) {
      console.error("Could not fetch documents:", err);
    }
  };

  const showToast = (type, message) => {
    setToast({ type, message });
  };

  const handleSelectDoc = (doc) => {
    setCurrentDoc(doc);
    setActiveTopicId(null);
    setIsDueCardsMode(false);
    setIsWeakSpotQuizMode(false);
    setActiveView('document');
  };

  const handleStartFlashcards = (docId = null, topicId = null, dueOnly = false) => {
    if (docId) {
      const doc = documents.find((d) => d.id === docId) || currentDoc;
      if (doc) setCurrentDoc(doc);
    }
    setActiveTopicId(topicId);
    setIsDueCardsMode(dueOnly);
    setActiveView('flashcards');
  };

  const handleStartQuiz = (docId = null, topicId = null, weakSpotOnly = false) => {
    if (docId) {
      const doc = documents.find((d) => d.id === docId) || currentDoc;
      if (doc) setCurrentDoc(doc);
    }
    setActiveTopicId(topicId);
    setIsWeakSpotQuizMode(weakSpotOnly);
    setActiveView('quiz');
  };

  const handleStartChat = (docId = null) => {
    if (docId) {
      const doc = documents.find((d) => d.id === docId) || currentDoc;
      if (doc) setCurrentDoc(doc);
    }
    setActiveView('chat');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900 selection:bg-amber-100 selection:text-amber-900">
      {/* Sticky Navigation Header */}
      <Navbar
        activeTab={activeView}
        onSelectTab={(tab) => {
          if (tab === 'library') {
            setActiveView('library');
          } else if (tab === 'dashboard') {
            setActiveView('dashboard');
          } else if (tab === 'document' && currentDoc) {
            setActiveView('document');
          }
        }}
        currentDoc={currentDoc}
      />

      {aiConfigured === false && !offlineNoticeDismissed && (
        <div className="animate-in fade-in slide-in-from-top-2 border-b border-amber-200 bg-amber-50 text-amber-950">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2 flex items-center gap-3 text-xs">
            <CloudOff className="w-4 h-4 shrink-0 text-amber-700" />
            <p className="flex-1">
              AI is offline right now, so summaries, flashcards, and quizzes use simpler versions built straight from your module.
            </p>
            <button
              onClick={() => setOfflineNoticeDismissed(true)}
              aria-label="Dismiss notice"
              className="p-1 rounded-md hover:bg-amber-100"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 pb-16">
        <div key={activeView} className="view-enter">
        {activeView === 'library' && (
          <UploadLibraryView
            documents={documents}
            onSelectDoc={handleSelectDoc}
            onRefreshDocs={fetchHealthAndDocs}
            showToast={showToast}
          />
        )}

        {activeView === 'dashboard' && (
          <ProgressView
            onStartDueCards={() => handleStartFlashcards(currentDoc?.id, null, true)}
            onStartWeakSpotQuiz={(docId) => handleStartQuiz(docId || currentDoc?.id, null, true)}
            onSelectTopicQuiz={(docId, topicId) => handleStartQuiz(docId, topicId, false)}
            showToast={showToast}
          />
        )}

        {activeView === 'document' && currentDoc && (
          <DocumentView
            documentId={currentDoc.id}
            onBack={() => setActiveView('library')}
            onStartFlashcards={(docId, topicId) => handleStartFlashcards(docId, topicId, false)}
            onStartQuiz={(docId, topicId) => handleStartQuiz(docId, topicId, false)}
            onStartChat={(docId) => handleStartChat(docId)}
            onStartWeakSpotQuiz={(docId) => handleStartQuiz(docId, null, true)}
            showToast={showToast}
          />
        )}

        {activeView === 'flashcards' && currentDoc && (
          <FlashcardStudyMode
            documentId={currentDoc.id}
            initialTopicId={activeTopicId}
            isDueMode={isDueCardsMode}
            onBack={() => setActiveView('document')}
            showToast={showToast}
          />
        )}

        {activeView === 'quiz' && currentDoc && (
          <QuizMode
            documentId={currentDoc.id}
            initialTopicId={activeTopicId}
            isWeakSpotMode={isWeakSpotQuizMode}
            aiConfigured={aiConfigured}
            onBack={() => setActiveView('document')}
            onGoToFlashcards={(docId) => handleStartFlashcards(docId, null, false)}
            showToast={showToast}
          />
        )}

        {activeView === 'chat' && currentDoc && (
          <ChatView
            documentId={currentDoc.id}
            documentTitle={currentDoc.title}
            onBack={() => setActiveView('document')}
            showToast={showToast}
          />
        )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span translate="no" className="notranslate font-extrabold text-slate-800">Kabisado {petEmoji}</span>
            <span>—</span>
            <span className="italic">Study today, pass tomorrow.</span>
          </div>
        </div>
      </footer>

      {/* Study-buddy pet that watches the cursor */}
      <Companion />

      {/* Toast Notifications */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
