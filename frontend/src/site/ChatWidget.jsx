import { Fragment, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage, publicApi } from '../api/client'
import Icon from '../components/Icon'
import { SITE } from './content'

const STORAGE_KEY = 'site-chat'
const GREETING = {
  role: 'assistant',
  content: `Hello! I'm the ${SITE.name} virtual assistant. Ask me about admissions, programmes, fees, the library or how to reach us.`,
}

function load() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY))
    return Array.isArray(saved) && saved.length ? saved : [GREETING]
  } catch {
    return [GREETING]
  }
}

/** Inline Markdown the assistant uses: [links](/path) and **bold**. Built as elements, never as HTML. */
function inline(text, keyPrefix) {
  const parts = []
  const pattern = /\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*/g
  let last = 0
  let match
  while ((match = pattern.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    const key = `${keyPrefix}-${match.index}`
    if (match[3]) parts.push(<strong key={key}>{match[3]}</strong>)
    else if (match[2].startsWith('/')) parts.push(<Link key={key} to={match[2]}>{match[1]}</Link>)
    else if (/^(https?:|mailto:|tel:)/.test(match[2])) parts.push(<a key={key} href={match[2]} target="_blank" rel="noreferrer">{match[1]}</a>)
    else parts.push(match[1])
    last = pattern.lastIndex
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

/** Paragraphs and "- " bullet lists. */
function Rich({ text }) {
  const blocks = text.trim().split(/\n{2,}/)
  return blocks.map((block, b) => {
    const lines = block.split('\n')
    const bullets = lines.filter((l) => /^\s*[-*•]\s+/.test(l))
    if (bullets.length && bullets.length >= lines.length - 1) {
      const intro = lines.find((l) => !/^\s*[-*•]\s+/.test(l))
      return (
        <Fragment key={b}>
          {intro && <p>{inline(intro, `i${b}`)}</p>}
          <ul>{bullets.map((l, i) => <li key={i}>{inline(l.replace(/^\s*[-*•]\s+/, ''), `${b}-${i}`)}</li>)}</ul>
        </Fragment>
      )
    }
    return <p key={b}>{lines.map((l, i) => <Fragment key={i}>{i > 0 && <br />}{inline(l, `${b}-${i}`)}</Fragment>)}</p>
  })
}

/** The website's chat assistant: a button in the corner that opens a small chat panel. */
export default function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState(load)
  const [suggestions, setSuggestions] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-30))) } catch { /* private mode */ }
  }, [messages])

  useEffect(() => {
    if (!open) return undefined
    inputRef.current?.focus()
    if (!suggestions.length && messages.length === 1) {
      publicApi.get('/chat/').then(({ data }) => setSuggestions(data.suggestions)).catch(() => {})
    }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, suggestions.length, messages.length])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending, open])

  const send = async (text) => {
    const question = text.trim()
    if (!question || sending) return
    const next = [...messages, { role: 'user', content: question }]
    setMessages(next)
    setInput('')
    setSuggestions([])
    setError('')
    setSending(true)
    try {
      // The greeting is ours, not part of the conversation the assistant needs.
      const history = next.filter((m) => m !== GREETING && m.content !== GREETING.content)
      const { data } = await publicApi.post('/chat/', { messages: history })
      setMessages([...next, { role: 'assistant', content: data.reply }])
      setSuggestions(data.suggestions || [])
    } catch (err) {
      setError(err.response?.status === 429 ? "You've sent a lot of messages. Please wait a little and try again." : errorMessage(err))
      setMessages(messages)
      setInput(question)
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const restart = () => {
    setMessages([GREETING])
    setError('')
    publicApi.get('/chat/').then(({ data }) => setSuggestions(data.suggestions)).catch(() => {})
  }

  return (
    <div className={`chat ${open ? 'chat-open' : ''}`}>
      {open && (
        <section className="chat-panel" role="dialog" aria-label="Chat with the university assistant">
          <header className="chat-header">
            <span className="chat-avatar"><Icon name="cap" size={18} strokeWidth={2} /></span>
            <div className="grow">
              <strong>Ask {SITE.name}</strong>
              <span>Virtual assistant</span>
            </div>
            <button className="chat-icon-btn" onClick={restart} title="Start a new conversation" aria-label="Start a new conversation"><Icon name="plus" size={16} /></button>
            <button className="chat-icon-btn" onClick={() => setOpen(false)} aria-label="Close chat"><Icon name="close" size={16} /></button>
          </header>
          <div className="chat-messages" ref={listRef} aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg chat-${m.role}`}>
                {m.role === 'assistant' ? <Rich text={m.content} /> : m.content}
              </div>
            ))}
            {sending && <div className="chat-msg chat-assistant chat-typing" aria-label="Assistant is typing"><span /><span /><span /></div>}
            {!sending && suggestions.length > 0 && (
              <div className="chat-suggestions">
                {suggestions.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}
              </div>
            )}
            {error && <div className="chat-error" role="alert">{error}</div>}
          </div>
          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(input) }}>
            <input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} maxLength={500}
                   placeholder="Type your question…" aria-label="Your question" />
            <button disabled={!input.trim() || sending} aria-label="Send"><Icon name="send" size={17} /></button>
          </form>
          <p className="chat-disclaimer">Automated answers may be incomplete. Please don't share passwords or personal details.</p>
        </section>
      )}
      <button className="chat-launcher" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={open ? 'Close chat' : 'Chat with us'}>
        <Icon name={open ? 'close' : 'chat'} size={24} />
        {!open && <span>Ask us</span>}
      </button>
    </div>
  )
}
