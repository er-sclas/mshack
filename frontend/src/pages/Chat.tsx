/**
 * Chat Page Component
 *
 * AI-powered chat interface for analyzing traffic simulations.
 * Features:
 * - Text and voice input
 * - Voice output toggle
 * - Run context selection for data-aware responses
 * - Markdown rendering for responses
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { clsx } from 'clsx';
import {
  PaperAirplaneIcon,
  MicrophoneIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  StopIcon,
  SparklesIcon,
  ChartBarIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import {
  sendChatMessage,
  transcribeAudio,
  textToSpeech,
  analyzeRun,
  listRuns,
  type ChatMessage,
} from '../utils/api';

interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
  isLoading?: boolean;
}

interface Run {
  id: string;
  scenarioId: string;
  status: string;
  summary?: {
    avgSpeed: number;
    avgDelay: number;
    adaptiveControl: boolean;
  };
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [isPlaying, setIsPlaying] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Load available runs
  useEffect(() => {
    listRuns({ status: 'completed', limit: 20 })
      .then((data) => setRuns(data.runs || []))
      .catch(console.error);
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Add welcome message on mount
  useEffect(() => {
    const welcomeMessage: Message = {
      id: 'welcome',
      role: 'assistant',
      content: `Hello! I'm your AI traffic analyst for FlowState.

I can help you:
- **Analyze simulation results** and explain the data visualizations
- **Compare ML adaptive control** vs fixed timing performance
- **Explain traffic patterns** and congestion hotspots
- **Provide insights** on how to improve traffic flow

${runs.length > 0 ? 'Select a simulation run from the dropdown above to give me context about specific data, or just ask me anything about traffic management!' : 'Once you run some simulations, I can analyze them for you!'}`,
      timestamp: new Date(),
    };
    setMessages([welcomeMessage]);
  }, [runs.length]);

  const playAudio = useCallback(async (text: string) => {
    if (!voiceEnabled) return;

    try {
      setIsPlaying(true);
      const { audio, format } = await textToSpeech(text);

      // Create audio from base64
      const audioData = atob(audio);
      const audioArray = new Uint8Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        audioArray[i] = audioData.charCodeAt(i);
      }
      const audioBlob = new Blob([audioArray], { type: `audio/${format}` });
      const audioUrl = URL.createObjectURL(audioBlob);

      if (audioRef.current) {
        audioRef.current.pause();
      }

      audioRef.current = new Audio(audioUrl);
      audioRef.current.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };
      audioRef.current.onerror = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };
      await audioRef.current.play();
    } catch (error) {
      console.error('Error playing audio:', error);
      setIsPlaying(false);
    }
  }, [voiceEnabled]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    };

    const loadingMessage: Message = {
      id: `loading-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Build conversation history (exclude loading and welcome messages)
      const history = messages
        .filter((m) => !m.isLoading && m.id !== 'welcome')
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await sendChatMessage({
        message: text.trim(),
        runId: selectedRunId || undefined,
        conversationHistory: history,
        includeVoice: voiceEnabled,
      });

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
      };

      setMessages((prev) =>
        prev.map((m) => (m.isLoading ? assistantMessage : m))
      );

      // Play audio if voice enabled
      if (voiceEnabled) {
        playAudio(response.response);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) =>
        prev.map((m) =>
          m.isLoading
            ? {
                ...m,
                isLoading: false,
                content: 'Sorry, I encountered an error. Please try again.',
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      // Check if mediaDevices is available (requires HTTPS or localhost)
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert('Voice recording requires HTTPS. The site is served over HTTP which blocks microphone access. Please use the text input instead.');
        return;
      }

      // Request microphone with specific constraints for better quality
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        }
      });

      // Try different MIME types in order of preference
      const mimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
        ''
      ];

      let mimeType = '';
      for (const type of mimeTypes) {
        if (type === '' || MediaRecorder.isTypeSupported(type)) {
          mimeType = type;
          break;
        }
      }

      console.log('Using MIME type:', mimeType || 'browser default');

      const options: MediaRecorderOptions = mimeType ? { mimeType } : {};
      mediaRecorderRef.current = new MediaRecorder(stream, options);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        console.log('Audio chunk received:', event.data.size, 'bytes');
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        const actualMimeType = mediaRecorderRef.current?.mimeType || 'audio/webm';
        console.log('Recording stopped. MIME type:', actualMimeType);
        console.log('Total chunks:', audioChunksRef.current.length);

        const audioBlob = new Blob(audioChunksRef.current, { type: actualMimeType });
        stream.getTracks().forEach((track) => track.stop());

        console.log('Audio blob size:', audioBlob.size, 'bytes');

        // Check if we got any audio data
        if (audioBlob.size < 1000) {
          console.error('Recording too short or empty:', audioBlob.size);
          alert('Recording too short. Please hold the button longer while speaking.');
          return;
        }

        try {
          setIsLoading(true);
          console.log('Sending audio for transcription...');
          const result = await transcribeAudio(audioBlob);
          console.log('Transcription result:', result);

          const text = result.text;
          if (text && text.trim() && text.trim() !== '.' && !text.startsWith('Error')) {
            setInput(text);
            // Auto-send after transcription
            sendMessage(text);
          } else if (text === '.' || text.trim() === '') {
            alert('No speech detected. Please speak clearly and try again.');
          } else {
            console.error('Transcription failed:', text);
            alert('Transcription failed: ' + text);
          }
        } catch (error) {
          console.error('Transcription error:', error);
          alert('Failed to transcribe audio. Please try again.');
        } finally {
          setIsLoading(false);
        }
      };

      mediaRecorderRef.current.start(250); // Collect data every 250ms
      setIsRecording(true);
      console.log('Recording started');
    } catch (error) {
      console.error('Error starting recording:', error);
      alert('Could not access microphone. Please check permissions and try again.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleAnalyzeRun = async () => {
    if (!selectedRunId || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: `Please analyze simulation run ${selectedRunId} and explain the results.`,
      timestamp: new Date(),
    };

    const loadingMessage: Message = {
      id: `loading-${Date.now()}`,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setIsLoading(true);

    try {
      const { analysis } = await analyzeRun(selectedRunId);

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: analysis,
        timestamp: new Date(),
      };

      setMessages((prev) =>
        prev.map((m) => (m.isLoading ? assistantMessage : m))
      );

      if (voiceEnabled) {
        playAudio(analysis);
      }
    } catch (error) {
      console.error('Error analyzing run:', error);
      setMessages((prev) =>
        prev.map((m) =>
          m.isLoading
            ? {
                ...m,
                isLoading: false,
                content: 'Sorry, I could not analyze this run. Please try again.',
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsPlaying(false);
  };

  // Simple markdown rendering
  const renderMarkdown = (text: string) => {
    return text
      .split('\n')
      .map((line, i) => {
        // Headers
        if (line.startsWith('### ')) {
          return (
            <h3 key={i} className="text-lg font-semibold mt-4 mb-2 text-gray-900 dark:text-white">
              {line.slice(4)}
            </h3>
          );
        }
        if (line.startsWith('## ')) {
          return (
            <h2 key={i} className="text-xl font-bold mt-4 mb-2 text-gray-900 dark:text-white">
              {line.slice(3)}
            </h2>
          );
        }
        if (line.startsWith('# ')) {
          return (
            <h1 key={i} className="text-2xl font-bold mt-4 mb-2 text-gray-900 dark:text-white">
              {line.slice(2)}
            </h1>
          );
        }
        // Bullet points
        if (line.startsWith('- ') || line.startsWith('* ')) {
          const content = line.slice(2);
          return (
            <li key={i} className="ml-4 list-disc">
              {renderInlineMarkdown(content)}
            </li>
          );
        }
        // Numbered lists
        const numberedMatch = line.match(/^(\d+)\.\s(.+)/);
        if (numberedMatch) {
          return (
            <li key={i} className="ml-4 list-decimal">
              {renderInlineMarkdown(numberedMatch[2])}
            </li>
          );
        }
        // Empty lines
        if (!line.trim()) {
          return <br key={i} />;
        }
        // Regular paragraphs
        return (
          <p key={i} className="mb-2">
            {renderInlineMarkdown(line)}
          </p>
        );
      });
  };

  const renderInlineMarkdown = (text: string) => {
    // Bold
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} className="font-semibold">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="card p-4 mb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <SparklesIcon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                FlowState AI
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Powered by GPT-OSS 120B
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Run Selector */}
            <select
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
              className="input text-sm py-1.5 w-48"
            >
              <option value="">No run selected</option>
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.id} - {run.status}
                </option>
              ))}
            </select>

            {/* Analyze Button */}
            {selectedRunId && (
              <button
                onClick={handleAnalyzeRun}
                disabled={isLoading}
                className="btn-secondary flex items-center gap-2 text-sm py-1.5"
              >
                <ChartBarIcon className="w-4 h-4" />
                Analyze
              </button>
            )}

            {/* Voice Toggle */}
            <button
              onClick={() => {
                if (isPlaying) stopAudio();
                setVoiceEnabled(!voiceEnabled);
              }}
              className={clsx(
                'p-2 rounded-lg transition-colors',
                voiceEnabled
                  ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
              )}
              title={voiceEnabled ? 'Disable voice output' : 'Enable voice output'}
            >
              {voiceEnabled ? (
                <SpeakerWaveIcon className="w-5 h-5" />
              ) : (
                <SpeakerXMarkIcon className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto card p-4 mb-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={clsx(
              'flex',
              message.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={clsx(
                'max-w-[80%] rounded-2xl px-4 py-3',
                message.role === 'user'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
              )}
            >
              {message.isLoading ? (
                <div className="flex items-center gap-2">
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  <span>Thinking...</span>
                </div>
              ) : (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {renderMarkdown(message.content)}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="card p-4">
        <div className="flex items-end gap-3">
          {/* Voice Input Button */}
          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isLoading}
            className={clsx(
              'p-3 rounded-xl transition-all',
              isRecording
                ? 'bg-red-500 text-white animate-pulse'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
            )}
            title={isRecording ? 'Stop recording' : 'Start voice input'}
          >
            {isRecording ? (
              <StopIcon className="w-5 h-5" />
            ) : (
              <MicrophoneIcon className="w-5 h-5" />
            )}
          </button>

          {/* Text Input */}
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about traffic patterns, simulation results, or ML control..."
              rows={1}
              className="input resize-none pr-12 py-3"
              disabled={isLoading || isRecording}
            />
          </div>

          {/* Send Button */}
          <button
            onClick={() => sendMessage(input)}
            disabled={isLoading || !input.trim()}
            className={clsx(
              'p-3 rounded-xl transition-all',
              input.trim() && !isLoading
                ? 'bg-primary-600 text-white hover:bg-primary-700'
                : 'bg-gray-100 text-gray-400 dark:bg-gray-700'
            )}
          >
            <PaperAirplaneIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Status Bar */}
        <div className="flex items-center justify-between mt-3 text-xs text-gray-500 dark:text-gray-400">
          <div className="flex items-center gap-4">
            {isRecording && (
              <span className="flex items-center gap-1 text-red-500">
                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                Recording...
              </span>
            )}
            {isPlaying && (
              <span className="flex items-center gap-1 text-primary-500">
                <SpeakerWaveIcon className="w-3 h-3" />
                Playing audio...
                <button
                  onClick={stopAudio}
                  className="ml-1 text-gray-400 hover:text-gray-600"
                >
                  <StopIcon className="w-3 h-3" />
                </button>
              </span>
            )}
          </div>
          <div>
            {selectedRunId ? (
              <span>
                Context: Run <span className="font-medium">{selectedRunId}</span>
              </span>
            ) : (
              <span>No simulation context selected</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
