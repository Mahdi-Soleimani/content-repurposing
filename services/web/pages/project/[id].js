import { useState, useRef, useEffect, useCallback } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { 
  initUpload, uploadToS3, completeUpload, 
  submitText, submitUrl, 
  getProjects, createProject, getProjectWorkspace, deleteProject,
  updateDraft, generateContent, discardTranscript, renameProject, updateProjectSettings, getJobOutputs
} from '../../src/lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';

const statusMap = {
  CREATED: "در حال آماده سازی...",
  UPLOADING: "در حال آپلود...",
  UPLOADED: "آپلود کامل شد",
  QUEUED: "در صف پردازش",
  PROCESSING: "در حال پردازش...",
  COMPLETED: "تکمیل شد ✅",
  FAILED: "خطا ❌",
  SUBMITTED: "ارسال شد",
  READY: "آماده ✅",
  PENDING: "در انتظار..."
};

export default function Home() {
  const [workspace, setWorkspace] = useState(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editProjectName, setEditProjectName] = useState("");
  const [projectId, setProjectId] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // UI States
  const [showInputModal, setShowInputModal] = useState(false);
  const [activeTab, setActiveTab] = useState('media');
  const [activeTranscriptIndex, setActiveTranscriptIndex] = useState(0);
  
  // Upload states
  const [file, setFile] = useState(null);
  const [textContent, setTextContent] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  
  // Generation States
  const [draftLoaded, setDraftLoaded] = useState(false);
  const [draft, setDraft] = useState({
    article: 0,
    telegram: 0,
    linkedin: 0,
    carousel: 0,
    summary: 0,
    twitter: 0
  });
  const [isGenerating, setIsGenerating] = useState(false);

  const toggleJobAccordion = async (jobId) => {
    if (expandedJobs[jobId]) {
      const newExp = { ...expandedJobs };
      delete newExp[jobId];
      setExpandedJobs(newExp);
    } else {
      setExpandedJobs(prev => ({ ...prev, [jobId]: { loading: true, data: null } }));
      try {
        const data = await getJobOutputs(projectId, jobId);
        setExpandedJobs(prev => ({ ...prev, [jobId]: { loading: false, data } }));
      } catch (err) {
        console.error("Failed to load job outputs", err);
        setExpandedJobs(prev => ({ ...prev, [jobId]: { loading: false, data: null, error: true } }));
      }
    }
  };

  const fetchWorkspace = useCallback(async (pid) => {
    try {
      const data = await getProjectWorkspace(pid);
      setWorkspace(data);
    } catch (err) {
      console.error("Failed to load workspace:", err);
    }
  }, []);

  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [selectedSttProvider, setSelectedSttProvider] = useState('shenava');
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [selectedOutput, setSelectedOutput] = useState(null);
  const [expandedJobs, setExpandedJobs] = useState({});
  const [settingsTab, setSettingsTab] = useState('stt');

  const router = useRouter();
  const { id } = router.query;

  // Initialize
  useEffect(() => {
    if (!id) return;
    
    async function init() {
      try {
        setLoading(true);
        setProjectId(id);
        await fetchWorkspace(id);
      } catch (err) {
        console.error("Initialization error:", err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [id, fetchWorkspace]);

  useEffect(() => {
    if (workspace?.project?.stt_provider) {
      setSelectedSttProvider(workspace.project.stt_provider);
    }
  }, [workspace?.project?.stt_provider]);

  // Sync draft from backend (only once)
  useEffect(() => {
    if (workspace?.generation_draft?.requested_outputs && !draftLoaded) {
      const loadedDraft = workspace.generation_draft.requested_outputs;
      setDraft(prev => ({ ...prev, ...loadedDraft }));
      setDraftLoaded(true);
    }
  }, [workspace, draftLoaded]);

  const handleSaveSettings = async () => {
    try {
      setIsSavingSettings(true);
      await updateProjectSettings(projectId, { stt_provider: selectedSttProvider });
      await fetchWorkspace(projectId);
      setShowSettingsModal(false);
    } catch (e) {
      alert("خطا در ذخیره تنظیمات: " + e.message);
    } finally {
      setIsSavingSettings(false);
    }
  };

  // Polling Logic
  useEffect(() => {
    if (!projectId || !workspace) return;
    
    const needsExtractionPolling = 
      workspace.uploads?.some(u => ['UPLOADING', 'QUEUED', 'PROCESSING'].includes(u.status)) ||
      workspace.sources?.some(s => ['PENDING', 'PROCESSING'].includes(s.status));
      
    const needsGenerationPolling = 
      workspace.generation_jobs?.some(j => ['PENDING', 'PROCESSING'].includes(j.status));
      
    let interval = null;
    if (needsExtractionPolling) {
      interval = setInterval(() => fetchWorkspace(projectId), 3000);
    } else if (needsGenerationPolling) {
      interval = setInterval(() => fetchWorkspace(projectId), 5000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    }
  }, [projectId, workspace, fetchWorkspace]);


  // ──── Handlers ────

  const handleMediaUpload = async () => {
    if (!file || !projectId) return;
    try {
      setError(null);
      setUploadStatus('CREATED');
      setProgress(0);
      
      const initData = await initUpload(projectId, file);
      setUploadStatus('UPLOADING');
      
      await uploadToS3(initData.upload_url, file, (percent) => setProgress(percent));
      
      setUploadStatus('UPLOADED');
      await completeUpload(initData.upload_id);
      
      setUploadStatus('COMPLETED');
      setTimeout(() => {
        setShowInputModal(false);
        setUploadStatus('');
        setFile(null);
        fetchWorkspace(projectId);
      }, 1500);
    } catch (err) {
      setUploadStatus('FAILED');
      setError(err.message || "خطا در آپلود");
    }
  };

  const handleRenameProject = async () => {
    if (!editProjectName.trim() || !projectId) return;
    try {
      await renameProject(projectId, editProjectName);
      setIsEditingName(false);
      fetchWorkspace(projectId);
    } catch (err) {
      setError(err.message || "خطا در تغییر نام پروژه");
    }
  };

  const handleTextSubmit = async () => {
    if (!textContent.trim() || !projectId) return;
    try {
      setError(null);
      setUploadStatus('PROCESSING');
      await submitText(projectId, textContent);
      setUploadStatus('SUBMITTED');
      setTimeout(() => {
        setShowInputModal(false);
        setUploadStatus('');
        setTextContent('');
        fetchWorkspace(projectId);
      }, 1000);
    } catch (err) {
      setUploadStatus('FAILED');
      setError(err.message || "خطا در ارسال");
    }
  };

  const handleUrlSubmit = async () => {
    if (!linkUrl.trim() || !projectId) return;
    try {
      setError(null);
      setUploadStatus('PROCESSING');
      await submitUrl(projectId, linkUrl);
      setUploadStatus('SUBMITTED');
      setTimeout(() => {
        setShowInputModal(false);
        setUploadStatus('');
        setLinkUrl('');
        fetchWorkspace(projectId);
      }, 1000);
    } catch (err) {
      setUploadStatus('FAILED');
      setError(err.message || "خطا در ارسال");
    }
  };

  const handleSubmit = () => {
    if (activeTab === 'media') handleMediaUpload();
    else if (activeTab === 'text') handleTextSubmit();
    else if (activeTab === 'link') handleUrlSubmit();
  };

  const handleDeleteProject = async () => {
    if (!projectId || !confirm("آیا از حذف این پروژه مطمئن هستید؟ تمام داده‌ها حذف خواهند شد.")) return;
    try {
      setLoading(true);
      await deleteProject(projectId);
      router.push('/');
    } catch (err) {
      alert("خطا در حذف پروژه: " + err.message);
      setLoading(false);
    }
  };

  const handleQuantityChange = async (platform, delta) => {
    const newVal = Math.max(0, (draft[platform] || 0) + delta);
    const newDraft = { ...draft, [platform]: newVal };
    setDraft(newDraft);
    
    try {
      await updateDraft(projectId, newDraft);
    } catch (e) {
      console.error(e);
    }
  };

  const handleGenerate = async () => {
    if (!activeTranscript) return;
    try {
      setIsGenerating(true);
      
      const requestedOutputs = Object.fromEntries(
        Object.entries(draft).filter(([k, v]) => v > 0)
      );

      await generateContent(projectId, activeTranscript.id, requestedOutputs);
      
      setDraft({
        article: 0,
        telegram: 0,
        linkedin: 0,
        carousel: 0,
        summary: 0,
        twitter: 0
      }); 
      setActiveTranscriptIndex(0); // Reset index for the next item
      await fetchWorkspace(projectId);
    } catch (e) {
      alert(e.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDiscard = async () => {
    if (!activeTranscript || !confirm("آیا از حذف و انصراف از تولید محتوا برای این فایل مطمئن هستید؟")) return;
    try {
      setIsGenerating(true);
      await discardTranscript(projectId, activeTranscript.id);
      setActiveTranscriptIndex(0); // Reset index
      await fetchWorkspace(projectId);
    } catch (e) {
      alert("خطا در حذف: " + e.message);
    } finally {
      setIsGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white" dir="rtl">
        <div className="animate-pulse flex flex-col items-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
          <p className="text-gray-400">در حال بارگذاری محیط کاری...</p>
        </div>
      </div>
    );
  }

  const pendingTranscripts = workspace?.transcripts?.filter(t => t.content_status === 'READY') || [];
  
  // Ensure index is within bounds
  let currentIndex = activeTranscriptIndex;
  if (currentIndex >= pendingTranscripts.length && pendingTranscripts.length > 0) {
    currentIndex = pendingTranscripts.length - 1;
  } else if (currentIndex < 0) {
    currentIndex = 0;
  }
  
  const activeTranscript = pendingTranscripts[currentIndex];
  
  const handleNextTranscript = () => {
    if (currentIndex < pendingTranscripts.length - 1) {
      setActiveTranscriptIndex(currentIndex + 1);
    }
  };

  const handlePrevTranscript = () => {
    if (currentIndex > 0) {
      setActiveTranscriptIndex(currentIndex - 1);
    }
  };
  
  let activeFileName = "فایل ناشناس";
  let activeIcon = "🎬";
  
  if (activeTranscript) {
    if (!activeTranscript.media_id) {
      activeFileName = 'محتوای متنی';
      activeIcon = '📝';
    } else {
      const media = workspace?.media?.find(m => m.id === activeTranscript.media_id);
      if (media) {
        const upload = workspace?.uploads?.find(u => u.source_id === media.source_id);
        const source = workspace?.sources?.find(s => s.id === media.source_id);
        
        if (source && source.source_type === 'url') {
          activeFileName = source.source_url;
          if (source.source_url?.includes('youtube.com') || source.source_url?.includes('youtu.be')) activeIcon = '▶️';
          else if (source.source_url?.includes('instagram.com')) activeIcon = '📸';
          else activeIcon = '🔗';
        } else if (upload) {
          activeFileName = upload.original_filename;
          activeIcon = upload.content_type?.includes('video') ? '🎬' : '🎙';
        } else if (source) {
          activeFileName = 'محتوای متنی';
          activeIcon = '📝';
        }
      }
    }
  }

  const totalRequested = Object.values(draft).reduce((a, b) => a + b, 0);

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6 font-sans" dir="rtl">
      <Head>
        <title>Content Repurposing | Dashboard</title>
      </Head>

      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <header className="page-header" style={{display: 'flex', alignItems: 'center', marginBottom: '2.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid #1f2937'}}>
        <button onClick={() => router.push('/')} style={{
          background: 'transparent', 
          border: '1px solid #374151', 
          color: '#9ca3af',
          borderRadius: '0.75rem',
          cursor: 'pointer',
          padding: '8px 12px',
          marginLeft: '1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <span>🏠</span> داشبورد
        </button>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isEditingName ? (
            <>
              <input 
                type="text" 
                value={editProjectName}
                onChange={(e) => setEditProjectName(e.target.value)}
                className="bg-gray-800 text-white px-3 py-1 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                style={{ fontSize: '1.25rem', fontWeight: 'bold' }}
                autoFocus
              />
              <button 
                onClick={handleRenameProject}
                className="bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-white text-sm"
              >
                تایید
              </button>
              <button 
                onClick={() => setIsEditingName(false)}
                className="bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded text-white text-sm"
              >
                لغو
              </button>
            </>
          ) : (
            <>
              <h1 style={{margin: 0, fontSize: '1.5rem', fontWeight: 'bold'}}>
                {workspace?.project?.name || "فضای کاری تولید محتوا"}
              </h1>
              <button 
                onClick={() => {
                  setEditProjectName(workspace?.project?.name || "");
                  setIsEditingName(true);
                }}
                className="text-gray-400 hover:text-white transition-colors"
                title="ویرایش نام پروژه"
              >
                ✏️
              </button>
            </>
          )}
        </div>
        <div className="flex gap-4">
            <button 
              onClick={() => setShowSettingsModal(true)}
              className="bg-gray-800 hover:bg-gray-700 px-5 py-2.5 rounded-xl font-medium transition-colors border border-gray-700"
            >
              ⚙️ تنظیمات پردازش
            </button>
            <button 
              onClick={() => setShowInputModal(true)}
              className="bg-indigo-600 hover:bg-indigo-500 px-5 py-2.5 rounded-xl font-medium transition-colors shadow-lg shadow-indigo-500/20"
            >
              + منبع جدید
            </button>
            <button 
              onClick={handleDeleteProject}
              className="bg-red-500/10 text-red-400 hover:bg-red-500/20 px-5 py-2.5 rounded-xl font-medium transition-colors border border-red-500/20"
            >
              حذف پروژه
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
          {/* ──── Left Column: Inputs & Generation ──── */}
          <div className="space-y-8">
            
            {/* Sources */}
            <section className="bg-gray-900 border border-gray-800 rounded-3xl p-6 shadow-xl relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 to-purple-500"></div>
              <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
                <span className="text-indigo-400">📥</span> منابع ورودی
              </h2>
              
              <div className="space-y-4">
                {workspace?.uploads?.length === 0 && workspace?.sources?.length === 0 && (
                  <p className="text-gray-500 text-sm text-center py-4">هنوز منبعی اضافه نشده است.</p>
                )}
                {workspace?.uploads?.filter(u => {
                  if (u.status?.toUpperCase() === 'DISCARDED' || u.status?.toUpperCase() === 'DELETED') return false;
                  const source = workspace?.sources?.find(s => s.id === u.source_id);
                  return (!source || source.source_type === 'media') && source?.status?.toUpperCase() !== 'DISCARDED';
                }).map(u => (
                  <div key={u.id} className="bg-gray-950 p-4 rounded-xl border border-gray-800 flex justify-between items-center group">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <span className="text-2xl">{u.content_type?.includes('video') ? '🎥' : '🎙'}</span>
                      <div className="truncate">
                        <p className="text-sm font-medium text-gray-200 truncate" dir="ltr">{u.original_filename}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{statusMap[u.status?.toUpperCase()] || u.status}</p>
                      </div>
                    </div>
                  </div>
                ))}
                {workspace?.sources?.filter(s => (s.source_type === 'text' || s.source_type === 'url') && s.status?.toUpperCase() !== 'DISCARDED' && s.status?.toUpperCase() !== 'DELETED').map(s => {
                  let icon = '📝';
                  if (s.source_type === 'url') {
                    if (s.source_url?.includes('youtube.com') || s.source_url?.includes('youtu.be')) icon = '▶️'; // YouTube
                    else if (s.source_url?.includes('instagram.com')) icon = '📸'; // Instagram
                    else icon = '🔗';
                  }
                  return (
                    <div key={s.id} className="bg-gray-950 p-4 rounded-xl border border-gray-800 flex justify-between items-center group">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <span className="text-2xl">{icon}</span>
                        <div className="truncate">
                          <p className="text-sm font-medium text-gray-200 truncate" dir="ltr">
                            {s.source_type === 'url' ? s.source_url : (s.source_content?.substring(0, 30) + '...')}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">{statusMap[s.status?.toUpperCase()] || s.status}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Content Ready & Draft Selection */}
            {activeTranscript && (
              <section className="bg-gray-900 border border-gray-800 rounded-3xl p-6 shadow-xl relative overflow-hidden animate-fade-in">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-cyan-500"></div>
                
                <div className="flex items-center justify-between mb-4 gap-4">
                  <h2 className="text-lg font-bold flex items-center gap-2 text-blue-400 min-w-0 flex-1">
                    <span className="text-2xl shrink-0">{activeIcon}</span>
                    <span dir="ltr" className="text-gray-100 text-base truncate">{activeFileName}</span>
                  </h2>
                  <div className="flex items-center gap-3 shrink-0">
                    {pendingTranscripts.length > 1 && (
                      <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-1 mr-2" dir="ltr">
                        <button 
                          onClick={handlePrevTranscript}
                          disabled={currentIndex === 0}
                          className="w-8 h-8 flex items-center justify-center rounded hover:bg-gray-700 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                        >
                          ◄
                        </button>
                        <span className="text-xs font-bold w-12 text-center text-gray-300">
                          {currentIndex + 1} / {pendingTranscripts.length}
                        </span>
                        <button 
                          onClick={handleNextTranscript}
                          disabled={currentIndex === pendingTranscripts.length - 1}
                          className="w-8 h-8 flex items-center justify-center rounded hover:bg-gray-700 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                        >
                          ►
                        </button>
                      </div>
                    )}
                    <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-1.5 rounded-md font-medium shrink-0">
                      {pendingTranscripts.length} فایل آماده تولید
                    </span>
                  </div>
                </div>

                <div className="flex gap-2 mb-6 text-xs">
                  <span className="bg-gray-800 text-gray-300 px-2 py-1 rounded-md flex items-center gap-1">
                    <span>⏱</span>
                    مدت زمان: {activeTranscript.duration_seconds ? Math.round(activeTranscript.duration_seconds / 60) + ' دقیقه' : 'نامشخص'}
                  </span>
                  <span className="bg-gray-800 text-gray-300 px-2 py-1 rounded-md flex items-center gap-1">
                    <span>⚙️</span>
                    موتور: {activeTranscript.provider === 'avalai' ? 'اول‌هوش' : (activeTranscript.provider === 'shenava' ? 'شناوا' : (activeTranscript.provider || 'نامشخص'))}
                  </span>
                </div>

                <div className="border-t border-gray-800 pt-6 mt-2">
                  <p className="text-sm text-gray-400 mb-6">فایل شما پردازش شده و آماده تبدیل به محتوای متنی است. خروجی‌های مورد نیاز را انتخاب کنید:</p>
                  
                  <div className="space-y-3 mb-6">
                    {[
                      { id: 'article', icon: '📝', label: 'مقاله سایت (وبلاگ)' },
                      { id: 'telegram', icon: '📱', label: 'پست تلگرام' },
                      { id: 'carousel', icon: '🖼', label: 'اسلاید اینستاگرام' }
                    ].map(platform => (
                      <div key={platform.id} className="flex items-center justify-between bg-gray-950/50 p-3 rounded-xl border border-gray-800/50 hover:border-gray-700 transition-colors">
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">{platform.icon}</span>
                          <span className="text-sm font-medium text-gray-200">{platform.label}</span>
                        </div>
                        <div className="flex items-center gap-4 bg-gray-900 rounded-lg p-1 border border-gray-700">
                          <button 
                            onClick={() => handleQuantityChange(platform.id, -1)}
                            className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-800 rounded-md transition-colors text-lg font-bold"
                          >
                            -
                          </button>
                          <span className="w-6 text-center text-lg font-bold">{draft[platform.id] || 0}</span>
                          <button 
                            onClick={() => handleQuantityChange(platform.id, 1)}
                            className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-800 rounded-md transition-colors text-lg font-bold"
                          >
                            +
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  <div className="flex gap-3">
                    <button
                      onClick={handleDiscard}
                      disabled={isGenerating}
                      className="px-6 py-3.5 bg-gray-800 hover:bg-red-500/20 text-gray-400 hover:text-red-400 border border-gray-700 hover:border-red-500/30 rounded-xl font-bold transition-all flex items-center justify-center disabled:opacity-50"
                    >
                      🗑️ انصراف و حذف
                    </button>
                    <button
                      onClick={handleGenerate}
                      disabled={totalRequested === 0 || isGenerating}
                      className="flex-1 py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-blue-500/20 flex justify-center items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span>{isGenerating ? 'در حال ارسال...' : '🚀 تایید و شروع تولید محتوا'}</span>
                    </button>
                  </div>
                </div>
              </section>
            )}

          </div>

          {/* ──── Right Column: Outputs Library ──── */}
          <div className="space-y-8">
            <section className="bg-gray-900 border border-gray-800 rounded-3xl p-6 shadow-xl relative overflow-hidden h-full">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 to-teal-500"></div>
              <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
                <span className="text-emerald-400">📚</span> کتابخانه خروجی‌ها
              </h2>
              
              <div className="space-y-4">
                {workspace?.generation_jobs?.length === 0 ? (
                  <p className="text-gray-500 text-sm text-center py-8">هنوز محتوایی تولید نشده است.</p>
                ) : (
                  workspace?.generation_jobs?.map(job => {
                    const isExpanded = !!expandedJobs[job.id];
                    const jobState = expandedJobs[job.id];
                    
                    return (
                      <div key={job.id} className="bg-gray-950 rounded-xl border border-gray-800 overflow-hidden transition-all">
                        {/* Job Header (Accordion Toggle) */}
                        <div 
                          onClick={() => toggleJobAccordion(job.id)}
                          className="p-4 flex justify-between items-center cursor-pointer hover:bg-gray-800/50 transition-colors"
                        >
                          <div>
                            <div className="flex items-center gap-3 mb-2">
                              <span className="text-sm font-bold text-gray-200">فرآیند تولید محتوا</span>
                              <span className="text-xs text-gray-500" dir="ltr">#{job.id.substring(0,8)}</span>
                              {job.status?.toUpperCase() === 'PROCESSING' || job.status?.toUpperCase() === 'PENDING' || job.status?.toUpperCase() === 'QUEUED' ? (
                                <span className="text-xs px-2 py-0.5 bg-blue-500/10 text-blue-400 rounded border border-blue-500/20">در حال پردازش...</span>
                              ) : job.status?.toUpperCase() === 'FAILED' ? (
                                <span className="text-xs px-2 py-0.5 bg-red-500/10 text-red-400 rounded border border-red-500/20">خطا</span>
                              ) : (
                                <span className="text-xs px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/20">تکمیل شده</span>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(job.requested_outputs || {}).filter(([_, count]) => count > 0).map(([platform, count]) => (
                                <span key={platform} className="text-xs text-gray-400 bg-gray-900 px-2 py-1 rounded border border-gray-800" dir="ltr">
                                  {platform}: {count}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="text-gray-500 text-xl font-bold">
                            {isExpanded ? '−' : '+'}
                          </div>
                        </div>

                        {/* Job Body (Expanded) */}
                        {isExpanded && (
                          <div className="p-4 border-t border-gray-800 bg-gray-900/30">
                            {jobState.loading ? (
                              <p className="text-sm text-gray-500 text-center py-4">در حال دریافت خروجی‌ها...</p>
                            ) : jobState.error ? (
                              <p className="text-sm text-red-400 text-center py-4">خطا در دریافت اطلاعات</p>
                            ) : !jobState.data?.outputs || Object.keys(jobState.data.outputs).length === 0 ? (
                              <p className="text-sm text-gray-500 text-center py-4">هنوز خروجی برای این فرآیند ثبت نشده است.</p>
                            ) : (
                              <div className="space-y-6">
                                {Object.entries(jobState.data.outputs).map(([type, outputs]) => {
                                  const platformLabel = type === 'telegram' ? 'پست تلگرام' : type === 'article' ? 'مقاله سایت' : type === 'carousel' ? 'اسلاید اینستاگرام' : type;
                                  const platformIcon = type === 'telegram' ? '📱' : type === 'article' ? '📝' : type === 'carousel' ? '🖼' : '📄';
                                  
                                  return (
                                    <div key={type} className="space-y-3">
                                      <h4 className="text-sm font-bold text-gray-300 flex items-center gap-2 mb-3">
                                        <span>{platformIcon}</span> {platformLabel}
                                      </h4>
                                      
                                      <div className="grid grid-cols-1 gap-3">
                                        {outputs.map(out => (
                                          <div 
                                            key={out.id}
                                            className="bg-gray-900 p-4 rounded-xl border border-gray-800 hover:border-gray-700 transition-colors group relative"
                                          >
                                            <div className="flex justify-between items-center mb-3 pb-3 border-b border-gray-800/50">
                                              <span className="text-sm font-medium text-gray-200">{out.title || 'خروجی آماده'}</span>
                                              <div className="flex gap-2">
                                                <button
                                                  onClick={() => {
                                                    let textToCopy = out.content;
                                                    if (!textToCopy && out.metadata?.slides?.length > 0) {
                                                      textToCopy = out.metadata.slides.map(s => `اسلاید ${s.index || ''}\n${s.title ? s.title + '\n' : ''}${s.text || ''}`).join('\n\n-----------------\n\n');
                                                    }
                                                    navigator.clipboard.writeText(textToCopy || '');
                                                    alert('متن کپی شد!');
                                                  }}
                                                  className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-lg border border-gray-700 transition-colors"
                                                  title="کپی خام متن/مارک‌داون"
                                                >
                                                  📋 کپی متن
                                                </button>
                                                <button
                                                  onClick={() => setSelectedOutput(out)}
                                                  className="text-xs bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-400 px-3 py-1.5 rounded-lg border border-indigo-500/20 transition-colors"
                                                >
                                                  👁️ پیش‌نمایش
                                                </button>
                                              </div>
                                            </div>
                                            <div className="text-sm text-gray-400 line-clamp-2 leading-relaxed mb-3">
                                              {out.content ? out.content : (out.metadata?.slides && out.metadata.slides.length > 0 ? `${out.metadata.slides.length} اسلاید ساخته شده...` : 'در حال تولید محتوا...')}
                                            </div>
                                            
                                            {/* Render Media if available */}
                                            {out.media && out.media.length > 0 && (
                                              <div className="flex flex-wrap gap-2 mt-2 pt-3 border-t border-gray-800/50">
                                                {out.media.map((m, idx) => (
                                                  m.url ? (
                                                    <img 
                                                      key={idx} 
                                                      src={m.url} 
                                                      alt={`media-${idx}`} 
                                                      className="h-16 w-16 object-cover rounded-lg border border-gray-700" 
                                                    />
                                                  ) : null
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </section>
          </div>
          
        </div>
      </div>

      {/* New Input Modal */}
      {showInputModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-3xl p-8 shadow-2xl relative">
            <button 
              onClick={() => setShowInputModal(false)}
              className="absolute top-4 left-4 text-gray-500 hover:text-gray-300"
            >
              ✕
            </button>
            
            <h3 className="text-xl font-bold mb-6 text-center">افزودن منبع جدید</h3>
            
            <div className="flex bg-gray-800/50 p-1 rounded-xl mb-6">
              <button onClick={() => setActiveTab('media')} className={`flex-1 py-2 rounded-lg text-sm transition-all ${activeTab === 'media' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200'}`}>🎥 فایل مدیا</button>
              <button onClick={() => setActiveTab('link')} className={`flex-1 py-2 rounded-lg text-sm transition-all ${activeTab === 'link' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200'}`}>🔗 لینک</button>
              <button onClick={() => setActiveTab('text')} className={`flex-1 py-2 rounded-lg text-sm transition-all ${activeTab === 'text' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200'}`}>📝 متن</button>
            </div>

            <div className="min-h-[160px] mb-6">
              {activeTab === 'media' && (
                <div 
                  onClick={() => !['UPLOADING', 'CREATED'].includes(uploadStatus) && fileInputRef.current?.click()}
                  className={`h-full border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center transition-all cursor-pointer
                    ${uploadStatus === 'UPLOADING' ? 'border-indigo-500/50 bg-indigo-500/5' : 'border-gray-700 hover:border-indigo-500 hover:bg-gray-800/50'}
                  `}
                >
                  <input 
                    type="file" ref={fileInputRef} onChange={e => setFile(e.target.files[0])} 
                    className="hidden" accept="video/*,audio/*"
                  />
                  {file ? (
                    <div className="text-center">
                      <p className="font-medium text-gray-200 truncate max-w-[200px]" dir="ltr">{file.name}</p>
                    </div>
                  ) : (
                    <p className="text-gray-400 text-sm">برای انتخاب فایل کلیک کنید</p>
                  )}
                </div>
              )}

              {activeTab === 'link' && (
                <div className="h-full flex flex-col justify-center">
                  <input 
                    type="url" placeholder="https://..." value={linkUrl}
                    onChange={(e) => setLinkUrl(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-700 rounded-xl p-4 text-white focus:border-indigo-500 outline-none" dir="ltr"
                  />
                </div>
              )}

              {activeTab === 'text' && (
                <div className="h-full flex flex-col">
                  <textarea 
                    placeholder="متن خود را اینجا وارد کنید..." value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    className="w-full h-32 bg-gray-950 border border-gray-700 rounded-xl p-4 text-white focus:border-indigo-500 outline-none resize-none"
                  />
                </div>
              )}
            </div>

            <button
              onClick={handleSubmit}
              disabled={['UPLOADING', 'PROCESSING', 'SUBMITTED', 'CREATED'].includes(uploadStatus)}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium transition-colors disabled:bg-gray-800 disabled:text-gray-500"
            >
              {uploadStatus === 'UPLOADING' ? 'در حال آپلود...' : 'ثبت منبع'}
            </button>
            
            {uploadStatus && uploadStatus !== 'FAILED' && (
              <p className="text-center text-sm text-indigo-400 mt-4">
                {statusMap[uploadStatus] || uploadStatus} {progress > 0 && uploadStatus === 'UPLOADING' ? `${progress}%` : ''}
              </p>
            )}
            {error && (
              <div className="mt-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-center">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}
          </div>
        </div>
      )}
      {/* Settings Modal */}
      {showSettingsModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-4xl bg-gray-900 border border-gray-800 rounded-3xl p-8 shadow-2xl relative">
            <button 
              onClick={() => setShowSettingsModal(false)}
              className="absolute top-4 left-4 text-gray-500 hover:text-gray-300"
            >
              ✕
            </button>
            
            <h3 className="text-xl font-bold mb-6 text-center">تنظیمات و آمار سیستم</h3>
            
            <div className="flex border-b border-gray-800 mb-6">
              <button 
                onClick={() => setSettingsTab('stt')}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${settingsTab === 'stt' ? 'text-indigo-400 border-b-2 border-indigo-400' : 'text-gray-500 hover:text-gray-300'}`}
              >
                تنظیمات STT
              </button>
              <button 
                onClick={() => setSettingsTab('system')}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${settingsTab === 'system' ? 'text-indigo-400 border-b-2 border-indigo-400' : 'text-gray-500 hover:text-gray-300'}`}
              >
                آمار و عیب‌یابی (Debug Center)
              </button>
            </div>
            
            <div className="max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
              {settingsTab === 'stt' && (
                <>
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-300 mb-4">موتور تبدیل صوت به متن (STT)</label>
                    
                    <div className="space-y-3">
                      <label className={`flex items-center p-4 border rounded-xl cursor-pointer transition-all ${selectedSttProvider === 'shenava' ? 'border-indigo-500 bg-indigo-500/10' : 'border-gray-700 bg-gray-800/50 hover:bg-gray-800'}`}>
                        <input 
                          type="radio" 
                          name="stt_provider" 
                          value="shenava"
                          checked={selectedSttProvider === 'shenava'}
                          onChange={(e) => setSelectedSttProvider(e.target.value)}
                          className="w-4 h-4 text-indigo-600 bg-gray-700 border-gray-600 focus:ring-indigo-600 focus:ring-offset-gray-800 ml-3" 
                        />
                        <div>
                          <span className="block text-sm font-medium text-white">شناوا (Shenava)</span>
                          <span className="block text-xs text-gray-400 mt-1">مدل سبک، رایگان، سرعت بالا - اجرا روی سرور محلی</span>
                        </div>
                      </label>
                      
                      <label className={`flex items-center p-4 border rounded-xl cursor-pointer transition-all ${selectedSttProvider === 'avalai' ? 'border-indigo-500 bg-indigo-500/10' : 'border-gray-700 bg-gray-800/50 hover:bg-gray-800'}`}>
                        <input 
                          type="radio" 
                          name="stt_provider" 
                          value="avalai"
                          checked={selectedSttProvider === 'avalai'}
                          onChange={(e) => setSelectedSttProvider(e.target.value)}
                          className="w-4 h-4 text-indigo-600 bg-gray-700 border-gray-600 focus:ring-indigo-600 focus:ring-offset-gray-800 ml-3" 
                        />
                        <div>
                          <span className="block text-sm font-medium text-white">اول‌هوش (AvalAI Whisper)</span>
                          <span className="block text-xs text-gray-400 mt-1">دقت بالا، هزینه دلاری (۰.۰۰۶$ / دقیقه) - پردازش ابری</span>
                        </div>
                      </label>
                    </div>
                  </div>

                  <button
                    onClick={handleSaveSettings}
                    disabled={isSavingSettings}
                    className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium transition-colors disabled:bg-gray-800 disabled:text-gray-500"
                  >
                    {isSavingSettings ? 'در حال ذخیره...' : 'ذخیره تنظیمات'}
                  </button>
                </>
              )}

              {settingsTab === 'system' && (
                <div className="space-y-8">
                  {/* Processing Usage */}
                  <div>
                    <h4 className="text-lg font-bold text-white mb-4 flex items-center gap-2"><span className="text-emerald-400">⚡</span> آمار مصرف پردازش (STT)</h4>
                    {(!workspace?.processing_usage || workspace.processing_usage.length === 0) ? (
                      <p className="text-gray-500 text-sm">هیچ لاگ پردازشی یافت نشد.</p>
                    ) : (
                      <div className="bg-gray-950 rounded-xl overflow-hidden border border-gray-800">
                        <table className="w-full text-sm text-right text-gray-400">
                          <thead className="bg-gray-900 text-gray-300">
                            <tr>
                              <th className="px-4 py-3">ارائه‌دهنده</th>
                              <th className="px-4 py-3">زمان صوت (ثانیه)</th>
                              <th className="px-4 py-3">زمان پردازش (ثانیه)</th>
                              <th className="px-4 py-3">هزینه (دلار)</th>
                              <th className="px-4 py-3">تاریخ</th>
                            </tr>
                          </thead>
                          <tbody>
                            {workspace.processing_usage.map(usage => (
                              <tr key={usage.id} className="border-t border-gray-800 hover:bg-gray-800/50">
                                <td className="px-4 py-3 font-medium text-white">{usage.provider} ({usage.model})</td>
                                <td className="px-4 py-3">{usage.audio_seconds?.toFixed(1) || '-'}</td>
                                <td className="px-4 py-3">{usage.duration_seconds?.toFixed(1) || '-'}</td>
                                <td className="px-4 py-3 text-emerald-400 font-mono">${usage.cost?.toFixed(4) || '0.0000'}</td>
                                <td className="px-4 py-3" dir="ltr">{new Date(usage.created_at).toLocaleString()}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Downloads */}
                  <div>
                    <h4 className="text-lg font-bold text-white mb-4 flex items-center gap-2"><span className="text-blue-400">⬇️</span> لاگ دانلود URLها</h4>
                    {(!workspace?.downloads || workspace.downloads.length === 0) ? (
                      <p className="text-gray-500 text-sm">هیچ لاگ دانلودی یافت نشد.</p>
                    ) : (
                      <div className="bg-gray-950 rounded-xl overflow-hidden border border-gray-800">
                        <table className="w-full text-sm text-right text-gray-400">
                          <thead className="bg-gray-900 text-gray-300">
                            <tr>
                              <th className="px-4 py-3">سرویس</th>
                              <th className="px-4 py-3">تلاش‌ها</th>
                              <th className="px-4 py-3">وضعیت</th>
                              <th className="px-4 py-3">خطا (در صورت وجود)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {workspace.downloads.map(dl => (
                              <tr key={dl.id} className="border-t border-gray-800 hover:bg-gray-800/50">
                                <td className="px-4 py-3 font-medium text-white">{dl.provider}</td>
                                <td className="px-4 py-3">{dl.attempt_count}</td>
                                <td className="px-4 py-3">
                                  <span className={`px-2 py-1 rounded text-xs ${dl.status?.toUpperCase() === 'SUCCESS' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                                    {dl.status}
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-red-400 truncate max-w-[200px]" title={dl.error_message}>{dl.error_message || '-'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Webhook Events */}
                  <div>
                    <h4 className="text-lg font-bold text-white mb-4 flex items-center gap-2"><span className="text-orange-400">🔗</span> رویدادهای وب‌هوک n8n</h4>
                    {(!workspace?.webhook_events || workspace.webhook_events.length === 0) ? (
                      <p className="text-gray-500 text-sm">هیچ وب‌هوکی ارسال نشده است.</p>
                    ) : (
                      <div className="bg-gray-950 rounded-xl overflow-hidden border border-gray-800">
                        <table className="w-full text-sm text-right text-gray-400">
                          <thead className="bg-gray-900 text-gray-300">
                            <tr>
                              <th className="px-4 py-3">نوع رویداد</th>
                              <th className="px-4 py-3">تلاش‌ها</th>
                              <th className="px-4 py-3">وضعیت</th>
                              <th className="px-4 py-3">آخرین خطا</th>
                              <th className="px-4 py-3">تاریخ ایجاد</th>
                            </tr>
                          </thead>
                          <tbody>
                            {workspace.webhook_events.map(wh => (
                              <tr key={wh.id} className="border-t border-gray-800 hover:bg-gray-800/50">
                                <td className="px-4 py-3 font-medium text-white" dir="ltr">{wh.event_type}</td>
                                <td className="px-4 py-3">{wh.attempts}</td>
                                <td className="px-4 py-3">
                                  <span className={`px-2 py-1 rounded text-xs ${wh.status?.toUpperCase() === 'SENT' ? 'bg-emerald-500/10 text-emerald-400' : wh.status?.toUpperCase() === 'FAILED' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'}`}>
                                    {wh.status}
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-red-400 truncate max-w-[150px]" title={wh.last_error}>{wh.last_error || '-'}</td>
                                <td className="px-4 py-3" dir="ltr">{new Date(wh.created_at).toLocaleString()}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* View Output Modal */}
      {selectedOutput && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-4xl max-h-[90vh] bg-gray-900 border border-gray-800 rounded-3xl shadow-2xl flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-gray-800">
              <h3 className="text-xl font-bold flex items-center gap-3">
                <span className="text-emerald-400">✨</span>
                <span>{selectedOutput.title || 'خروجی تولید شده'}</span>
                <span className="text-xs font-medium px-2 py-1 bg-gray-800 text-gray-300 rounded-md" dir="ltr">
                  {selectedOutput.platform || selectedOutput.output_type}
                </span>
              </h3>
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    let textToCopy = selectedOutput.content;
                    if (!textToCopy && selectedOutput.metadata?.slides?.length > 0) {
                      textToCopy = selectedOutput.metadata.slides.map(s => `اسلاید ${s.index || ''}\n${s.title ? s.title + '\n' : ''}${s.text || ''}`).join('\n\n-----------------\n\n');
                    }
                    navigator.clipboard.writeText(textToCopy || '');
                    alert('متن خام کپی شد!');
                  }}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors border border-gray-700 flex items-center gap-2"
                >
                  <span>📋</span> کپی متن خام
                </button>
                <button 
                  onClick={() => setSelectedOutput(null)}
                  className="text-gray-500 hover:text-gray-300 w-10 h-10 flex items-center justify-center bg-gray-800 rounded-lg"
                >
                  ✕
                </button>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1 bg-gray-950/50">
              <div className="markdown-body text-gray-200 leading-relaxed space-y-4" dir="rtl">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw, rehypeSanitize]}
                  components={{
                    h1: ({node, ...props}) => <h1 className="text-2xl font-bold text-white mt-6 mb-4" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-xl font-bold text-white mt-5 mb-3" {...props} />,
                    h3: ({node, ...props}) => <h3 className="text-lg font-bold text-white mt-4 mb-2" {...props} />,
                    p: ({node, ...props}) => <p className="mb-4 text-base" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc list-inside mb-4 space-y-1 mr-4" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal list-inside mb-4 space-y-1 mr-4" {...props} />,
                    li: ({node, ...props}) => <li className="text-gray-300" {...props} />,
                    a: ({node, ...props}) => <a className="text-indigo-400 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
                    blockquote: ({node, ...props}) => <blockquote className="border-r-4 border-indigo-500 pr-4 py-1 bg-gray-800/30 text-gray-400 italic mb-4" {...props} />,
                    img: ({node, ...props}) => <img className="rounded-xl shadow-lg max-w-full h-auto my-6" {...props} />,
                    code: ({node, inline, ...props}) => inline ? <code className="bg-gray-800 px-1.5 py-0.5 rounded text-indigo-300 text-sm font-mono" dir="ltr" {...props} /> : <pre className="bg-gray-900 p-4 rounded-xl overflow-x-auto text-sm text-gray-300 mb-4 border border-gray-800 font-mono" dir="ltr"><code {...props} /></pre>
                  }}
                >
                  {selectedOutput.content}
                </ReactMarkdown>
                
                {selectedOutput.media && selectedOutput.media.length > 0 && (
                  <div className="mt-8 space-y-4 border-t border-gray-800 pt-6">
                    <h3 className="text-xl font-bold text-white mb-4">مدیا و تصاویر پیوست</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      {selectedOutput.media.map((m, idx) => (
                        m.url && (
                          <div key={idx} className="bg-gray-900 rounded-xl overflow-hidden border border-gray-800 shadow-md group relative">
                            <img src={m.url} alt={`media-${idx}`} className="w-full aspect-square object-cover" />
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <a 
                                href={m.url} 
                                download={`media-${idx + 1}`}
                                target="_blank"
                                rel="noreferrer"
                                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 transition-colors shadow-lg"
                              >
                                <span>⬇️</span> دانلود
                              </a>
                            </div>
                          </div>
                        )
                      ))}
                    </div>
                  </div>
                )}

                {selectedOutput.metadata?.slides && selectedOutput.metadata.slides.length > 0 && (
                  <div className="mt-8 space-y-8 border-t border-gray-800 pt-6">
                    <h3 className="text-xl font-bold text-white mb-6">اسلایدها</h3>
                    {selectedOutput.metadata.slides.map((slide, idx) => (
                      <div key={idx} className="bg-gray-900 rounded-xl overflow-hidden border border-gray-800 shadow-md">
                        {slide.image?.url && (
                          <div className="w-full bg-gray-800/50 relative flex justify-center border-b border-gray-800/50 group">
                            <img src={slide.image.url} alt={`اسلاید ${slide.index}`} className="max-h-96 w-auto object-contain" />
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <a 
                                href={slide.image.url} 
                                download={`slide-${slide.index || idx + 1}.png`}
                                target="_blank"
                                rel="noreferrer"
                                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 transition-colors shadow-lg"
                              >
                                <span>⬇️</span> دانلود عکس
                              </a>
                            </div>
                          </div>
                        )}
                        <div className="p-6">
                          <div className="flex items-center gap-3 mb-4">
                            <span className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-sm">
                              {slide.index || idx + 1}
                            </span>
                            <h4 className="text-lg font-bold text-white">{slide.title || `اسلاید ${slide.index || idx + 1}`}</h4>
                          </div>
                          <div className="text-gray-300 whitespace-pre-wrap leading-relaxed text-sm">
                            {slide.text}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                {selectedOutput.metadata?.media && selectedOutput.metadata.media.length > 0 && (
                  <div className="mt-8 grid grid-cols-2 gap-4 border-t border-gray-800 pt-6">
                    {selectedOutput.metadata.media.map((m, idx) => (
                      <div key={idx} className="bg-gray-900 rounded-xl overflow-hidden border border-gray-800 shadow-md">
                        {m.url ? (
                          <div className="relative group w-full h-full flex">
                            <img src={m.url} alt="Generated Media" className="w-full h-auto object-cover" />
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <a 
                                href={m.url} 
                                download={`media-${idx + 1}.png`}
                                target="_blank"
                                rel="noreferrer"
                                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 transition-colors shadow-lg"
                              >
                                <span>⬇️</span> دانلود
                              </a>
                            </div>
                          </div>
                        ) : (
                          <div className="p-4 flex items-center justify-center h-32 bg-gray-800/50">
                            <p className="text-xs text-gray-500 break-all text-center">{m.storage_path}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
