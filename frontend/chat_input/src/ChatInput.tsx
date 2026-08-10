import React, { useCallback, useEffect, useRef, useState } from "react";
import { Streamlit } from "streamlit-component-lib";
import "./style.css";

type AttachmentPayload = { name: string; type: string; size: number; data: string; };
type ChatEvent = { type: "send" | "audio"; event_id: string; text?: string; files?: AttachmentPayload[]; audio?: string; audio_type?: string; audio_name?: string; };
type ExtendedFile = { file: File; id: string; previewUrl?: string; };

const MAX_FILE_SIZE = 20 * 1024 * 1024;
const MAX_FILES = 10;

function generateEventId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") { reject(new Error("Falha ao converter arquivo.")); return; }
      resolve(result.split(",")[1] || result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Erro de IO."));
    reader.readAsDataURL(file);
  });
}

function isImage(file: File): boolean { return file.type.startsWith("image/"); }
function getFileIcon(file: File): string {
  if (file.type === "application/pdf") return "ðŸ“„";
  if (isImage(file)) return "ðŸ–¼ï¸";
  if (file.type.includes("spreadsheet") || file.name.endsWith(".xlsx") || file.name.endsWith(".csv")) return "ðŸ“Š";
  return "ðŸ“Ž";
}
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ChatInput() {
  // Inicializa oficialmente o iframe como componente Streamlit.
  React.useEffect(() => {
    Streamlit.setComponentReady();
    Streamlit.setFrameHeight();
  }, []);

  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<ExtendedFile[]>([]);
  const [recording, setRecording] = useState(false);
  const [processingAudio, setProcessingAudio] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Sync Streamlit Height
  const updateFrameHeight = useCallback(() => {
    if (containerRef.current) {
      Streamlit.setFrameHeight(containerRef.current.scrollHeight + 10);
    }
  }, []);

  useEffect(() => {
    updateFrameHeight();
    const observer = new ResizeObserver(() => updateFrameHeight());
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [updateFrameHeight, text, attachments, error]);

  // Cleanup Object URLs on unmount to prevent memory leaks
  useEffect(() => {
    return () => { attachments.forEach(a => { if (a.previewUrl) URL.revokeObjectURL(a.previewUrl); }); };
  }, [attachments]);

  const emit = useCallback((event: ChatEvent) => { Streamlit.setComponentValue(event); }, []);

  const handleFileSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const selected = Array.from(event.target.files ?? []);
    if (!selected.length) return;

    if (attachments.length + selected.length > MAX_FILES) {
      setError(`MÃ¡ximo de ${MAX_FILES} arquivos permitido.`);
      event.target.value = "";
      return;
    }

    const oversized = selected.find(f => f.size > MAX_FILE_SIZE);
    if (oversized) {
      setError(`Arquivo "${oversized.name}" excede 20MB.`);
      event.target.value = "";
      return;
    }

    const newExtFiles: ExtendedFile[] = selected.map(file => ({
      file, id: generateEventId(), previewUrl: isImage(file) ? URL.createObjectURL(file) : undefined
    }));
    
    setAttachments(prev => [...prev, ...newExtFiles]);
    event.target.value = "";
  };

  const removeAttachment = (id: string) => {
    setAttachments(prev => {
      const item = prev.find(a => a.id === id);
      if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
      return prev.filter(a => a.id !== id);
    });
  };

  const sendMessage = async () => {
    const trimmedText = text.trim();
    if (!trimmedText && attachments.length === 0) return;
    try {
      setError(null);
      const encodedFiles: AttachmentPayload[] = await Promise.all(
        attachments.map(async (a) => ({
          name: a.file.name, type: a.file.type, size: a.file.size, data: await fileToBase64(a.file),
        }))
      );
      emit({ type: "send", event_id: generateEventId(), text: trimmedText, files: encodedFiles });
      setText("");
      // Limpeza segura dos previews antes de resetar o array
      attachments.forEach(a => { if (a.previewUrl) URL.revokeObjectURL(a.previewUrl); });
      setAttachments([]);
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    } catch (err) {
      setError("Erro de IO ao preparar pacote.");
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  const startRecording = async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      mediaStreamRef.current = stream;
      
      let mimeType = "audio/webm";
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) mimeType = "audio/webm;codecs=opus";
      else if (MediaRecorder.isTypeSupported("audio/mp4")) mimeType = "audio/mp4";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        try {
          setProcessingAudio(true);
          const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || mimeType });
          const base64 = await fileToBase64(new File([blob], "audio.webm", { type: blob.type }));
          emit({ type: "audio", event_id: generateEventId(), audio: base64, audio_type: blob.type, audio_name: "audio.webm" });
        } catch (err) { setError("Falha ao codificar Ã¡udio."); } 
        finally {
          setProcessingAudio(false);
          audioChunksRef.current = [];
          stream.getTracks().forEach(t => t.stop());
          mediaStreamRef.current = null;
          mediaRecorderRef.current = null;
        }
      };
      recorder.start();
      setRecording(true);
    } catch (err) {
      setError("Microfone negado ou indisponÃ­vel.");
      setRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  };

  return (
    <div className="chat-wrapper" ref={containerRef}>
      {error && (
        <div className="chat-error">
          <span>{error}</span><button onClick={() => setError(null)}>Ã—</button>
        </div>
      )}
      
      {attachments.length > 0 && (
        <div className="attachments">
          {attachments.map((a) => (
            <div className="attachment" key={a.id}>
              {a.previewUrl ? (
                <div className="attachment-thumbnail"><img src={a.previewUrl} alt="" /></div>
              ) : (
                <span className="attachment-icon">{getFileIcon(a.file)}</span>
              )}
              <div className="attachment-info">
                <span className="attachment-name">{a.file.name}</span>
                <span className="attachment-size">{formatFileSize(a.file.size)}</span>
              </div>
              <button className="attachment-remove" onClick={() => removeAttachment(a.id)}>Ã—</button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-bar">
        <button className="icon-button" onClick={() => fileInputRef.current?.click()} type="button" aria-label="Anexar arquivo" disabled={recording || processingAudio}>
          <svg viewBox="0 0 24 24"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" /></svg>
        </button>
        <input ref={fileInputRef} className="hidden-file-input" type="file" multiple onChange={handleFileSelection} />
        
        <textarea ref={textareaRef} className="chat-textarea" value={text} onChange={handleInput} onKeyDown={handleKeyDown} placeholder={recording ? "Gravando Ã¡udio..." : processingAudio ? "Processando..." : "Mensagem para ROG AI..."} rows={1} disabled={recording || processingAudio} />
        
        <button className={`icon-button microphone-button ${recording ? "recording" : ""}`} onClick={recording ? stopRecording : startRecording} type="button" disabled={processingAudio}>
          {recording ? (
            <span className="recording-indicator"><span/><span/><span/></span>
          ) : (
            <svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 003-3V6a3 3 0 00-6 0v5a3 3 0 003 3z"/><path d="M19 11a7 7 0 01-14 0"/><path d="M12 18v4"/><path d="M8 22h8"/></svg>
          )}
        </button>
        
        <button className="send-button" onClick={() => void sendMessage()} disabled={recording || processingAudio || (!text.trim() && attachments.length === 0)} type="button">
          <svg viewBox="0 0 24 24"><path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4 20-7z" /></svg>
        </button>
      </div>
    </div>
  );
}