import { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { getProjects, createProject, deleteProject } from '../src/lib/api';

export default function Dashboard() {
  const router = useRouter();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const data = await getProjects();
      setProjects(data.projects || []);
    } catch (err) {
      console.error("Failed to load projects:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    
    try {
      setIsCreating(true);
      const proj = await createProject(newProjectName.trim(), newProjectDesc.trim());
      setShowCreateModal(false);
      setNewProjectName('');
      setNewProjectDesc('');
      router.push(`/project/${proj.id}`);
    } catch (err) {
      alert("خطا در ساخت پروژه: " + err.message);
      setIsCreating(false);
    }
  };

  const handleDeleteProject = async (e, id) => {
    e.stopPropagation();
    if (confirm("آیا از حذف این پروژه اطمینان دارید؟")) {
      try {
        await deleteProject(id);
        fetchProjects();
      } catch (err) {
        alert("خطا در حذف پروژه: " + err.message);
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-gray-100 p-8" dir="rtl" style={{ fontFamily: 'system-ui, sans-serif' }}>
      <Head>
        <title>داشبورد مدیریت تولید محتوا</title>
      </Head>

      <div className="max-w-5xl mx-auto">
        <header className="flex justify-between items-center mb-10 pb-6 border-b border-gray-800">
          <div>
            <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">
              پروژه‌های من
            </h1>
            <p className="text-sm text-gray-400 mt-2">مدیریت فضاهای کاری تولید محتوا</p>
          </div>
          
          <div className="flex items-center gap-4">
            <Link 
              href="/settings/youtube"
              className="bg-gray-800 hover:bg-gray-700 text-gray-300 px-5 py-3 rounded-xl font-medium transition-colors flex items-center gap-2 border border-gray-700"
            >
              ⚙️ تنظیمات یوتیوب
            </Link>
            <button 
              onClick={() => setShowCreateModal(true)}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-indigo-500/20 flex items-center gap-2"
            >
              <span className="text-xl">+</span> پروژه جدید
            </button>
          </div>
        </header>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20 bg-gray-900/50 rounded-2xl border border-gray-800 border-dashed">
            <p className="text-gray-400 mb-6 text-lg">هنوز پروژه‌ای نساخته‌اید.</p>
            <button 
              onClick={() => setShowCreateModal(true)}
              className="text-indigo-400 hover:text-indigo-300 font-medium"
            >
              اولین پروژه خود را بسازید
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map(proj => (
              <div 
                key={proj.id} 
                onClick={() => router.push(`/project/${proj.id}`)}
                className="bg-gray-800/40 hover:bg-gray-800 border border-gray-700/50 hover:border-indigo-500/30 rounded-2xl p-6 cursor-pointer transition-all hover:shadow-xl hover:shadow-indigo-500/5 group"
              >
                <div className="flex justify-between items-start mb-4">
                  <h2 className="text-xl font-semibold text-gray-100 group-hover:text-indigo-400 transition-colors">
                    {proj.name}
                  </h2>
                  <button 
                    onClick={(e) => handleDeleteProject(e, proj.id)}
                    className="text-gray-500 hover:text-red-400 p-2 -mr-2 rounded-lg hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                    title="حذف پروژه"
                  >
                    🗑️
                  </button>
                </div>
                
                {proj.description && (
                  <p className="text-gray-400 text-sm mb-6 line-clamp-2">{proj.description}</p>
                )}
                
                <div className="flex items-center justify-between text-xs text-gray-500 mt-auto pt-4 border-t border-gray-700/50">
                  <span>آخرین تغییر: {new Date(proj.updated_at).toLocaleDateString('fa-IR', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                  <span className={`px-2 py-1 rounded-full ${proj.status === 'processing' ? 'bg-amber-500/10 text-amber-400' : 'bg-emerald-500/10 text-emerald-400'}`}>
                    {proj.status === 'processing' ? 'در حال پردازش' : 'آماده'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md shadow-2xl p-6" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6 pb-4 border-b border-gray-800">
              <h2 className="text-xl font-bold">پروژه جدید</h2>
              <button 
                onClick={() => setShowCreateModal(false)}
                className="text-gray-500 hover:text-gray-300 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-800"
              >
                ✕
              </button>
            </div>
            
            <form onSubmit={handleCreateProject}>
              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">نام پروژه <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={e => setNewProjectName(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
                    placeholder="مثال: کمپین یلدا"
                    required
                    autoFocus
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">توضیحات (اختیاری)</label>
                  <textarea
                    value={newProjectDesc}
                    onChange={e => setNewProjectDesc(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors resize-none h-24"
                    placeholder="توضیحات کوتاه درباره این پروژه..."
                  />
                </div>
              </div>
              
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-5 py-2.5 rounded-xl font-medium text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
                  disabled={isCreating}
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-6 py-2.5 rounded-xl font-medium transition-colors flex items-center gap-2"
                  disabled={!newProjectName.trim() || isCreating}
                >
                  {isCreating ? 'در حال ساخت...' : 'ساخت پروژه'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
