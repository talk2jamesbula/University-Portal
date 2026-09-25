import { useState } from 'react'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Card, EmptyState, Modal, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import ImportQuestionsModal from './ImportQuestionsModal'

const LETTERS = 'ABCDEF'
const blankChoices = () => [0, 1, 2, 3].map((i) => ({ text: '', is_correct: i === 0 }))

function QuestionModal({ examId, question, onClose, onSaved }) {
  const [text, setText] = useState(question?.text ?? '')
  const [marks, setMarks] = useState(question?.marks ?? 1)
  const [choices, setChoices] = useState(question?.choices.map(({ text: t, is_correct }) => ({ text: t, is_correct })) ?? blankChoices())
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const setChoice = (i, change) => setChoices(choices.map((c, j) => (j === i ? { ...c, ...change } : c)))
  const markCorrect = (i) => setChoices(choices.map((c, j) => ({ ...c, is_correct: i === j })))
  const remove = (i) => {
    const next = choices.filter((_, j) => j !== i)
    if (!next.some((c) => c.is_correct)) next[0].is_correct = true
    setChoices(next)
  }
  const trueFalse = () => setChoices([{ text: 'True', is_correct: true }, { text: 'False', is_correct: false }])

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    const payload = { text, marks: Number(marks), choices }
    try {
      const { data } = question
        ? await api.put(`/exams/questions/${question.id}/`, payload)
        : await api.post(`/exams/timetable/${examId}/questions/`, payload)
      onSaved(data, Boolean(question))
    } catch (err) {
      setError(errorMessage(err))
      setSaving(false)
    }
  }

  return (
    <Modal
      wide
      title={question ? `Edit question ${question.order}` : 'Add a question'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="question-form" disabled={saving}>{saving ? 'Saving…' : 'Save question'}</button>
        </>
      }
    >
      <form id="question-form" className="form" onSubmit={save}>
        <Alert>{error}</Alert>
        <label className="field"><span>Question</span><textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} required /></label>
        <label className="field field-narrow"><span>Marks</span><input type="number" min="1" max="20" value={marks} onChange={(e) => setMarks(e.target.value)} required /></label>
        <fieldset className="field">
          <span>Options · choose the correct answer</span>
          <div className="stack">
            {choices.map((c, i) => (
              <div key={i} className="option-row">
                <input type="radio" name="correct" checked={c.is_correct} onChange={() => markCorrect(i)} aria-label={`Option ${LETTERS[i]} is correct`} />
                <span className="choice-letter">{LETTERS[i]}</span>
                <input value={c.text} onChange={(e) => setChoice(i, { text: e.target.value })} maxLength={500} required aria-label={`Option ${LETTERS[i]}`} />
                <button type="button" className="icon-btn" onClick={() => remove(i)} disabled={choices.length <= 2} aria-label={`Remove option ${LETTERS[i]}`}>
                  <Icon name="close" size={14} />
                </button>
              </div>
            ))}
          </div>
          <div className="row-actions">
            <button type="button" className="link-button" onClick={() => setChoices([...choices, { text: '', is_correct: false }])} disabled={choices.length >= 6}>
              <Icon name="plus" size={14} /> Add option
            </button>
            <button type="button" className="link-button" onClick={trueFalse}>Make it true / false</button>
          </div>
        </fieldset>
      </form>
    </Modal>
  )
}

function SettingsForm({ exam, total, locked, onSaved }) {
  const [perCandidate, setPerCandidate] = useState(exam.questions_per_candidate ?? '')
  const [instructions, setInstructions] = useState(exam.instructions)
  const [state, setState] = useState({ saving: false, error: '', saved: false })

  const save = async (e) => {
    e.preventDefault()
    setState({ saving: true, error: '', saved: false })
    const payload = { instructions, ...(locked ? {} : { questions_per_candidate: perCandidate === '' ? null : Number(perCandidate) }) }
    try {
      const { data } = await api.patch(`/exams/timetable/${exam.id}/settings/`, payload)
      onSaved(data)
      setState({ saving: false, error: '', saved: true })
    } catch (err) {
      setState({ saving: false, error: errorMessage(err), saved: false })
    }
  }

  return (
    <form className="form" onSubmit={save}>
      <Alert>{state.error}</Alert>
      <label className="field field-narrow">
        <span>Questions per candidate</span>
        <input type="number" min="1" max={total || undefined} value={perCandidate} onChange={(e) => setPerCandidate(e.target.value)}
               placeholder={`All ${total}`} disabled={locked} />
      </label>
      <p className="muted small">
        Every candidate gets the questions in a different order, with the options shuffled. Set a number lower than {total || 'the total'} to
        draw a different random selection for each candidate.
      </p>
      <label className="field"><span>Instructions shown to candidates</span><textarea rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} /></label>
      <div className="row-actions">
        <button className="btn btn-ghost btn-sm" disabled={state.saving}>{state.saving ? 'Saving…' : 'Save settings'}</button>
        {state.saved && <span className="text-green small">Saved</span>}
      </div>
    </form>
  )
}

