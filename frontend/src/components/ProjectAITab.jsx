import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Plus,
  MessageSquare,
  Trash2,
  Bot,
  Lock,
  Send,
  ExternalLink,
  X,
  Database,
  Shield,
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

  const renderTextWithActivityChips = (text) => {
    const codeRegex = /\b(ACT-[A-Za-z0-9_\-]+|[A-Za-z]{2,5}-\d{1,5})\b/gi;
    const parts = text.split(codeRegex);

    return parts.map((part, i) => {
      if (part.match(/^(ACT-[A-Za-z0-9_\-]+|[A-Za-z]{2,5}-\d{1,5})$/i)) {
        return (
          <button
            key={i}
            type="button"
            onClick={() => onSelectActivityCode && onSelectActivityCode(part)}
            className="activity-code-chip"
            title={`Click to view activity ${part} in schedule`}
          >
            <span>{part}</span>
            <ExternalLink size={10} className="opacity-75 flex-shrink-0" />
          </button>
        );
      }
      return part;
    });
  };

  const renderAssistantMarkdown = (content) => {
    if (!content) return null;

    const components = {
      code({ inline, className, children, ...props }) {
        const textVal = String(children).replace(/\n$/, '');
        if (inline && textVal.match(/^(ACT-[A-Za-z0-9_\-]+|[A-Za-z]{2,5}-\d{1,5})$/i)) {
          return (
            <button
              type="button"
              onClick={() => onSelectActivityCode && onSelectActivityCode(textVal)}
              className="activity-code-chip"
              title={`Click to view activity ${textVal} in schedule`}
            >
              <span>{textVal}</span>
              <ExternalLink size={10} className="opacity-75 flex-shrink-0" />
            </button>
          );
        }
        return (
          <code className={className} {...props}>
            {children}
          </code>
        );
      },
      p({ children }) {
        return (
          <p>
            {React.Children.map(children, (child) => {
              if (typeof child === 'string') {
                return renderTextWithActivityChips(child);
              }
              return child;
            })}
          </p>
        );
      },
      li({ children }) {
        return (
          <li>
            {React.Children.map(children, (child) => {
              if (typeof child === 'string') {
                return renderTextWithActivityChips(child);
              }
              return child;
            })}
          </li>
        );
      },
    };

    return (
      <div className="ai-markdown-content">
        <ReactMarkdown components={components}>{content}</ReactMarkdown>
      </div>
    );
  };

  const suggestionChips = [
    { label: '👥 Assigned Team', prompt: 'How many supervisors are assigned to this project?' },
    { label: '📊 Project Overview', prompt: 'Give me an operational overview of project status' },
    { label: "📅 Today's Work", prompt: "What activities are scheduled for today?" },
    { label: '⚠️ Overdue Activities', prompt: 'Show me all overdue activities' },
    { label: '⏳ Upcoming Deadlines', prompt: 'What activities are due in the next 7 days?' },
    { label: '🏗️ Discipline Progress', prompt: 'Provide a discipline progress breakdown' },
  ];

  return (
    <div className="project-ai-card">
      {/* Clean AI Header */}
      <div className="project-ai-header">
        <div className="project-ai-header-main">
          <div className="project-ai-icon-badge">
            <Bot size={20} />
          </div>
          <div className="project-ai-header-titles">
            <div className="project-ai-title-row">
              <h2 className="project-ai-main-heading">Project AI</h2>
              <span className="project-ai-project-name">— {project.name}</span>
              <div className="project-ai-badge-group">
                <span className="ai-badge ai-badge-blue">
                  PROJECT SCOPED
                </span>
                <span className="ai-badge ai-badge-amber">
                  <Lock size={10} />
                  READ ONLY
                </span>
              </div>
            </div>
            <div className="project-ai-meta-row">
              <span>Project: <strong className="font-mono">{project.project_code}</strong></span>
              <span className="meta-separator">•</span>
              <span>Role: <strong>{user.role}</strong></span>
              {assignedDiscipline && (
                <>
                  <span className="meta-separator">•</span>
                  <span className="text-amber-700 font-semibold">({assignedDiscipline} Scoped)</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout Shell */}
      <div className="project-ai-body">
        {/* LEFT SIDEBAR: Conversations */}
        <aside className="project-ai-sidebar">
          <div className="project-ai-sidebar-top">
            <button
              type="button"
              onClick={handleNewChat}
              className="btn-new-chat"
            >
              <Plus size={15} />
              <span>+ New Chat</span>
            </button>
          </div>

          <div className="project-ai-sidebar-list">
            <div className="sidebar-section-label">
              Recent Conversations
            </div>

            {fetchingHistory ? (
              <div className="sidebar-loading-text">Loading history...</div>
            ) : conversations.length === 0 ? (
              <div className="sidebar-empty-text">No chat history yet.</div>
            ) : (
              conversations.map((conv) => {
                const isActive = conv.id === activeConversationId;
                return (
                  <div
                    key={conv.id}
                    onClick={() => handleSelectConversation(conv.id)}
                    className={`sidebar-conv-row ${isActive ? 'active' : ''}`}
                  >
                    <div className="conv-row-title-block">
                      <MessageSquare size={14} className="conv-icon" />
                      <span className="conv-title-text" title={conv.title}>
                        {conv.title}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteConversation(e, conv.id)}
                      className="conv-delete-btn"
                      title="Delete Conversation"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* MAIN CHAT AREA */}
        <main className="project-ai-chat-area">
          {errorMsg && (
            <div className="ai-error-banner">
              <span>{errorMsg}</span>
              <button type="button" onClick={() => setErrorMsg(null)} className="error-close-btn">
                <X size={14} />
              </button>
            </div>
          )}

          {/* Message Stream */}
          <div className="project-ai-stream-container">
            <div className="stream-inner-max-width">
              {messages.length === 0 ? (
                <div className="project-ai-empty-wrapper">
                  <div className="empty-avatar-icon">
                    <Bot size={28} />
                  </div>
                  <h3 className="empty-heading">Project Operational Intelligence</h3>
                  <p className="empty-description">
                    Ask operational questions about baseline schedules, assigned team members, site progress, overdue activities, or discipline status. All data is derived strictly from this project's database.
                  </p>

                  <div className="empty-chips-grid">
                    {suggestionChips.map((chip, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSendMessage(chip.prompt)}
                        className="chip-prompt-btn"
                      >
                        <span className="chip-icon">{chip.label.split(' ')[0]}</span>
                        <span className="chip-text">{chip.label.substring(chip.label.indexOf(' ') + 1)}</span>
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
                    <div key={i} className={`chat-message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
                      <div className={`chat-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
                        {!isUser && (
                          <div className="assistant-bubble-header">
                            <span className="assistant-name-tag">
                              <Bot size={14} className="bot-icon-small" />
                              AI Assistant
                            </span>
                            <span className="message-timestamp">
                              {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                            </span>
                          </div>
                        )}

                        <div className="message-body-content">
                          {isUser ? (
                            <p className="user-message-text">{msg.content}</p>
                          ) : (
                            renderAssistantMarkdown(msg.content)
                          )}
                        </div>

                        {!isUser && sources && sources.length > 0 && (
                          <details className="tools-disclosure">
                            <summary className="tools-disclosure-summary">
                              <Database size={11} className="inline mr-1 opacity-70" />
                              Project data consulted ({sources.length} {sources.length === 1 ? 'tool' : 'tools'})
                            </summary>
                            <div className="tools-disclosure-body">
                              {sources.map((s, si) => (
                                <div key={si} className="tool-source-item">
                                  <span className="tool-name">{s.tool}</span>
                                  <span className="tool-args">{JSON.stringify(s.args || {})}</span>
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
                <div className="chat-message-row assistant-row">
                  <div className="chat-bubble assistant-bubble loading-bubble">
                    <div className="loading-dot" />
                    <span>Retrieving live project data & generating response...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Bottom Anchored Chat Input Bar */}
          <div className="project-ai-input-bar">
            <div className="input-inner-max-width">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendMessage();
                }}
                className="chat-input-form"
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
                  className="chat-input-control"
                />
                <button
                  type="submit"
                  disabled={!promptInput.trim() || loading}
                  className="btn-send-message"
                >
                  <span>Send</span>
                  <Send size={14} />
                </button>
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}



