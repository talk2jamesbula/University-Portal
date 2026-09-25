import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Card, Modal, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import { formatCountdown } from './exams'

const LETTERS = 'ABCDEF'

function Submitted({ paper }) {
  return (
    <div className="stack-lg checkin-page">
      <Card>
        <div className="checkin-result">
          <span className="checkin-icon tone-green"><Icon name="check" size={32} /></span>
          <h2>Your {paper.exam.code} exam has been submitted</h2>
          <p className="muted">
            {paper.status === 'timed_out' ? 'Time ran out, so your paper was submitted automatically. ' : ''}
            You answered {paper.answered} of {paper.question_count} questions. Your score will appear with your results once
            they are approved and published.
          </p>
          <Link to="/portal/exams" className="btn btn-primary">Back to examinations</Link>
        </div>
      </Card>
    </div>
  )
}

/** The open paper. Mounted once the paper has loaded, so its state starts from the server's copy. */
function Paper({ paper, onSubmitted, onExpired }) {
  const id = paper.id
  const [answers, setAnswers] = useState(() => Object.fromEntries(paper.questions.map((q) => [q.id, q.answer])))
  const [saveState, setSaveState] = useState({})
  const [current, setCurrent] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  // How far the device clock is from the server's: the countdown follows the server.
  const [offset] = useState(() => new Date(paper.server_time).getTime() - Date.now())
  const [focusLosses, setFocusLosses] = useState(paper.focus_losses)
  const [confirming, setConfirming] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const latest = useRef({ ...answers })
  const inFlight = useRef({})
  const finishing = useRef(false)
  const deadline = new Date(paper.deadline).getTime()

  /** Save a question's answer, one request at a time per question, always ending on the latest choice. */
  const send = useCallback((qid) => {
    if (inFlight.current[qid]) return inFlight.current[qid]
    const run = (async () => {
      let sent
      try {
        do {
          sent = latest.current[qid]
          setSaveState((s) => ({ ...s, [qid]: 'saving' }))
          await api.put(`/exams/attempts/${id}/answer/`, { question: qid, choice: sent ?? null })
        } while (latest.current[qid] !== sent)
        setSaveState((s) => ({ ...s, [qid]: 'saved' }))
      } catch (err) {
        if (err.response?.status === 400) onExpired() // time is up or the paper was submitted
        else setSaveState((s) => ({ ...s, [qid]: 'error' }))
      } finally {
        delete inFlight.current[qid]
      }
    })()
    inFlight.current[qid] = run
    return run
  }, [id, onExpired])

  const choose = (qid, choiceId) => {
    latest.current[qid] = choiceId
    setAnswers((a) => ({ ...a, [qid]: choiceId }))
    send(qid)
  }

  const finish = useCallback(async () => {
    if (finishing.current) return
    finishing.current = true
    setSubmitting(true)
    setSubmitError('')
    await Promise.allSettled(Object.values(inFlight.current))
    try {
      const { data } = await api.post(`/exams/attempts/${id}/submit/`)
      onSubmitted(data)
    } catch (err) {
      setSubmitError(errorMessage(err, 'Could not submit. Check your connection and try again.'))
      finishing.current = false
      setSubmitting(false)
      setConfirming(false)
    }
  }, [id, onSubmitted])

  // The clock ticks every second and submits the paper when time runs out.
  useEffect(() => {
    const timer = setInterval(() => {
      const t = Date.now()
      setNow(t)
      if (deadline - (t + offset) <= 0) finish()
    }, 1000)
    return () => clearInterval(timer)
  }, [deadline, offset, finish])
  const remaining = (deadline - (now + offset)) / 1000

  // Retry answers that failed to save (e.g. the network dropped for a moment).
  const failed = Object.entries(saveState).filter(([, st]) => st === 'error').map(([qid]) => qid).join(',')
  useEffect(() => {
    if (!failed) return undefined
    const timer = setTimeout(() => failed.split(',').forEach((qid) => send(Number(qid))), 5000)
    return () => clearTimeout(timer)
  }, [failed, send])

  // Leaving the page is recorded for the lecturer; warn before closing the tab.
  useEffect(() => {
    const onVisibility = () => {
      api.post(`/exams/attempts/${id}/event/`, { kind: document.hidden ? 'left_page' : 'returned' })
        .then(({ data }) => setFocusLosses(data.focus_losses))
        .catch(() => {})
    }
    const onUnload = (e) => { e.preventDefault(); e.returnValue = '' }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('beforeunload', onUnload)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('beforeunload', onUnload)
    }
  }, [id])

  const questions = paper.questions
  const question = questions[current]
  const answered = questions.filter((q) => answers[q.id] != null).length
  const unanswered = questions.length - answered
  const low = remaining < 300

  return (
    <div className="exam-shell">
      <div className="exam-bar">
        <div>
          <div className="cell-title">{paper.exam.code} · {paper.exam.title}</div>
          <div className="muted small">{answered} of {questions.length} answered</div>
        </div>
        <div className={`exam-timer ${low ? 'is-low' : ''}`} role="timer" aria-live={low ? 'polite' : 'off'} aria-label="Time left">
          <Icon name="clock" size={18} /> {formatCountdown(remaining)}
        </div>
        <button className="btn btn-primary" onClick={() => setConfirming(true)} disabled={submitting}>Submit</button>
      </div>

      {failed && (
        <Alert>Some answers haven't been saved yet. Check your connection; we'll keep trying.</Alert>
      )}
      <Alert onClose={() => setSubmitError('')}>{submitError}</Alert>
      {focusLosses > 0 && (
        <div className="callout callout-danger">
          <Icon name="alert" />
          <span>You have left the exam page {focusLosses} time{focusLosses === 1 ? '' : 's'}. This is recorded and reported to your lecturer.</span>
        </div>
      )}

      <div className="exam-layout">
        <Card>
          <div className="question-head">
            <span className="eyebrow">Question {question.number} of {questions.length}</span>
            <span className="muted small">
              {question.marks} mark{question.marks === 1 ? '' : 's'}
              {saveState[question.id] === 'saving' && ' · Saving…'}
              {saveState[question.id] === 'saved' && ' · Saved'}
              {saveState[question.id] === 'error' && <span className="text-red"> · Not saved</span>}
            </span>
          </div>
          <p className="question-text">{question.text}</p>
          <div className="choice-list" role="radiogroup" aria-label={`Question ${question.number}`}>
            {question.choices.map((c, i) => (
              <label key={c.id} className={`choice ${answers[question.id] === c.id ? 'is-selected' : ''}`}>
                <input type="radio" name={`q-${question.id}`} checked={answers[question.id] === c.id} onChange={() => choose(question.id, c.id)} />
                <span className="choice-letter">{LETTERS[i]}</span>
                <span>{c.text}</span>
              </label>
            ))}
          </div>
          <div className="question-actions">
            <button className="btn btn-ghost" onClick={() => setCurrent(current - 1)} disabled={current === 0}>
              <Icon name="arrowLeft" size={16} /> Previous
            </button>
            {answers[question.id] != null && (
              <button className="link-button muted small" onClick={() => choose(question.id, null)}>Clear answer</button>
            )}
            {current < questions.length - 1 ? (
              <button className="btn btn-primary" onClick={() => setCurrent(current + 1)}>Next <Icon name="arrowRight" size={16} /></button>
            ) : (
              <button className="btn btn-primary" onClick={() => setConfirming(true)}>Finish</button>
            )}
          </div>
        </Card>
        <Card title="Questions">
          <div className="question-nav">
            {questions.map((q, i) => (
              <button
                key={q.id}
                className={`qnav-btn ${answers[q.id] != null ? 'is-answered' : ''} ${i === current ? 'is-current' : ''}`}
                onClick={() => setCurrent(i)}
                aria-label={`Question ${q.number}${answers[q.id] != null ? ', answered' : ''}`}
                aria-current={i === current ? 'step' : undefined}
              >
                {q.number}
              </button>
            ))}
          </div>
          {paper.exam.instructions && <p className="muted small">{paper.exam.instructions}</p>}
        </Card>
      </div>

      {confirming && (
        <Modal
          title="Submit your exam?"
          onClose={() => setConfirming(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setConfirming(false)}>Keep working</button>
              <button className="btn btn-primary" onClick={finish} disabled={submitting}>{submitting ? 'Submitting…' : 'Submit now'}</button>
            </>
          }
        >
          <p>
            {unanswered
              ? <><strong>{unanswered} question{unanswered === 1 ? ' is' : 's are'} unanswered.</strong> </>
              : 'You have answered every question. '}
            Once you submit you can't change your answers.
          </p>
        </Modal>
      )}
    </div>
  )
}

/** A student sitting a computer-based test: one question at a time, autosaved, against a server-side clock. */
export default function TakeExam() {
  const { id } = useParams()
  const { data: paper, error, reload, setData } = useApi(`/exams/attempts/${id}/`)

  if (error && !paper) return <Alert>{error}</Alert>
  if (!paper) return <Spinner />
  if (paper.status !== 'in_progress') return <Submitted paper={paper} />
  return <Paper paper={paper} onSubmitted={setData} onExpired={reload} />
}
