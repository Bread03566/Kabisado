import React, { useState, useRef } from 'react';
import { 
  Upload, 
  FileText, 
  FileUp, 
  Trash2, 
  BookOpen, 
  BrainCircuit, 
  HelpCircle, 
  Sparkles, 
  Clock, 
  Layers, 
  ArrowRight,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import Mascot from '../components/Mascot';
import { uploadDocumentFile, createDocumentFromText, deleteDocument } from '../services/api';

const SAMPLE_MODULE = {
  title: "Aralin 1: Ang Kasaysayan ng Kilusang Propaganda at si Jose Rizal",
  text: `Kabanata 1: Ang Kalagayan ng Pilipinas noong Ika-19 na Siglo
Noong ika-19 na siglo, ang Pilipinas ay nasa ilalim ng pamamahala ng Imperyong Espanyol. Laganap ang diskriminasyon sa pagitan ng mga Kastila (peninsulares at insulares) at mga katutubong Pilipino (indio). Ang mga prayle ang may hawak sa malalaking hacienda at may matinding impluwensya sa pamahalaan at edukasyon. Sa kabila nito, ang pagbubukas ng Suez Canal noong 1869 ay nagdulot ng mas mabilis na kalakalan at pagpasok ng mga kaisipang liberal mula sa Europa.

Kabanata 2: Ang Pag-usbong ng Kilusang Propaganda
Ang Kilusang Propaganda ay isang mapayapang kilusan na binuo ng mga ilustrado o mga Pilipinong nakapag-aral sa Europa. Ang kanilang pangunahing layunin ay hindi ang agarang himagsikan, kundi ang asimilasyon o pagiging opisyal na lalawigan ng Espanya ang Pilipinas. Hiniling nila ang pantay na karapatan sa ilalim ng batas, kalayaan sa pamamahayag, sekularisasyon ng mga parokya, at pagkakaroon ng kinatawan sa Cortes ng Espanya. Ang opisyal na pahayagan ng kilusan ay ang La Solidaridad na itinatag ni Graciano Lopez Jaena sa Barcelona.

Kabanata 3: Ang Buhay at mga Akda ni Dr. Jose Rizal
Si Dr. Jose Protacio Rizal Mercado y Alonso Realonda ay isinilang noong Hunyo 19, 1861 sa Calamba, Laguna. Siya ay itinuturing na Pambansang Bayani ng Pilipinas dahil sa kanyang matatalinong akda na gumising sa damdaming makabayan ng mga mamamayan. Ang kanyang unang nobela, ang Noli Me Tangere, ay nalimbag sa Berlin noong 1887. Ito ay isang nobelang panlipunan na naglantad sa mga sakit ng lipunan at pang-aabuso ng mga tiwaling pinuno. Ang kanyang pangalawang nobela, ang El Filibusterismo, ay nalimbag sa Ghent noong 1891 na may mas mapangahas at rebolusyonaryong diwa.

Kabanata 4: Ang Pagtatapos ng Kilusan at Pagsiklab ng Katipunan
Bagamat hindi nakamit ng Kilusang Propaganda ang lahat ng kanilang hiniling na reporma mula sa pamahalaang Espanyol, ang kanilang mga isinulat ay naging mitsa upang maitatag ni Andres Bonifacio ang KKK (Kataas-taasang, Kagalang-galangang Katipunan ng mga Anak ng Bayan) noong Hulyo 7, 1892. Dito nagsimula ang armadong rebolusyon para sa ganap na kalayaan ng Inang Bayan.`
};

export default function UploadLibraryView({ 
  documents, 
  onSelectDoc, 
  onRefreshDocs, 
  showToast 
}) {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'paste'
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [customTitle, setCustomTitle] = useState('');
  const [pasteTitle, setPasteTitle] = useState('');
  const [pasteText, setPasteText] = useState('');
  const fileInputRef = useRef(null);

  const handleFileUpload = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'docx') {
      showToast('error', 'PDF o DOCX file lang muna ang puwede, lodi!');
      return;
    }

    setIsUploading(true);
    try {
      showToast('info', 'Binabasa ni Kabi ang module mo... Wag kang maingay!');
      const newDoc = await uploadDocumentFile(file, customTitle);
      showToast('success', `Na-upload na ang "${newDoc.title}"! Handa na para sa review.`);
      setCustomTitle('');
      await onRefreshDocs();
      onSelectDoc(newDoc);
    } catch (err) {
      showToast('error', err.message || 'May problema sa pag-upload.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handlePasteSubmit = async (e) => {
    e.preventDefault();
    if (!pasteTitle.trim() || !pasteText.trim()) {
      showToast('error', 'Pakilagyan ng title at text ang module mo!');
      return;
    }

    setIsUploading(true);
    try {
      showToast('info', 'Pinoproseso ang teksto at hinahati sa topics...');
      const newDoc = await createDocumentFromText(pasteTitle, pasteText);
      showToast('success', `Na-save na ang "${newDoc.title}"!`);
      setPasteTitle('');
      setPasteText('');
      await onRefreshDocs();
      onSelectDoc(newDoc);
    } catch (err) {
      showToast('error', err.message || 'May problema sa pag-save.');
    } finally {
      setIsUploading(false);
    }
  };

  const loadSampleHandout = () => {
    setPasteTitle(SAMPLE_MODULE.title);
    setPasteText(SAMPLE_MODULE.text);
    setActiveTab('paste');
    showToast('info', 'Na-load na ang Sample Handout (Rizal & Propaganda). Pindutin ang "I-save at I-proseso".');
  };

  const handleDelete = async (docId, title, e) => {
    e.stopPropagation();
    if (!window.confirm(`Sigurado ka bang buburahin ang "${title}"?`)) return;

    try {
      await deleteDocument(docId);
      showToast('success', `Burado na ang "${title}".`);
      onRefreshDocs();
    } catch (err) {
      showToast('error', 'Hindi nabura ang document.');
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-10">
      {/* Hero Roasting & Welcome Banner */}
      <div className="relative overflow-hidden bg-gradient-to-br from-amber-500 via-amber-600 to-orange-600 text-white rounded-3xl p-6 sm:p-8 shadow-xl shadow-amber-500/10">
        <div className="relative z-10 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="text-center sm:text-left space-y-2 max-w-xl">
            <span className="inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-white/20 backdrop-blur-md">
              🦉 Puyat pero Papasa
            </span>
            <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">
              Aral ngayon, pasa bukas.
            </h1>
            <p className="text-amber-100 text-sm sm:text-base leading-relaxed">
              I-upload mo na ang handouts, reviewers, o modules mo. Si Kabi na bahala magbuod, gumawa ng flashcards, at maghanda ng exam questions para sa'yo!
            </p>
            <div className="pt-2">
              <button
                onClick={loadSampleHandout}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white text-amber-900 hover:bg-amber-50 text-xs sm:text-sm font-bold rounded-xl shadow-md transition transform active:scale-95"
              >
                <Sparkles className="w-4 h-4 text-amber-600" />
                <span>Subukan ang Sample Handout (1-Click Demo)</span>
              </button>
            </div>
          </div>

          <Mascot 
            mood={documents.length === 0 ? "sleepy" : "studying"} 
            size="xl" 
            message={
              documents.length === 0 
                ? "Wala ka pang module. Bukas na naman? I-upload mo na yan!" 
                : "Ayan, may aralin na tayo! Wag nang mag-procrastinate!"
            }
          />
        </div>

        {/* Ambient background circles */}
        <div className="absolute -right-10 -bottom-10 w-64 h-64 bg-white/10 rounded-full blur-2xl pointer-events-none" />
        <div className="absolute -left-10 -top-10 w-48 h-48 bg-amber-400/20 rounded-full blur-xl pointer-events-none" />
      </div>

      {/* Upload & Paste Section */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {/* Tab Headers */}
        <div className="flex border-b border-slate-200 bg-slate-50/50">
          <button
            onClick={() => setActiveTab('upload')}
            className={`flex-1 py-3.5 px-4 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition border-b-2 ${
              activeTab === 'upload'
                ? 'border-amber-500 text-amber-700 bg-white'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>Mag-upload ng File (PDF / DOCX)</span>
          </button>
          <button
            onClick={() => setActiveTab('paste')}
            className={`flex-1 py-3.5 px-4 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition border-b-2 ${
              activeTab === 'paste'
                ? 'border-amber-500 text-amber-700 bg-white'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Mag-paste ng Text o Notes</span>
          </button>
        </div>

        <div className="p-6">
          {activeTab === 'upload' ? (
            <div className="space-y-4">
              {/* Optional custom title input */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Pangalan ng Module (Optional):
                </label>
                <input
                  type="text"
                  placeholder="Halimbawa: Bio 101 - Cell Biology Chapter 1"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  className="w-full text-xs sm:text-sm px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                />
              </div>

              {/* Drag and Drop Box */}
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center cursor-pointer transition flex flex-col items-center justify-center gap-3 ${
                  isDragging
                    ? 'border-amber-500 bg-amber-50/60'
                    : 'border-slate-300 hover:border-amber-400 hover:bg-amber-50/30'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => handleFileUpload(e.target.files?.[0])}
                  accept=".pdf,.docx"
                  className="hidden"
                />

                <div className="w-14 h-14 rounded-2xl bg-amber-100 flex items-center justify-center text-amber-700 shadow-xs">
                  <FileUp className="w-7 h-7" />
                </div>

                <div>
                  <p className="font-bold text-slate-800 text-sm sm:text-base">
                    I-drag dito ang PDF o Word DOCX file, o mag-browse sa device
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Tinatanggap: <span className="font-semibold text-slate-700">PDF (.pdf)</span> at <span className="font-semibold text-slate-700">Word (.docx)</span>
                  </p>
                </div>

                {isUploading && (
                  <div className="flex items-center gap-2 text-xs font-semibold text-amber-600 bg-amber-50 px-4 py-2 rounded-full border border-amber-200 animate-pulse mt-2">
                    <Sparkles className="w-4 h-4 animate-spin" />
                    <span>Binabasa at hinahati sa mga aralin...</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <form onSubmit={handlePasteSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Pamagat ng Lesson / Notes:
                </label>
                <input
                  type="text"
                  placeholder="Halimbawa: Rizal - Kabanata 1 at 2"
                  value={pasteTitle}
                  onChange={(e) => setPasteTitle(e.target.value)}
                  className="w-full text-xs sm:text-sm px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                  required
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-slate-700">
                    Nilalaman o Text ng Module:
                  </label>
                  <span className="text-[11px] text-slate-400">
                    {pasteText.length} letra • {pasteText.split(/\s+/).filter(Boolean).length} salita
                  </span>
                </div>
                <textarea
                  rows={8}
                  placeholder="I-paste dito ang handouts, lecture notes, o transcript..."
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  className="w-full text-xs sm:text-sm p-3.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 font-mono"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={loadSampleHandout}
                  className="px-4 py-2 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-xl transition"
                >
                  I-paste ang Sample Handout
                </button>
                <button
                  type="submit"
                  disabled={isUploading}
                  className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition disabled:opacity-50 flex items-center gap-2"
                >
                  {isUploading ? (
                    <>
                      <Sparkles className="w-4 h-4 animate-spin" />
                      <span>Pinoproseso...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>I-save at I-proseso</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* Library of Uploaded Modules */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              Ang Aklatan Mo ({documents.length})
            </h2>
            <p className="text-xs text-slate-500">
              Pumili ng module para makita ang buod, mag-flashcards, o mag-quiz.
            </p>
          </div>
        </div>

        {documents.length === 0 ? (
          /* Empty State */
          <div className="bg-white rounded-2xl border border-dashed border-slate-300 p-12 text-center flex flex-col items-center justify-center space-y-3">
            <Mascot mood="sleepy" size="lg" />
            <h3 className="font-bold text-slate-800 text-lg">
              Wala ka pang module. Bukas na naman?
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 max-w-md">
              Huwag mag-cram sa gabi bago ang exam! Mag-upload ng module sa itaas o pindutin ang "Subukan ang Sample Handout".
            </p>
            <button
              onClick={loadSampleHandout}
              className="mt-2 inline-flex items-center gap-2 px-4 py-2 bg-amber-500 text-white font-semibold text-xs rounded-xl shadow hover:bg-amber-600 transition"
            >
              <Sparkles className="w-4 h-4" />
              <span>Mag-load ng Sample Handout</span>
            </button>
          </div>
        ) : (
          /* Grid of Document Cards */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {documents.map((doc) => (
              <div
                key={doc.id}
                onClick={() => onSelectDoc(doc)}
                className="group bg-white rounded-2xl border border-slate-200 p-5 shadow-xs hover:shadow-md hover:border-amber-400 transition cursor-pointer flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wide ${
                      doc.file_type === 'pdf'
                        ? 'bg-red-50 text-red-700 border border-red-200'
                        : doc.file_type === 'docx'
                        ? 'bg-blue-50 text-blue-700 border border-blue-200'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    }`}>
                      {doc.file_type}
                    </span>

                    <button
                      onClick={(e) => handleDelete(doc.id, doc.title, e)}
                      title="Burahin ang module"
                      className="text-slate-400 hover:text-rose-600 p-1 rounded-md hover:bg-rose-50 transition"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <h3 className="font-bold text-slate-900 group-hover:text-amber-700 transition line-clamp-2 text-sm sm:text-base leading-snug">
                    {doc.title}
                  </h3>

                  <div className="flex items-center gap-3 text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100">
                    <div className="flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5 text-amber-500" />
                      <span>{doc.topics_count || 1} Topics</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <BrainCircuit className="w-3.5 h-3.5 text-indigo-500" />
                      <span>{doc.flashcards_count || 0} Cards</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <HelpCircle className="w-3.5 h-3.5 text-emerald-500" />
                      <span>{doc.questions_count || 0} Questions</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-amber-600 group-hover:text-amber-700">
                  <span>Aralin Na</span>
                  <ArrowRight className="w-4 h-4 transform group-hover:translate-x-1 transition" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
