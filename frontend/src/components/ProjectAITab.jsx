import React, { useState, useEffect, useRef } from 'react';
import {
  Plus,
  MessageSquare,
  Trash2,
  Bot,
  Lock,
  Send,
  ExternalLink,
  X,
  Sparkles,
} from 'lucide-react';
import {
  sendAIChatMessage,
  getAIConversations,
  getAIConversation,
  deleteAIConversation,
} from '../services/api';

export default function ProjectAITab({ token, project, user, assignedDiscipline, onSelectActivityCode }) {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [promptInput, setPromptInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    loadConversations();
  }, [project.id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const loadConversations = async () => {
    setFetchingHistory(true);
    const res = await getAIConversations(token, project.id);
    setFetchingHistory(false);
    if (res.success) {
      setConversations(res.data || []);
    }
  };

  const handleSelectConversation = async (convId) => {
    if (convId === activeConversationId) return;
    setActiveConversationId(convId);
    setErrorMsg(null);
    setLoading(true);

    const res = await getAIConversation(token, project.id, convId);
    setLoading(false);

    if (res.success && res.data) {
      setMessages(res.data.messages || []);
    } else {
      setErrorMsg(res.error || 'Failed to load conversation history');
    }
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setPromptInput('');
    setErrorMsg(null);
  };

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this chat session?')) return;

    const res = await deleteAIConversation(token, project.id, convId);
    if (res.success) {
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleNewChat();
      }
    } else {
      alert(res.error || 'Failed to delete conversation');
    }
  };

  const handleSendMessage = async (customPrompt = null) => {
    const textToSend = customPrompt || promptInput.trim();
    if (!textToSend || loading) return;

    setErrorMsg(null);
    if (!customPrompt) setPromptInput('');

    const tempUserMsg = {
      id: Date.now(),
      role: 'USER',
      content: textToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setLoading(true);

    const res = await sendAIChatMessage(token, project.id, {
      conversationId: activeConversationId,
      prompt: textToSend,
    });

    setLoading(false);

    if (res.success && res.data) {
      if (!activeConversationId) {
        setActiveConversationId(res.data.conversation_id);
        loadConversations();
      }

      const assistantMsg = {
        id: res.data.assistant_message.id,
        role: 'ASSISTANT',
        content: res.data.assistant_message.content,
        created_at: res.data.assistant_message.created_at,
        metadata_json: JSON.stringify(res.data.sources || []),
      };

      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempUserMsg.id);
        return [...filtered, res.data.user_message, assistantMsg];
      });
    } else {
      setErrorMsg(res.error || 'Failed to get response from AI Assistant');
    }
  };

  const renderFormattedContent = (content) => {
    if (!content) return null;

    const lines = content.split('\n');

    return lines.map((line, idx) => {
      if (line.startsWith('### ') || line.startsWith('#### ')) {
        const title = line.replace(/^#{3,4}\s+/, '');
        return (
          <h4 key={idx} className="font-semibold text-slate-100 text-sm mt-3 mb-1">
            {renderLineWithClickableCodes(title)}
          </h4>
        );
      }

      if (line.trim().startsWith('- ')) {
        const bulletText = line.trim().substring(2);
        return (
          <div key={idx} className="flex items-start gap-2 text-xs text-slate-300 my-0.5 pl-2">
            <span className="text-cyan-400 font-bold">•</span>
            <div>{renderLineWithClickableCodes(bulletText)}</div>
          </div>
        );
      }

      if (!line.trim()) {
        return <div key={idx} className="h-2" />;
      }

      return (
        <p key={idx} className="text-xs text-slate-300 my-1 leading-relaxed">
          {renderLineWithClickableCodes(line)}
        </p>
      );
    });
  };

  const renderLineWithClickableCodes = (text) => {
    const codeRegex = /(`?[A-Za-z0-9_\-]{3,15}`?)/g;
    const parts = text.split(codeRegex);

    return parts.map((part, i) => {
      const cleanCode = part.replace(/`/g, '');
      if (cleanCode.match(/^(ACT-[A-Za-z0-9_\-]+|PIP-\d+|CIV-\d+|ELE-\d+)$/i)) {
        return (
          <button
            key={i}
            onClick={() => onSelectActivityCode && onSelectActivityCode(cleanCode)}
            className="inline-flex items-center gap-1 bg-cyan-950/70 text-cyan-300 font-mono text-[11px] px-1.5 py-0.5 rounded border border-cyan-700 hover:bg-cyan-900 transition-colors mx-0.5 font-medium cursor-pointer"
            title={`Click to view activity ${cleanCode} in schedule`}
          >
            <span>{cleanCode}</span>
            <ExternalLink size={10} className="opacity-70 flex-shrink-0" />
          </button>
        );
      }

      if (part.includes('**')) {
        const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
        return boldParts.map((bPart, bi) => {
          if (bPart.startsWith('**') && bPart.endsWith('**')) {
            return <strong key={bi} className="font-semibold text-slate-100">{bPart.slice(2, -2)}</strong>;
          }
          return bPart;
        });
      }

      return part;
    });
  };

  const suggestionChips = [
    { label: '📊 Project Overview', prompt: 'Give me an operational overview of project status' },
    { label: "📅 Today's Work", prompt: "What activities are scheduled for today?" },
    { label: '⚠️ Overdue Activities', prompt: 'Show me all overdue activities' },
    { label: '⏳ Upcoming Deadlines', prompt: 'What activities are due in the next 7 days?' },
    { label: '🏗️ Discipline Progress', prompt: 'Provide a discipline progress breakdown' },
    { label: '📝 Recent Site Updates', prompt: 'Show recent site updates and audit logs' },
  ];

  return (
    <div className="project-ai-workspace">
      {/* Sidebar: Conversations */}
      <div className="project-ai-sidebar">
        <div className="project-ai-sidebar-header">
          <button
            onClick={handleNewChat}
            className="project-ai-new-chat-btn"
          >
            <Plus size={16} className="flex-shrink-0" />
            <span>+ New Chat Session</span>
          </button>
        </div>

        <div className="project-ai-conv-list">
          <div className="px-2 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Recent Conversations
          </div>

          {fetchingHistory ? (
            <div className="p-4 text-center text-xs text-slate-400 animate-pulse">Loading history...</div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center text-xs text-slate-400">No chat history yet.</div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              return (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConversation(conv.id)}
                  className={`project-ai-conv-item ${isActive ? 'active' : ''}`}
                >
                  <div className="project-ai-conv-item-title">
                    <MessageSquare size={14} className="flex-shrink-0 text-cyan-400" />
                    <span className="truncate">{conv.title}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                    className="project-ai-delete-btn"
                    title="Delete Conversation"
                  >
                    <Trash2 size={14} className="flex-shrink-0" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="project-ai-main">
        {/* Header */}
        <div className="project-ai-header">
          <div className="project-ai-header-left">
            <div className="project-ai-avatar">
              <Bot size={18} className="flex-shrink-0" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                Project Operational AI Assistant
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-600/40 uppercase tracking-wider">
                  <Lock size={11} className="text-cyan-400 flex-shrink-0" />
                  READ-ONLY ASSISTANT
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Scope: <span className="text-cyan-300 font-mono">{project.project_code}</span> | Role:{' '}
                <span className="text-slate-200 font-medium">{user.role}</span>
                {assignedDiscipline && (
                  <span className="ml-1 text-amber-400 font-medium">({assignedDiscipline} Scoped)</span>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Error Banner */}
        {errorMsg && (
          <div className="bg-red-950/80 border-b border-red-800/80 px-4 py-2 text-xs text-red-200 flex items-center justify-between">
            <span>{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-white cursor-pointer">
              <X size={14} className="flex-shrink-0" />
            </button>
          </div>
        )}

        {/* Message Stream */}
        <div className="project-ai-stream">
          {messages.length === 0 ? (
            <div className="project-ai-empty-state">
              <div className="project-ai-empty-icon">
                <Bot size={30} className="flex-shrink-0 text-cyan-400" />
              </div>
              <h4 className="text-sm font-semibold text-slate-100 mb-1">
                Project Operational Intelligence
              </h4>
              <p className="text-xs text-slate-400 mb-4 max-w-lg mx-auto leading-relaxed">
                Ask questions about baseline schedules, actual site progress, overdue activities, upcoming deadlines, or discipline status. All responses are derived strictly from this project's database.
              </p>

              <div className="project-ai-chips-grid">
                {suggestionChips.map((chip, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(chip.prompt)}
                    className="project-ai-chip-btn"
                  >
                    <span className="text-sm flex-shrink-0">{chip.label.split(' ')[0]}</span>
                    <span className="font-medium truncate">{chip.label.substring(chip.label.indexOf(' ') + 1)}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => {
              const isUser = msg.role === 'USER';
              let sources = [];
              if (msg.metadata_json) {
                try {
                  sources = JSON.parse(msg.metadata_json);
                } catch (e) {}
              }

              return (
                <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-3xl rounded-xl p-3 text-xs shadow-md ${
                      isUser
                        ? 'bg-gradient-to-r from-blue-700 to-cyan-700 text-white rounded-br-none'
                        : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none'
                    }`}
                  >
                    {!isUser && (
                      <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-1.5 mb-2">
                        <span className="font-semibold text-cyan-400 flex items-center gap-1 text-[11px]">
                          <Bot size={13} className="flex-shrink-0 text-cyan-400" />
                          AI Assistant
                        </span>
                        <span className="text-[10px] text-slate-500">
                          {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </div>
                    )}

                    <div className="space-y-1 leading-relaxed">
                      {isUser ? (
                        <p className="whitespace-pre-wrap font-medium">{msg.content}</p>
                      ) : (
                        renderFormattedContent(msg.content)
                      )}
                    </div>

                    {!isUser && sources && sources.length > 0 && (
                      <details className="mt-2.5 pt-2 border-t border-slate-800/80 text-[10px] text-slate-400">
                        <summary className="cursor-pointer font-medium hover:text-cyan-400 transition-colors">
                          Inspect Database Tools Executed ({sources.length})
                        </summary>
                        <div className="mt-1.5 space-y-1 pl-2 bg-slate-950/60 p-2 rounded border border-slate-800/60 font-mono">
                          {sources.map((s, si) => (
                            <div key={si} className="flex items-center justify-between text-[10px]">
                              <span className="text-cyan-400 font-semibold">{s.tool}</span>
                              <span className="text-slate-500">{JSON.stringify(s.args || {})}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              );
            })
          )}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-slate-900 border border-slate-800 text-slate-300 rounded-xl rounded-bl-none p-3 text-xs flex items-center gap-2 shadow-md">
                <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                <span className="animate-pulse">Retrieving live project data & generating operational answer...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="project-ai-input-container">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="project-ai-input-form"
          >
            <input
              type="text"
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              placeholder={
                assignedDiscipline
                  ? `Ask operational AI assistant (${assignedDiscipline} discipline scoped)...`
                  : 'Ask operational AI assistant (project-wide)...'
              }
              disabled={loading}
              className="project-ai-input-field"
            />
            <button
              type="submit"
              disabled={!promptInput.trim() || loading}
              className="project-ai-send-btn"
            >
              <span>Send</span>
              <Send size={14} className="flex-shrink-0" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

