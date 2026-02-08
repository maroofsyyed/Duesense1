import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { uploadDeck, getDeckStatus } from '../api';
import { Upload as UploadIcon, FileText, CheckCircle, Loader2, AlertCircle, ArrowRight, Zap } from 'lucide-react';

const STAGES = [
  { key: 'uploading', label: 'Uploading', icon: UploadIcon },
  { key: 'extracting', label: 'Extracting Data', icon: FileText },
  { key: 'enriching', label: 'Enriching from Sources', icon: Zap },
  { key: 'scoring', label: 'AI Scoring', icon: Zap },
  { key: 'generating_memo', label: 'Generating Memo', icon: FileText },
  { key: 'completed', label: 'Analysis Complete', icon: CheckCircle },
];

export default function Upload() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [companyWebsite, setCompanyWebsite] = useState('');
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [currentStatus, setCurrentStatus] = useState(null);
  const [companyId, setCompanyId] = useState(null);
  const [error, setError] = useState(null);

  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'application/vnd.ms-powerpoint': ['.ppt'],
    },
    maxFiles: 1,
    maxSize: 25 * 1024 * 1024,
  });

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);

    try {
      const res = await uploadDeck(file, companyWebsite);
      const { deck_id, company_id } = res.data;
      setCompanyId(company_id);
      setUploading(false);
      setProcessing(true);
      setCurrentStatus('uploading');

      // Poll for status
      const poll = setInterval(async () => {
        try {
          const statusRes = await getDeckStatus(deck_id);
          const status = statusRes.data.processing_status;
          setCurrentStatus(status);

          if (status === 'completed') {
            clearInterval(poll);
            setProcessing(false);
          } else if (status === 'failed') {
            clearInterval(poll);
            setProcessing(false);
            setError(statusRes.data.error_message || 'Processing failed');
          }
        } catch (e) {
          // Keep polling
        }
      }, 3000);
    } catch (e) {
      setUploading(false);
      setError(e.response?.data?.detail || 'Upload failed');
    }
  };

  const getStageIndex = () => STAGES.findIndex(s => s.key === currentStatus);

  return (
    <div className="p-6 lg:p-8 max-w-[900px] mx-auto" data-testid="upload-page">
      <div className="mb-8">
        <h1 className="font-heading font-black text-3xl text-text-primary tracking-tight">Upload Pitch Deck</h1>
        <p className="text-text-secondary text-sm mt-1">Upload a PDF or PPTX to start AI-powered due diligence</p>
      </div>

      {!processing && currentStatus !== 'completed' && (
        <>
          {/* Dropzone */}
          <div
            {...getRootProps()}
            data-testid="dropzone"
            className={`border-2 border-dashed rounded-sm p-12 text-center cursor-pointer transition-all duration-300 ${
              isDragActive
                ? 'border-primary bg-primary/5'
                : file
                ? 'border-success/50 bg-success/5'
                : 'border-border hover:border-primary/40 hover:bg-surface'
            }`}
          >
            <input {...getInputProps()} data-testid="file-input" />
            {file ? (
              <div className="animate-fade-in">
                <FileText size={48} className="mx-auto text-success mb-4" />
                <p className="text-text-primary font-medium">{file.name}</p>
                <p className="text-text-muted text-sm mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            ) : (
              <div>
                <UploadIcon size={48} className="mx-auto text-text-muted mb-4" />
                <p className="text-text-primary font-medium">
                  {isDragActive ? 'Drop your pitch deck here' : 'Drag & drop your pitch deck'}
                </p>
                <p className="text-text-muted text-sm mt-2">Supports PDF and PPTX up to 25MB</p>
              </div>
            )}
          </div>

          {/* Upload Button */}
          {file && (
            <button
              onClick={handleUpload}
              disabled={uploading}
              data-testid="upload-btn"
              className="mt-6 w-full flex items-center justify-center gap-2 px-6 py-3 bg-primary text-white rounded-sm font-medium hover:bg-primary-hover transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {uploading ? (
                <>
                  <Loader2 size={18} className="animate-spin" /> Uploading...
                </>
              ) : (
                <>
                  <Zap size={18} /> Analyze with AI
                </>
              )}
            </button>
          )}
        </>
      )}

      {/* Processing Pipeline */}
      {(processing || currentStatus === 'completed') && (
        <div className="bg-surface border border-border rounded-sm p-8 animate-fade-in" data-testid="processing-pipeline">
          <h3 className="font-heading font-bold text-xl text-text-primary mb-6">Analysis Pipeline</h3>
          <div className="space-y-4">
            {STAGES.map((stage, i) => {
              const stageIdx = getStageIndex();
              const isActive = stage.key === currentStatus;
              const isDone = stageIdx > i || currentStatus === 'completed';
              const Icon = stage.icon;

              return (
                <div
                  key={stage.key}
                  data-testid={`stage-${stage.key}`}
                  className={`flex items-center gap-4 p-3 rounded-sm border transition-all duration-300 ${
                    isActive
                      ? 'border-primary bg-primary/5'
                      : isDone
                      ? 'border-success/20 bg-success/5'
                      : 'border-border opacity-40'
                  }`}
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    isDone ? 'bg-success' : isActive ? 'bg-primary pulse-glow' : 'bg-surface-hl'
                  }`}>
                    {isDone ? (
                      <CheckCircle size={16} className="text-white" />
                    ) : isActive ? (
                      <Loader2 size={16} className="text-white animate-spin" />
                    ) : (
                      <Icon size={16} className="text-text-muted" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className={`text-sm font-medium ${isDone ? 'text-success' : isActive ? 'text-primary' : 'text-text-muted'}`}>
                      {stage.label}
                    </div>
                  </div>
                  {isDone && <span className="text-[10px] text-success font-mono uppercase">Done</span>}
                  {isActive && <span className="text-[10px] text-primary font-mono uppercase">In Progress</span>}
                </div>
              );
            })}
          </div>

          {currentStatus === 'completed' && companyId && (
            <button
              onClick={() => navigate(`/companies/${companyId}`)}
              data-testid="view-analysis-btn"
              className="mt-6 w-full flex items-center justify-center gap-2 px-6 py-3 bg-primary text-white rounded-sm font-medium hover:bg-primary-hover transition-all active:scale-[0.98]"
            >
              View Full Analysis <ArrowRight size={18} />
            </button>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-6 bg-destructive/10 border border-destructive/20 rounded-sm p-4 flex items-start gap-3" data-testid="upload-error">
          <AlertCircle size={18} className="text-destructive mt-0.5" />
          <div>
            <p className="text-destructive text-sm font-medium">Analysis Failed</p>
            <p className="text-text-muted text-xs mt-1">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
