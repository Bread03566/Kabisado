import React, { useState, useEffect, useRef } from 'react';
import { 
  ArrowLeft, 
  Send, 
  Sparkles, 
  Volume2, 
  Mic, 
  MicOff, 
  BookMarked,
  ToggleLeft,
  ToggleRight
} from 'lucide-react';
import Mascot from '../components/Mascot';
import Markdown from '../components/Markdown';
import { askDocumentChat } from '../services/api';

export default function ChatView({ 
  documentId, 
  documentTitle, 
  onBack, 
  showToast 
}) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hi! I'm Kabi 🦉. Ask me anything about **"${documentTitle}"**. ` +
               `I'll explain the confusing parts, grounded in the material and citing the exact section. ` +
               `If the answer isn't in the module, I'll tell you right away so we don't have to guess!`,
      citation: null,
      found_in_document: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [explainLikeNew, setExplainLikeNew] = useState(false);
  const [isSending, setIsSending] = useState(false);
  
  // Voice Mode States (Phase 4)
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  const handleSendMessage = async (customPrompt = null) => {
    const textToSend = (customPrompt || inputText).trim();
    if (!textToSend || isSending) return;

    const userMessage = {
      role: 'user',
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText('');
    setIsSending(true);

    try {
      const historyPayload = messages.slice(-4).map((m) => ({
        role: m.role,
        content: m.content
      }));

      const res = await askDocumentChat(
        documentId, 
        textToSend, 
        explainLikeNew, 
        historyPayload
      );

      const assistantMessage = {
        role: 'assistant',
        content: res.answer,
        citation: res.citation,
        found_in_document: res.found_in_document,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      showToast('error', err.message || 'Could not get an answer from Kabi.');
    } finally {
      setIsSending(false);
    }
  };

  // Speech-to-Text via Web Speech API (Phase 4)
  const handleToggleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      showToast('error', 'Speech recognition isn\'t supported in this browser yet.');
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => {
        setIsListening(true);
        showToast('info', 'Kabi is listening... Go ahead and speak!');
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputText(transcript);
        setIsListening(false);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  // Text-to-Speech via Web Speech API (Phase 4)
  const speakText = (text) => {
    if (!window.speechSynthesis) {
      showToast('error', 'Voice isn\'t supported in this browser.');
      return;
    }

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    // Clean markdown before speaking
    const cleanText = text.replace(/[#*`>_]/g, '').trim();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  const samplePrompts = [
    "What's the most important lesson in this module?",
    "Why are these events important?",
    "How can I explain this in my own words?",
    "What might come up on the exam about this?"
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 flex flex-col h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-lg sm:text-xl font-black text-slate-900 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-500" />
              <span>Ask Kabisado (Explainer Chat)</span>
            </h1>
            <p className="text-xs text-slate-500 truncate max-w-xs sm:max-w-md">
              Lesson: {documentTitle}
            </p>
          </div>
        </div>

        {/* Explain like I'm new toggle */}
        <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-bold text-slate-700 hidden sm:inline">
            Explain like I'm new
          </span>
          <button
            onClick={() => setExplainLikeNew(!explainLikeNew)}
            className={`flex items-center gap-1 text-xs font-bold transition ${
              explainLikeNew ? 'text-amber-600' : 'text-slate-400'
            }`}
          >
            {explainLikeNew ? (
              <ToggleRight className="w-6 h-6 text-amber-500" />
            ) : (
              <ToggleLeft className="w-6 h-6 text-slate-400" />
            )}
            <span className="sm:hidden text-[10px]">ELI5</span>
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto py-6 space-y-4 pr-1">
        {messages.map((m, idx) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={idx}
              className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {!isUser && (
                <Mascot mood={m.found_in_document ? "studying" : "shocked"} size="sm" className="shrink-0 mt-1" />
              )}

              <div
                className={`max-w-[85%] sm:max-w-xl p-4 rounded-3xl text-xs sm:text-sm leading-relaxed shadow-xs space-y-2 ${
                  isUser
                    ? 'bg-amber-500 text-white rounded-tr-xs'
                    : 'bg-white border border-slate-200 text-slate-800 rounded-tl-xs'
                }`}
              >
                {isUser ? (
                  <div className="whitespace-pre-wrap">{m.content}</div>
                ) : (
                  <Markdown>{m.content}</Markdown>
                )}

                {/* Citation badge if provided */}
                {!isUser && m.citation && (
                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                    <span className="inline-flex items-center gap-1 font-semibold text-amber-800 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                      <BookMarked className="w-3 h-3" />
                      <span>{m.citation}</span>
                    </span>

                    <button
                      onClick={() => speakText(m.content)}
                      title="Read aloud (Voice Mode)"
                      className="text-slate-400 hover:text-amber-600 p-1 rounded-md transition"
                    >
                      <Volume2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                <div className={`text-[10px] text-right font-medium ${isUser ? 'text-amber-100' : 'text-slate-400'}`}>
                  {m.timestamp}
                </div>
              </div>
            </div>
          );
        })}

        {isSending && (
          <div className="flex gap-3 items-center">
            <Mascot mood="studying" size="sm" />
            <div className="bg-white border border-slate-200 px-4 py-3 rounded-2xl text-xs text-slate-500 flex items-center gap-2 shadow-xs">
              <Sparkles className="w-4 h-4 text-amber-500 animate-spin" />
              <span>Kabi is searching the module for the answer...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Sample Prompt Suggestions */}
      {messages.length <= 2 && (
        <div className="py-2 flex items-center gap-2 overflow-x-auto text-[11px]">
          <span className="font-bold text-slate-400 shrink-0">Try:</span>
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(p)}
              className="px-2.5 py-1 bg-white border border-slate-200 hover:border-amber-400 text-slate-700 rounded-xl whitespace-nowrap transition"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input Form */}
      <div className="pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2 bg-white p-2 rounded-2xl border border-slate-200 shadow-md focus-within:ring-2 focus-within:ring-amber-500/20 focus-within:border-amber-500"
        >
          {/* Speech-to-Text Button (Voice Mode) */}
          <button
            type="button"
            onClick={handleToggleVoiceInput}
            title={isListening ? "Stop Listening" : "Speak with your voice (Voice Input)"}
            className={`p-2.5 rounded-xl transition ${
              isListening
                ? 'bg-rose-500 text-white animate-pulse'
                : 'text-slate-400 hover:text-slate-700 hover:bg-slate-100'
            }`}
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          <input
            type="text"
            placeholder={isListening ? "You're speaking... Kabi is listening..." : "Ask about this module..."}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isSending}
            className="flex-1 text-xs sm:text-sm bg-transparent outline-none px-2 text-slate-800 placeholder-slate-400"
          />

          <button
            type="submit"
            disabled={!inputText.trim() || isSending}
            className="p-2.5 bg-amber-500 hover:bg-amber-600 disabled:opacity-40 text-white rounded-xl shadow-xs transition"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
