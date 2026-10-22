import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Toast from './components/Toast';
import UploadLibraryView from './views/UploadLibraryView';
import DocumentView from './views/DocumentView';
import FlashcardStudyMode from './views/FlashcardStudyMode';
import QuizMode from './views/QuizMode';
import ProgressView from './views/ProgressView';
import ChatView from './views/ChatView';
import { getDocuments, checkHealth } from './services/api';

export default function App() {
  const [activeView, setActiveView] = useState('library'); // 'library' | 'dashboard' | 'document' | 'flashcards' | 'quiz' | 'chat'
  const [documents, setDocuments] = useState([]);
  const [currentDoc, setCurrentDoc] = useState(null);
  const [activeTopicId, setActiveTopicId] = useState(null);
  const [isDueCardsMode, setIsDueCardsMode] = useState(false);
  const [isWeakSpotQuizMode, setIsWeakSpotQuizMode] = useState(false);
  const [aiConfigured, setAiConfigured] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    fetchHealthAndDocs();
  }, []);

  const fetchHealthAndDocs = async () => {
    try {
      const health = await checkHealth();
      setAiConfigured(Boolean(health.ai_configured));
    } catch {
      setAiConfigured(false);
    }

    try {
      const docs = await getDocuments();
      setDocuments(docs);
      if (docs.length > 0 && !currentDoc) {
        setCurrentDoc(docs[0]);
      }
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
        aiConfigured={aiConfigured}
      />

      {/* Main Content Area */}
      <main className="flex-1 pb-16">
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
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-slate-800">Kabisado 🦉</span>
            <span>—</span>
            <span className="italic">Aral ngayon, pasa bukas.</span>
          </div>
          <div className="flex items-center gap-3 text-[11px] text-slate-400">
            <span>Phases 1-4 Complete</span>
            <span>•</span>
            <span>React + Vite + FastAPI + Claude</span>
          </div>
        </div>
      </footer>

      {/* Toast Notifications */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
