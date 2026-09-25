import { useRef, useState } from 'react'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Modal } from '../../components/ui'

const LETTERS = 'ABCDEF'
const FIELD = { question: 'Question', options: 'Options', answer: 'Answer', marks: 'Marks' }

function Preview({ questions, more }) {
  return (
    <ol className="question-list">
      {questions.map((q) => (
        <li key={q.text}>
          <div className="question-list-head">
            <p className="question-text">{q.text}</p>
            <span className="muted small nowrap">{q.marks} mark{q.marks === 1 ? '' : 's'}</span>
          </div>
          <ul className="answer-key">
            {q.choices.map((c, i) => (
              <li key={c} className={i === q.correct ? 'is-correct' : ''}>
                <span className="choice-letter">{LETTERS[i]}</span> {c} {i === q.correct && <Icon name="check" size={14} />}
              </li>
            ))}
          </ul>
        </li>
      ))}
      {more > 0 && <p className="muted small">…and {more} more.</p>}
    </ol>
  )
}

/**
 * Import CBT questions from a CSV or Excel file. The file is checked first (nothing is saved); once
 * every row is valid the questions are added to the exam's, or replace them.
 */
export default function ImportQuestionsModal({ exam, existing, onClose, onSaved }) {
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [replace, setReplace] = useState(false)
  const [check, setCheck] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const base = `/exams/timetable/${exam.id}/questions`

  const send = async (dryRun) => {
    setBusy(dryRun ? 'check' : 'save')
    setError('')
    const body = new FormData()
    body.append('file', file)
    body.append('dry_run', dryRun ? 'true' : 'false')
    body.append('replace', replace ? 'true' : 'false')
    try {
      const { data } = await api.post(`${base}/upload/`, body)
      if (data.saved) onSaved(data)
      else setCheck(data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy('')
    }
  }
  const template = (fmt) => downloadFile(`${base}/template/`, { file: fmt }, `${exam.code}-questions.${fmt}`)
    .catch(async (err) => setError(await blobErrorMessage(err)))
  const pick = (f) => { setFile(f || null); setCheck(null) }

  const ready = check && check.errors.length === 0
  return (
    <Modal
      wide
      title={`Import questions · ${exam.code}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          {ready
            ? (
              <button className="btn btn-primary" onClick={() => send(false)} disabled={Boolean(busy)}>
                {busy === 'save' ? 'Importing…' : `${replace && existing ? 'Replace with' : 'Import'} ${check.valid} question${check.valid === 1 ? '' : 's'}`}
              </button>
            )
            : <button className="btn btn-primary" onClick={() => send(true)} disabled={!file || Boolean(busy)}>{busy === 'check' ? 'Checking…' : 'Check file'}</button>}
        </>
      }
    >
      <div className="stack">
        <Alert>{error}</Alert>
        <ol className="import-steps">
          <li>
            <p>
              Put one question per row: the <strong>question</strong>, two to six options (<strong>option_a</strong> to{' '}
              <strong>option_f</strong>), the <strong>answer</strong> (the correct option's letter, e.g. <em>B</em>, or its
              exact text) and, optionally, the <strong>marks</strong> (1 if blank). For true/false, use True and False as
              options A and B.
            </p>
            <div className="toolbar">
              <button className="btn btn-ghost btn-sm" onClick={() => template('xlsx')}><Icon name="download" size={14} /> Excel template</button>
              <button className="btn btn-ghost btn-sm" onClick={() => template('csv')}><Icon name="download" size={14} /> CSV template</button>
            </div>
            {existing > 0 && <p className="muted small">The template holds this exam's {existing} current questions, so you can edit them and upload the file again.</p>}
          </li>
          <li>
            <p>Choose the completed file (.xlsx or .csv) and check it. Nothing is saved until every row is valid.</p>
            <div className="file-pick">
              <input ref={input} type="file" accept=".csv,.xlsx" hidden onChange={(e) => pick(e.target.files[0])} />
              <button className="btn btn-ghost btn-sm" onClick={() => input.current.click()}><Icon name="plus" size={14} /> Choose file</button>
              <span className="muted small">{file ? file.name : 'No file chosen'}</span>
            </div>
            {existing > 0 && (
              <label className="check-inline declaration">
                <input type="checkbox" checked={replace} onChange={(e) => { setReplace(e.target.checked); setCheck(null) }} />
                Replace the {existing} existing question{existing === 1 ? '' : 's'} instead of adding to them.
              </label>
            )}
          </li>
        </ol>

        {check && (ready ? (
          <>
            <Alert tone="success">
              All {check.rows} questions are valid ({check.marks} marks).
              {check.replacing ? ` They will replace the ${check.replacing} existing questions.` : ''} The first few:
            </Alert>
            <Preview questions={check.preview} more={check.valid - check.preview.length} />
          </>
        ) : (
          <>
            <Alert>{check.errors.length} of {check.rows} rows have problems. Fix them in the file and check it again.</Alert>
            <div className="import-errors">
              <table className="table table-compact">
                <thead><tr><th>Row</th><th>Question</th><th>Problems</th></tr></thead>
                <tbody>
                  {check.errors.map((r) => (
                    <tr key={r.row}>
                      <td className="num">{r.row}</td>
                      <td className="small">{r.question || <span className="muted">—</span>}</td>
                      <td className="small">
                        {Object.entries(r.errors).map(([field, messages]) => (
                          <div key={field}><strong>{FIELD[field] ?? field}:</strong> {[].concat(messages).join(' ')}</div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ))}
      </div>
    </Modal>
  )
}
