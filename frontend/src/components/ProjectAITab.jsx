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
  CheckCircle,
  AlertTriangle,
  XCircle,
  HelpCircle,
  ChevronDown,
  Search,
  Settings,
  ArrowRight,
  Check,
  RefreshCw,
  Shield,
} from 'lucide-react';
import VoiceInputButton from './VoiceInputButton';
import {
  sendAIChatMessage,
  getAIConversations,
  getAIConversation,
  deleteAIConversation,
  confirmAIDraft,
  cancelAIDraft,
  selectAIDraftActivity,
  flagAIDraftPlannerReview,
  getActivities,
} from '../services/api';

/**
 * Error Boundary component to prevent Project AI render crashes from blanking out the app
 */
class ProjectAIErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Project AI Component Error Boundary caught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2.5rem', textAlign: 'center', backgroundColor: '#FFFFFF', border: '1px solid #DDE2E6', borderRadius: '10px', margin: '1rem 0' }}>
          <Bot size={36} style={{ margin: '0 auto 0.75rem', color: '#17324D' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#17324D', marginBottom: '0.5rem' }}>Project AI Workspace</h3>
          <p style={{ fontSize: '0.85rem', color: '#5E6B75', maxWidth: '460px', margin: '0 auto 1.25rem' }}>
            {this.state.error?.message || 'An unexpected rendering issue occurred while loading Project AI.'}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{ padding: '0.55rem 1.25rem', backgroundColor: '#17324D', color: '#FFFFFF', border: 'none', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}
          >
            Retry Loading AI Tab
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default function ProjectAITab(props) {
  return (
    <ProjectAIErrorBoundary>
      <ProjectAITabInner {...props} />
    </ProjectAIErrorBoundary>
  );
}

function ProjectAITabInner({ token, project, user, assignedDiscipline, onSelectActivityCode }) {
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
    if (project?.id) {
      loadConversations();
    }
  }, [project?.id]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const loadConversations = async () => {
    if (!project?.id) return;
    setFetchingHistory(true);
    const res = await getAIConversations(token, project.id);
    setFetchingHistory(false);
    if (res.success) {
      setConversations(res.data || []);
    }
  };

  const handleSelectConversation = async (convId) => {
    if (!project?.id || convId === activeConversationId) return;
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
    if (!project?.id) return;
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
    if (!textToSend || loading || !project?.id) return;

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
        draft: res.data.draft || null,
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
    if (!text) return null;
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
              <span className="project-ai-project-name">— {project?.name || 'Infrastructure Project'}</span>
              <div className="project-ai-badge-group">
                <span className="ai-badge ai-badge-blue">
                  PROJECT SCOPED
                </span>
                {user?.role === 'SUPERVISOR' ? (
                  <span className="ai-badge ai-badge-emerald">
                    <Shield size={10} />
                    CONFIRMATION REQUIRED
                  </span>
                ) : (
                  <span className="ai-badge ai-badge-amber">
                    <Lock size={10} />
                    READ ONLY
                  </span>
                )}
              </div>
            </div>
            <div className="project-ai-meta-row">
              <span>Project: <strong className="font-mono">{project?.project_code || ''}</strong></span>
              <span className="meta-separator">•</span>
              <span>Role: <strong>{user?.role || 'USER'}</strong></span>
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
                    Ask operational questions about baseline schedules, assigned team members, site progress, overdue activities, or discipline status. Supervisors can also report natural language execution updates.
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
                  let sources = msg.sources || [];
                  let evidence = msg.evidence || [];
                  if (msg.metadata_json) {
                    try {
                      const meta = JSON.parse(msg.metadata_json);
                      if (Array.isArray(meta)) {
                        sources = meta;
                      } else if (typeof meta === 'object' && meta !== null) {
                        if (meta.sources) sources = meta.sources;
                        if (meta.evidence) evidence = meta.evidence;
                      }
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
                            <>
                              {renderAssistantMarkdown(msg.content)}
                              {msg.draft && (
                                <AIDraftConfirmationCard
                                  token={token}
                                  projectId={project?.id}
                                  initialDraft={msg.draft}
                                  user={user}
                                  assignedDiscipline={assignedDiscipline}
                                  onDraftUpdated={(updatedDraft) => {
                                    setMessages((prev) =>
                                      prev.map((m) =>
                                        m.id === msg.id ? { ...m, draft: updatedDraft } : m
                                      )
                                    );
                                  }}
                                />
                              )}

                              {/* Phase 14 Grounded Evidence UI */}
                              {!msg.draft && evidence && evidence.length > 0 && (
                                <div className="ai-evidence-container">
                                  <div className="ai-evidence-header">
                                    <Shield size={12} className="text-orange" />
                                    <span>Evidence from project records ({evidence.length})</span>
                                  </div>
                                  <div className="ai-evidence-grid">
                                    {evidence.map((ev, ei) => (
                                      <div key={ei} className="ai-evidence-card">
                                        <div className="ai-ev-top-row">
                                          <span className="ai-ev-id-badge font-mono">{ev.id || `E${ei + 1}`}</span>
                                          {ev.date && <span className="ai-ev-date font-mono">{ev.date}</span>}
                                          {ev.source && (
                                            <span className={`ai-ev-source-badge src-${(ev.source || 'manual').toLowerCase()}`}>
                                              {ev.source.replace('_', ' ')}
                                            </span>
                                          )}
                                        </div>
                                        <div className="ai-ev-code-row">
                                          <span className="ai-ev-code font-mono">{ev.activity_code}</span>
                                          {ev.activity_name && <span className="ai-ev-name">• {ev.activity_name}</span>}
                                        </div>
                                        <div className="ai-ev-summary">{ev.summary}</div>
                                        {ev.remarks && (
                                          <div className="ai-ev-remarks">"{ev.remarks}"</div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </>
                          )}
                        </div>

                        {!isUser && sources && sources.length > 0 && !msg.draft && (
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
                    <span>Analyzing report &amp; matching schedule activity...</span>
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
                    user?.role === 'SUPERVISOR'
                      ? `Report site execution (e.g., 'Started foundation concreting today') or ask AI...`
                      : 'Ask operational AI assistant (project-wide)...'
                  }
                  disabled={loading}
                  className="chat-input-control"
                />
                <VoiceInputButton
                  disabled={loading}
                  currentInputText={promptInput}
                  onTranscript={(newFullText) => {
                    setPromptInput(newFullText);
                  }}
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

/**
 * Phase 8 AI Draft Confirmation Card Component (Polished Enterprise UI)
 */
function AIDraftConfirmationCard({ token, projectId, initialDraft, user, assignedDiscipline, onDraftUpdated }) {
  const [draft, setDraft] = useState(initialDraft);
  const [processing, setProcessing] = useState(false);
  const [cardError, setCardError] = useState(null);
  const [showActivityPicker, setShowActivityPicker] = useState(false);
  const [pickerSearch, setPickerSearch] = useState('');
  const [pickerActivities, setPickerActivities] = useState([]);
  const [loadingActivities, setLoadingActivities] = useState(false);

  useEffect(() => {
    setDraft(initialDraft);
  }, [initialDraft]);

  if (!draft) return null;

  const handleConfirm = async () => {
    if (processing || !projectId || draft.status !== 'PENDING') return;
    setProcessing(true);
    setCardError(null);

    const res = await confirmAIDraft(token, projectId, draft.id);
    setProcessing(false);

    if (res.success && res.data) {
      setDraft(res.data);
      if (onDraftUpdated) onDraftUpdated(res.data);
    } else {
      setCardError(res.error || 'Failed to confirm progress update');
    }
  };

  const handleCancel = async () => {
    if (processing || !projectId || draft.status !== 'PENDING') return;
    setProcessing(true);
    setCardError(null);

    const res = await cancelAIDraft(token, projectId, draft.id);
    setProcessing(false);

    if (res.success && res.data) {
      setDraft(res.data);
      if (onDraftUpdated) onDraftUpdated(res.data);
    } else {
      setCardError(res.error || 'Failed to cancel draft');
    }
  };

  const handleFlagReview = async () => {
    if (processing || !projectId) return;
    setProcessing(true);

    const res = await flagAIDraftPlannerReview(token, projectId, draft.id);
    setProcessing(false);

    if (res.success && res.data) {
      setDraft(res.data);
      if (onDraftUpdated) onDraftUpdated(res.data);
    }
  };

  const handleSelectActivity = async (actId) => {
    if (!projectId) return;
    setProcessing(true);
    setCardError(null);

    const res = await selectAIDraftActivity(token, projectId, draft.id, actId);
    setProcessing(false);
    setShowActivityPicker(false);

    if (res.success && res.data) {
      setDraft(res.data);
      if (onDraftUpdated) onDraftUpdated(res.data);
    } else {
      setCardError(res.error || 'Failed to link activity');
    }
  };

  const loadPickerActivities = async (searchVal = '') => {
    if (!projectId) return;
    setLoadingActivities(true);
    const res = await getActivities(token, projectId, {
      page: 1,
      pageSize: 20,
      search: searchVal,
      discipline: assignedDiscipline || 'ALL',
    });
    setLoadingActivities(false);
    if (res.success) {
      setPickerActivities(res.data.items || []);
    }
  };

  const togglePicker = () => {
    if (!showActivityPicker) {
      loadPickerActivities();
    }
    setShowActivityPicker(!showActivityPicker);
  };

  // Confidence Badge Rendering
  const renderConfidenceBadge = () => {
    if (draft.match_status === 'MANUALLY_SELECTED') {
      return (
        <span className="ai-confidence-badge manual">
          <Check size={11} />
          MANUALLY SELECTED
        </span>
      );
    }
    const confPct = draft.match_confidence !== null && draft.match_confidence !== undefined ? Math.round(draft.match_confidence * 100) : null;
    if (draft.match_status === 'MATCHED_HIGH') {
      return (
        <span className="ai-confidence-badge high">
          <CheckCircle size={11} />
          {confPct ? `${confPct}% HIGH CONFIDENCE` : 'HIGH CONFIDENCE'}
        </span>
      );
    }
    if (draft.match_status === 'MATCHED_MEDIUM') {
      return (
        <span className="ai-confidence-badge medium">
          <AlertTriangle size={11} />
          {confPct ? `${confPct}% MEDIUM` : 'MEDIUM CONFIDENCE'}
        </span>
      );
    }
    return (
      <span className="ai-confidence-badge low">
        <HelpCircle size={11} />
        UNMATCHED ACTIVITY
      </span>
    );
  };

  // State: CONFIRMED
  if (draft.status === 'CONFIRMED') {
    return (
      <div className="ai-draft-card-confirmed">
        <div className="confirmed-card-header">
          <div className="confirmed-card-title">
            <CheckCircle size={15} className="text-emerald-600 flex-shrink-0" />
            <span>✓ Progress Updated</span>
          </div>
          <span className="confirmed-source-tag">Source: AI Chat</span>
        </div>
        <div className="confirmed-activity-row">
          <span className="ai-draft-code-tag">{draft.matched_activity_code}</span>
          <span className="confirmed-activity-name">{draft.matched_activity_name}</span>
        </div>
        <div className="confirmed-details-row">
          <span>Action: <strong className="uppercase font-semibold">{draft.update_type}</strong></span>
          <span className="meta-dot">•</span>
          <span>Progress: <strong className="text-emerald-700 font-bold">{draft.progress_percentage ?? 100}%</strong></span>
          <span className="meta-dot">•</span>
          <span>Status: <strong>{draft.current_status || 'IN_PROGRESS'}</strong></span>
        </div>
      </div>
    );
  }

  // State: REJECTED
  if (draft.status === 'REJECTED') {
    return (
      <div className="ai-draft-card-rejected">
        <div className="rejected-card-header">
          <XCircle size={14} className="text-slate-500 flex-shrink-0" />
          <span className="font-semibold text-slate-700">Progress proposal cancelled</span>
        </div>
        <div className="rejected-card-desc">No database execution data was changed.</div>
      </div>
    );
  }

  // State: NEEDS_PLANNER_REVIEW
  if (draft.status === 'NEEDS_PLANNER_REVIEW') {
    return (
      <div className="ai-draft-card-review">
        <div className="review-card-header">
          <AlertTriangle size={14} className="text-amber-600 flex-shrink-0" />
          <span className="font-semibold text-amber-900">Flagged for Planner Review</span>
        </div>
        <div className="review-card-text">Original Report: "{draft.original_text}"</div>
        <div className="review-card-sub text-amber-700">Unmatched activity preserved for Planner inspection.</div>
      </div>
    );
  }

  // Active Proposal Card (PENDING)
  const currentProgVal = draft.current_progress ?? 0;

  // Derive proposed progress deterministically with safe fallbacks
  let proposedProgVal = currentProgVal;
  if (draft.proposed_progress !== null && draft.proposed_progress !== undefined) {
    proposedProgVal = draft.proposed_progress;
  } else if (draft.update_type === 'START') {
    proposedProgVal = (draft.progress_percentage !== null && draft.progress_percentage !== undefined && draft.progress_percentage > 0) ? draft.progress_percentage : currentProgVal;
  } else if (draft.update_type === 'PROGRESS') {
    proposedProgVal = draft.progress_percentage ?? currentProgVal;
  } else if (draft.update_type === 'COMPLETE') {
    proposedProgVal = 100;
  } else if (draft.update_type === 'ON_HOLD' || draft.update_type === 'RESUME') {
    proposedProgVal = currentProgVal;
  }

  // Derive proposed status deterministically with safe fallbacks
  let proposedStatusVal = draft.current_status || 'NOT_STARTED';
  if (draft.proposed_status) {
    proposedStatusVal = draft.proposed_status;
  } else if (draft.update_type === 'START') {
    proposedStatusVal = 'IN_PROGRESS';
  } else if (draft.update_type === 'PROGRESS') {
    proposedStatusVal = 'IN_PROGRESS';
  } else if (draft.update_type === 'COMPLETE') {
    proposedStatusVal = 'COMPLETED';
  } else if (draft.update_type === 'ON_HOLD') {
    proposedStatusVal = 'ON_HOLD';
  } else if (draft.update_type === 'RESUME') {
    proposedStatusVal = 'IN_PROGRESS';
  }

  return (
    <div className="ai-draft-card">
      {/* Header Bar */}
      <div className="ai-draft-header">
        <div className="ai-draft-header-title">
          <Settings size={14} className="text-slate-500" />
          <span>Progress Update Detected</span>
        </div>
        {renderConfidenceBadge()}
      </div>

      {cardError && (
        <div className="ai-draft-error-alert">
          {cardError}
        </div>
      )}

      {/* Activity Identity Box */}
      {draft.matched_activity_code ? (
        <div className="ai-draft-activity-box">
          <div className="ai-draft-activity-identity">
            <span className="ai-draft-code-tag">{draft.matched_activity_code}</span>
            {draft.matched_discipline && (
              <span className="ai-draft-discipline-tag">{draft.matched_discipline}</span>
            )}
          </div>
          <h4 className="ai-draft-activity-name">{draft.matched_activity_name}</h4>

          {/* 2-Column Detail Grid */}
          <div className="ai-draft-detail-grid">
            <div className="grid-item">
              <span className="grid-label">Action</span>
              <span className="grid-value action-badge">{draft.update_type}</span>
            </div>
            <div className="grid-item">
              <span className="grid-label">Reported Date</span>
              <span className="grid-value">{draft.reported_date}</span>
            </div>
            <div className="grid-item">
              <span className="grid-label">Current Progress</span>
              <span className="grid-value">{currentProgVal}%</span>
            </div>
            <div className="grid-item">
              <span className="grid-label">Proposed Progress</span>
              <span className="grid-value highlight-emerald">{proposedProgVal}%</span>
            </div>
            <div className="grid-item">
              <span className="grid-label">Current Status</span>
              <span className="grid-value">{draft.current_status || 'NOT_STARTED'}</span>
            </div>
            <div className="grid-item">
              <span className="grid-label">Proposed Status</span>
              <span className="grid-value font-bold text-amber-800">{proposedStatusVal}</span>
            </div>
            {draft.remarks && (
              <div className="grid-item full-width">
                <span className="grid-label">Remarks</span>
                <span className="grid-value italic">"{draft.remarks}"</span>
              </div>
            )}
          </div>

          {/* Progress Visualizer Bar */}
          {draft.update_type === 'PROGRESS' && (
            <div className="ai-draft-progress-bar-container">
              <div className="progress-bar-labels">
                <span>Progress: <strong>{currentProgVal}%</strong></span>
                <ArrowRight size={11} className="text-slate-400" />
                <span className="text-emerald-700 font-bold">{proposedProgVal}%</span>
              </div>
              <div className="progress-bar-track">
                <div className="progress-fill-current" style={{ width: `${Math.min(100, currentProgVal)}%` }} />
                <div
                  className="progress-fill-proposed"
                  style={{
                    left: `${Math.min(100, currentProgVal)}%`,
                    width: `${Math.max(0, Math.min(100, proposedProgVal - currentProgVal))}%`,
                  }}
                />
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="ai-draft-unmatched-box">
          <p className="unmatched-title">Could not confidently match report to a schedule activity.</p>
          <p className="unmatched-report-text">Original Report: "{draft.original_text}"</p>
        </div>
      )}

      {/* Suggested Alternative Candidates */}
      {draft.alternatives && draft.alternatives.length > 0 && draft.match_status !== 'MATCHED_HIGH' && (
        <div className="ai-draft-alternatives-section">
          <span className="alternatives-label">Suggested Alternative Candidates:</span>
          <div className="alternatives-list">
            {draft.alternatives.map((alt) => (
              <button
                key={alt.activity_id}
                type="button"
                onClick={() => handleSelectActivity(alt.activity_id)}
                disabled={processing}
                className="btn-alternative-candidate"
              >
                <span className="alt-code">{alt.activity_code}</span>
                <span className="alt-name">{alt.activity_name}</span>
                <span className="alt-conf">{Math.round(alt.confidence * 100)}%</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Choose Different Activity Picker Panel */}
      {showActivityPicker && (
        <div className="ai-draft-picker-panel">
          <div className="picker-search-wrapper">
            <Search size={14} className="picker-search-icon" />
            <input
              type="text"
              value={pickerSearch}
              onChange={(e) => {
                setPickerSearch(e.target.value);
                loadPickerActivities(e.target.value);
              }}
              placeholder={`Search ${assignedDiscipline || ''} activities...`}
              className="picker-search-input"
            />
          </div>
          <div className="picker-candidate-list">
            {loadingActivities ? (
              <div className="picker-loading-text">Loading activities...</div>
            ) : pickerActivities.length === 0 ? (
              <div className="picker-empty-text">No matching activities found in your assigned discipline.</div>
            ) : (
              pickerActivities.map((act) => (
                <div
                  key={act.id}
                  onClick={() => handleSelectActivity(act.id)}
                  className="picker-candidate-row"
                >
                  <div className="candidate-left">
                    <span className="ai-draft-code-tag">{act.activity_code}</span>
                    <span className="candidate-name">{act.activity_name}</span>
                  </div>
                  <span className="ai-draft-discipline-tag">{act.discipline}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Action Buttons Row */}
      <div className="ai-draft-actions-row">
        {draft.matched_activity_id && (
          <button
            type="button"
            onClick={handleConfirm}
            disabled={processing}
            className="btn-draft-confirm"
          >
            {processing ? (
              <>
                <RefreshCw size={13} className="animate-spin" />
                <span>Updating...</span>
              </>
            ) : (
              <>
                <Check size={14} />
                <span>Confirm Update</span>
              </>
            )}
          </button>
        )}

        <button
          type="button"
          onClick={togglePicker}
          disabled={processing}
          className="btn-draft-secondary"
        >
          <span>Choose Different Activity</span>
          <ChevronDown size={13} />
        </button>

        {!draft.matched_activity_id && (
          <button
            type="button"
            onClick={handleFlagReview}
            disabled={processing}
            className="btn-draft-warning"
          >
            Flag for Planner Review
          </button>
        )}

        <button
          type="button"
          onClick={handleCancel}
          disabled={processing}
          className="btn-draft-cancel"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
