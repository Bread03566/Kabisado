// Kabisado API Client

const API_BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/+$/, "");

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("API unreachable");
  return res.json();
}

// ==================== Documents ====================
export async function getDocuments() {
  const res = await fetch(`${API_BASE}/api/documents`);
  if (!res.ok) throw new Error("Failed to fetch documents");
  return res.json();
}

export async function getDocument(id) {
  const res = await fetch(`${API_BASE}/api/documents/${id}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Document not found");
  }
  return res.json();
}

export async function uploadDocumentFile(file, customTitle = "") {
  const formData = new FormData();
  formData.append("file", file);
  if (customTitle) {
    formData.append("custom_title", customTitle);
  }

  const res = await fetch(`${API_BASE}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function createDocumentFromText(title, text) {
  const res = await fetch(`${API_BASE}/api/documents/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create document");
  }
  return res.json();
}

export async function deleteDocument(id) {
  const res = await fetch(`${API_BASE}/api/documents/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete document");
  return res.json();
}

// ==================== Summaries ====================
export async function summarizeDocument(id, length = "standard", topicId = null, force = false) {
  const res = await fetch(`${API_BASE}/api/documents/${id}/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ length, topic_id: topicId, force }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Summarization failed");
  }
  return res.json();
}

// ==================== Flashcards ====================
export async function getFlashcards(documentId, topicId = null) {
  let url = `${API_BASE}/api/documents/${documentId}/flashcards`;
  if (topicId) url += `?topic_id=${topicId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load flashcards");
  return res.json();
}

export async function generateFlashcards(documentId, count = 8, topicId = null, cardType = "mixed") {
  const res = await fetch(`${API_BASE}/api/documents/${documentId}/flashcards/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count, topic_id: topicId, card_type: cardType }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Flashcard generation failed");
  }
  return res.json();
}

export async function createFlashcard(cardData) {
  const res = await fetch(`${API_BASE}/api/flashcards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cardData),
  });
  if (!res.ok) throw new Error("Failed to create flashcard");
  return res.json();
}

export async function updateFlashcard(cardId, updateData) {
  const res = await fetch(`${API_BASE}/api/flashcards/${cardId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updateData),
  });
  if (!res.ok) throw new Error("Failed to update flashcard");
  return res.json();
}

export async function deleteFlashcard(cardId) {
  const res = await fetch(`${API_BASE}/api/flashcards/${cardId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete flashcard");
  return res.json();
}

export async function reviewFlashcard(cardId, rating) {
  const res = await fetch(`${API_BASE}/api/flashcards/${cardId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  if (!res.ok) throw new Error("Failed to submit review");
  return res.json();
}

// ==================== Quizzes ====================
export async function getQuestions(documentId, topicId = null, difficulty = null) {
  let url = `${API_BASE}/api/documents/${documentId}/questions?`;
  if (topicId) url += `topic_id=${topicId}&`;
  if (difficulty && difficulty !== "mixed") url += `difficulty=${difficulty}&`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load questions");
  return res.json();
}

export async function generateQuiz(documentId, count = 5, topicId = null, difficulty = "medium", questionType = "multiple_choice", style = "mixed") {
  const res = await fetch(`${API_BASE}/api/documents/${documentId}/quiz/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count, topic_id: topicId, difficulty, question_type: questionType, style }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Quiz generation failed");
  }
  return res.json();
}

// Instant feedback for typed and matching answers, using the same grader as the final score
export async function checkAnswer(questionId, answer) {
  const res = await fetch(`${API_BASE}/api/quizzes/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, ...answer }),
  });
  if (!res.ok) throw new Error("Could not check the answer");
  return res.json();
}

export async function submitQuizAttempt(documentId, answers, difficulty = "mixed", topicId = null) {
  const res = await fetch(`${API_BASE}/api/quizzes/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_id: documentId,
      topic_id: topicId,
      difficulty,
      answers,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Quiz submission failed");
  }
  return res.json();
}

// ==================== Flags ====================
export async function submitFlag(targetType, targetId, reason, notes = "") {
  const res = await fetch(`${API_BASE}/api/flags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_type: targetType,
      target_id: targetId,
      reason,
      notes,
    }),
  });
  if (!res.ok) throw new Error("Failed to submit flag");
  return res.json();
}

// ==================== Progress & Dashboard ====================
export async function getDashboardStats(documentId = null) {
  // Lets the server count streak days by the student's own calendar, not UTC
  let url = `${API_BASE}/api/progress/dashboard?tz_offset_minutes=${new Date().getTimezoneOffset()}`;
  if (documentId) url += `&document_id=${documentId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch dashboard stats");
  return res.json();
}

export async function getDueFlashcards(documentId = null) {
  let url = `${API_BASE}/api/flashcards/due`;
  if (documentId) url += `?document_id=${documentId}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch due flashcards");
  return res.json();
}

// ==================== Explainer Chat ====================
export async function askDocumentChat(documentId, question, explainLikeNew = false, conversationHistory = []) {
  const res = await fetch(`${API_BASE}/api/documents/${documentId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      explain_like_new: explainLikeNew,
      conversation_history: conversationHistory,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Chat request failed");
  }
  return res.json();
}

// ==================== Weak-Spot Quiz ====================
export async function generateWeakSpotQuiz(documentId) {
  const res = await fetch(`${API_BASE}/api/documents/${documentId}/quiz/weak-spots`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Weak-spot quiz generation failed");
  }
  return res.json();
}

