import { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { uploadYoutubeCookies, testYoutubeCookies } from '../../src/lib/api';

export default function YoutubeSettings() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState('Not configured'); // 'Not configured', 'Testing', 'Active', 'Failed'
  const [testResult, setTestResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      alert("لطفاً یک فایل انتخاب کنید.");
      return;
    }
    
    try {
      setUploading(true);
      setErrorMsg('');
      await uploadYoutubeCookies(file);
      
      // Auto trigger test
      handleTest();
    } catch (err) {
      setErrorMsg("خطا در آپلود: " + err.message);
      setStatus('Failed');
    } finally {
      setUploading(false);
    }
  };

  const handleTest = async () => {
    try {
      setTesting(true);
      setStatus('Testing');
      setErrorMsg('');
      setTestResult(null);
      
      const result = await testYoutubeCookies();
      setTestResult(result);
      
      if (result.success) {
        setStatus('Active');
      } else {
        setStatus('Failed');
        setErrorMsg(result.message || "Cookie expired or invalid");
      }
    } catch (err) {
      setErrorMsg("خطا در تست: " + err.message);
      setStatus('Failed');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-gray-100 p-8" dir="rtl" style={{ fontFamily: 'system-ui, sans-serif' }}>
      <Head>
        <title>تنظیمات یوتیوب - داشبورد</title>
      </Head>

      <div className="max-w-3xl mx-auto">
        <header className="flex justify-between items-center mb-10 pb-6 border-b border-gray-800">
          <div>
            <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-pink-500">
              تنظیمات یوتیوب
            </h1>
            <p className="text-sm text-gray-400 mt-2">مدیریت کوکی‌ها برای دور زدن محدودیت‌های ربات یوتیوب</p>
          </div>
          
          <Link href="/" className="text-gray-400 hover:text-white transition-colors flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg">
            <span>&larr;</span> بازگشت به داشبورد
          </Link>
        </header>

        <div className="bg-gray-900/50 border border-gray-800 rounded-2xl p-8 shadow-xl">
          <div className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-white">آپلود فایل کوکی (youtube_cookies.txt)</h2>
            <p className="text-gray-400 text-sm mb-6 leading-relaxed">
              برای جلوگیری از خطای "Sign in to confirm you're not a bot" باید کوکی‌های مرورگر خود را استخراج کرده و اینجا آپلود کنید.
              پیشنهاد می‌شود از افزونه‌های مرورگر مانند Get cookies.txt LOCALLY استفاده کنید.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
              <input 
                type="file" 
                accept=".txt"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-400
                  file:mr-4 file:py-2.5 file:px-4
                  file:rounded-lg file:border-0
                  file:text-sm file:font-semibold
                  file:bg-indigo-600 file:text-white
                  hover:file:bg-indigo-500 file:cursor-pointer
                  bg-gray-800 border border-gray-700 rounded-lg cursor-pointer"
              />
              <button 
                onClick={handleUpload}
                disabled={!file || uploading || testing}
                className={`px-6 py-2.5 rounded-lg font-medium transition-all min-w-[120px] shadow-lg
                  ${!file || uploading || testing 
                    ? 'bg-gray-700 text-gray-500 cursor-not-allowed shadow-none' 
                    : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/20'}`}
              >
                {uploading ? 'در حال آپلود...' : 'آپلود کوکی'}
              </button>
            </div>
          </div>

          <div className="pt-8 border-t border-gray-800">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-white">وضعیت فعلی</h2>
              <div className="flex items-center gap-4">
                <span className={`px-3 py-1 text-sm rounded-full font-medium border
                  ${status === 'Not configured' ? 'bg-gray-800 text-gray-400 border-gray-700' : ''}
                  ${status === 'Testing' ? 'bg-blue-900/30 text-blue-400 border-blue-800/50 animate-pulse' : ''}
                  ${status === 'Active' ? 'bg-green-900/30 text-green-400 border-green-800/50' : ''}
                  ${status === 'Failed' ? 'bg-red-900/30 text-red-400 border-red-800/50' : ''}
                `}>
                  {status === 'Not configured' && 'پیکربندی نشده'}
                  {status === 'Testing' && 'در حال تست...'}
                  {status === 'Active' && 'فعال'}
                  {status === 'Failed' && 'نامعتبر / منقضی'}
                </span>
                
                <button 
                  onClick={handleTest}
                  disabled={testing || uploading}
                  className="text-indigo-400 hover:text-indigo-300 transition-colors text-sm font-medium disabled:opacity-50"
                >
                  تست مجدد
                </button>
              </div>
            </div>

            {testResult && (
              <div className={`p-4 rounded-xl mb-4 border ${testResult.success ? 'bg-green-900/10 border-green-900/30' : 'bg-red-900/10 border-red-900/30'}`}>
                <div className="flex items-start gap-3">
                  <div className={`text-xl mt-0.5 ${testResult.success ? 'text-green-500' : 'text-red-500'}`}>
                    {testResult.success ? '✅' : '❌'}
                  </div>
                  <div>
                    <h4 className={`font-medium ${testResult.success ? 'text-green-400' : 'text-red-400'}`}>
                      {testResult.success ? 'YouTube connection successful' : 'Cookie expired or invalid'}
                    </h4>
                    {testResult.message && <p className="text-sm text-gray-300 mt-1">{testResult.message}</p>}
                    {!testResult.success && testResult.details && (
                      <pre className="mt-3 p-3 bg-gray-900 rounded-lg text-xs text-red-300 overflow-x-auto whitespace-pre-wrap font-mono border border-gray-800">
                        {testResult.details}
                      </pre>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            {errorMsg && !testResult && (
              <div className="p-4 rounded-xl mb-4 border bg-red-900/10 border-red-900/30">
                <div className="flex items-start gap-3">
                  <div className="text-xl mt-0.5 text-red-500">❌</div>
                  <div>
                    <h4 className="font-medium text-red-400">خطا</h4>
                    <p className="text-sm text-gray-300 mt-1">{errorMsg}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
