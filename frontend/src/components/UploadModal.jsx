import React, { useState, useRef } from 'react';
import { Upload, X, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export default function UploadModal({ isOpen, onClose, onUploadSuccess, token }) {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const inputRef = useRef(null);

  if (!isOpen) return null;

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    setError(null);
    setSuccess(false);

    if (!selectedFile) return;

    if (selectedFile.type !== "application/pdf") {
      setError("Unsupported file format. Only standard PDF files are supported.");
      return;
    }

    if (selectedFile.size > 15 * 1024 * 1024) {
      setError("File is too large. Maximum allowed size is 15MB.");
      return;
    }

    setFile(selectedFile);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const onButtonClick = () => {
    inputRef.current.click();
  };

  const handleUploadSubmit = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);
    setProgress(20);

    const formData = new FormData();
    formData.append("file", file);

    try {
      setProgress(50);
      const response = await fetch("http://localhost:8000/api/v1/documents/upload", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData
      });

      setProgress(85);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "PDF ingestion failed.");
      }

      const result = await response.json();
      setProgress(100);
      setSuccess(true);
      setFile(null);
      
      // Notify parent to reload list
      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
      
      setTimeout(() => {
        onClose();
        setSuccess(false);
      }, 1500);

    } catch (err) {
      console.error(err);
      setError(err.message || "An error occurred while uploading. Please check backend connectivity.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 p-4 bg-background/80 backdrop-blur-sm transition-opacity duration-300">
      <div className="w-full max-w-md relative rounded-2xl glass-panel p-6 shadow-2xl animate-in fade-in zoom-in duration-200">
        
        {/* Header bar */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Upload Knowledge Document</h3>
            <p className="text-xs text-gray-400">Add documents to your RAG vector database memory</p>
          </div>
          <button 
            onClick={onClose} 
            disabled={loading}
            className="p-1 hover:bg-border/40 rounded-full transition-colors text-gray-400 hover:text-foreground"
          >
            <X size={18} />
          </button>
        </div>

        {/* Drag-and-drop zone */}
        {!success && (
          <div 
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`w-full min-h-[180px] rounded-xl border border-dashed flex flex-col justify-center items-center p-6 text-center transition-all ${
              dragActive 
                ? "border-primary bg-primary/5 text-primary scale-[0.98]" 
                : file 
                  ? "border-primary/50 bg-primary/5" 
                  : "border-border hover:border-gray-500 bg-background/30"
            }`}
          >
            <input 
              ref={inputRef}
              type="file"
              accept=".pdf"
              onChange={handleChange}
              className="hidden"
            />

            {file ? (
              <div className="flex flex-col items-center animate-in fade-in duration-300">
                <FileText size={44} className="text-primary mb-3 animate-bounce" />
                <span className="text-sm font-medium text-foreground max-w-[280px] truncate">{file.name}</span>
                <span className="text-xs text-gray-400 mt-1">{(file.size / (1024*1024)).toFixed(2)} MB</span>
                <button 
                  onClick={() => setFile(null)} 
                  disabled={loading}
                  className="text-xs text-red-400 hover:text-red-500 font-medium underline mt-3 transition-colors"
                >
                  Remove file
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <Upload size={40} className="text-gray-400 mb-3" />
                <span className="text-sm text-foreground font-medium">Drag and drop your PDF here</span>
                <span className="text-xs text-gray-400 mt-1 mb-4">Supported formats: PDF (max 15MB)</span>
                <button 
                  onClick={onButtonClick}
                  className="px-4 py-1.5 bg-border/40 hover:bg-border/60 border border-border text-foreground text-xs font-semibold rounded-lg transition-all"
                >
                  Browse Files
                </button>
              </div>
            )}
          </div>
        )}

        {/* Success animation block */}
        {success && (
          <div className="w-full py-8 flex flex-col items-center justify-center text-center animate-in fade-in duration-300">
            <CheckCircle2 size={54} className="text-primary mb-3 animate-pulse" />
            <h4 className="text-base font-semibold text-foreground">Ingestion Completed!</h4>
            <p className="text-xs text-gray-400 mt-1">Document parsed, split, and fully embedded.</p>
          </div>
        )}

        {/* Loading progress bar */}
        {loading && (
          <div className="mt-4 space-y-2 animate-in fade-in duration-200">
            <div className="flex justify-between items-center text-xs">
              <span className="flex items-center gap-1.5 text-gray-400">
                <Loader2 size={12} className="animate-spin text-primary" />
                Processing PDF pages...
              </span>
              <span className="font-semibold text-foreground">{progress}%</span>
            </div>
            <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
              <div 
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error panel */}
        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 text-red-200 text-xs rounded-lg flex items-start gap-2 animate-in slide-in-from-top-2 duration-300">
            <AlertCircle size={14} className="text-red-400 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Footer actions */}
        {!success && (
          <div className="flex justify-end gap-3 mt-6 border-t border-border pt-4">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 bg-transparent hover:bg-border/20 border border-border text-foreground text-xs font-semibold rounded-lg transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleUploadSubmit}
              disabled={!file || loading}
              className="px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-bold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-primary/20 flex items-center gap-1.5"
            >
              {loading && <Loader2 size={12} className="animate-spin" />}
              Upload & Index
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