/** The course lecturer writes a CBT's questions; they lock once the exam starts. */
export default function Questions({ exam, onExamChange }) {
  const { data, error, reload } = useApi(`/exams/timetable/${exam.id}/questions/`)
  const [editing, setEditing] = useState(null)
  const [removing, setRemoving] = useState(null)
  const [actionError, setActionError] = useState('')
  const [importing, setImporting] = useState(false)
  const [imported, setImported] = useState('')

  if (error && !data) return <Alert>{error}</Alert>
  if (!data) return <Spinner />

  const { questions, locked } = data
  const marks = questions.reduce((sum, q) => sum + q.marks, 0)
  const download = () => downloadFile(`/exams/timetable/${exam.id}/questions/template/`, { file: 'xlsx' }, `${exam.code}-questions.xlsx`)
    .catch(async (err) => setActionError(await blobErrorMessage(err)))
  const remove = async () => {
    try {
      await api.delete(`/exams/questions/${removing.id}/`)
      setRemoving(null)
      reload()
    } catch (err) {
      setActionError(errorMessage(err))
      setRemoving(null)
    }
  }

  return (
    <div className="stack-lg">
      {locked && <Alert tone="info">The exam has started, so its questions are locked.</Alert>}
      <Alert onClose={() => setActionError('')}>{actionError}</Alert>
      <Alert tone="success" onClose={() => setImported('')}>{imported}</Alert>
      <Card title="Settings"><SettingsForm exam={exam} total={questions.length} locked={locked} onSaved={onExamChange} /></Card>
      <Card
        title={`Questions (${questions.length}) · ${marks} mark${marks === 1 ? '' : 's'}`}
        action={
          <span className="row-actions">
            {questions.length > 0 && <button className="btn btn-ghost btn-sm" onClick={download}><Icon name="download" size={14} /> Download</button>}
            {!locked && <button className="btn btn-ghost btn-sm" onClick={() => setImporting(true)}><Icon name="register" size={14} /> Import from file</button>}
            {!locked && <button className="btn btn-primary btn-sm" onClick={() => setEditing('new')}><Icon name="plus" size={14} /> Add question</button>}
          </span>
        }
      >
        {questions.length === 0 ? (
          <EmptyState icon="register" title="No questions yet">
            Add multiple-choice or true/false questions one at a time, or import a whole bank from a CSV or Excel file.
            Scores are marked automatically and scaled to 70.
          </EmptyState>
        ) : (
          <ol className="question-list">
            {questions.map((q) => (
              <li key={q.id}>
                <div className="question-list-head">
                  <p className="question-text">{q.text}</p>
                  <span className="muted small nowrap">{q.marks} mark{q.marks === 1 ? '' : 's'}</span>
                  {!locked && (
                    <span className="row-actions">
                      <button className="link-button" onClick={() => setEditing(q)}>Edit</button>
                      <button className="link-button link-danger" onClick={() => setRemoving(q)}>Delete</button>
                    </span>
                  )}
                </div>
                <ul className="answer-key">
                  {q.choices.map((c, i) => (
                    <li key={c.id} className={c.is_correct ? 'is-correct' : ''}>
                      <span className="choice-letter">{LETTERS[i]}</span> {c.text} {c.is_correct && <Icon name="check" size={14} />}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        )}
      </Card>
      {editing && (
        <QuestionModal
          examId={exam.id}
          question={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); reload() }}
        />
      )}
      {importing && (
        <ImportQuestionsModal
          exam={exam}
          existing={questions.length}
          onClose={() => setImporting(false)}
          onSaved={(result) => {
            setImporting(false)
            setImported(`Imported ${result.valid} question${result.valid === 1 ? '' : 's'}. The exam now has ${result.total}.`)
            reload()
            onExamChange()
          }}
        />
      )}
      {removing && (
        <Modal
          title="Delete this question?"
          onClose={() => setRemoving(null)}
          footer={<><button className="btn btn-ghost" onClick={() => setRemoving(null)}>Cancel</button><button className="btn btn-danger" onClick={remove}>Delete</button></>}
        >
          <p>{removing.text}</p>
        </Modal>
      )}
    </div>
  )
}
