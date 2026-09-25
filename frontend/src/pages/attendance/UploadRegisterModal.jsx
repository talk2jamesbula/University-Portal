import { useRef, useState } from 'react'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Modal } from '../../components/ui'
import { formatDate, formatTime, localToday } from '../../utils/format'

const FIELD = { date: 'Date', start_time: 'Class time', matric_number: 'Matric no.', status: 'Status' }

function ClassesTable({ sessions, close }) {
  return (
    <table className="table table-compact">
      <thead>
        <tr>
          <th>Class</th><th className="num">Present</th><th className="num">Late</th><th className="num">Excused</th>
          <th className="num">Absent</th><th className="num">Not in file</th><th>Session</th>
        </tr>
      </thead>
      <tbody>
        {sessions.map((s) => (
          <tr key={`${s.date}-${s.start_time}`}>
            <td className="cell-title">{formatDate(s.date, { weekday: 'short', day: 'numeric', month: 'short' })} · {formatTime(s.start_time)}</td>
            <td className="num">{s.present}</td>
            <td className="num">{s.late}</td>
            <td className="num">{s.excused}</td>
            <td className="num">{s.absent}</td>
            <td className="num">{s.not_in_file ? <span title={close ? 'Will be marked absent' : 'Left unmarked'}>{s.not_in_file}{close ? ' → absent' : ''}</span> : 0}</td>
            <td>
              {s.session_status === 'new' ? <Badge tone="blue">New</Badge>
                : s.session_status === 'closed' ? <Badge tone="green">Closed</Badge>
                  : <Badge>{s.session_status === 'open' ? 'Open' : 'Scheduled'}</Badge>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/**
 * Upload paper registers for a course. The file is checked first (nothing is saved); once every row is
 * valid, the attendance is recorded, each class is matched to its session (or one is created) and, by
 * default, closed with everyone not on the register marked absent.
 */
export default function UploadRegisterModal({ offering, onClose, onSaved }) {
  const input = useRef(null)
  const [day, setDay] = useState(localToday())
  const [file, setFile] = useState(null)
  const [close, setClose] = useState(true)
  const [check, setCheck] = useState(null)
  const [saved, setSaved] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const base = `/attendance/offerings/${offering.id}`

  const send = async (dryRun) => {
    setBusy(dryRun ? 'check' : 'save')
    setError('')
    const body = new FormData()
    body.append('file', file)
    body.append('dry_run', dryRun ? 'true' : 'false')
    body.append('close', close ? 'true' : 'false')
    try {
      const { data } = await api.post(`${base}/upload/`, body)
      if (data.saved) {
        setSaved(data)
        onSaved()
      } else setCheck(data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy('')
    }
  }
  const template = (fmt) => downloadFile(`${base}/upload-template/`, { file: fmt, date: day }, `${offering.code}-register.${fmt}`)
    .catch(async (err) => setError(await blobErrorMessage(err)))
  const pick = (f) => { setFile(f || null); setCheck(null) }

  if (saved) {
    return (
      <Modal wide title="Register uploaded" onClose={onClose} footer={<button className="btn btn-primary" onClick={onClose}>Done</button>}>
        <div className="stack">
          <Alert tone="success">
            {saved.valid} attendance records saved for {saved.sessions.length} class{saved.sessions.length === 1 ? '' : 'es'}.
            {close ? ' Students not on the register were marked absent and notified.' : ''}
          </Alert>
          <ClassesTable sessions={saved.sessions} close={close} />
        </div>
      </Modal>
    )
  }

  const ready = check && check.errors.length === 0
  return (
    <Modal
      wide
      title={`Upload attendance register · ${offering.code}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          {ready
            ? <button className="btn btn-primary" onClick={() => send(false)} disabled={Boolean(busy)}>{busy === 'save' ? 'Saving…' : `Save ${check.valid} records`}</button>
            : <button className="btn btn-primary" onClick={() => send(true)} disabled={!file || Boolean(busy)}>{busy === 'check' ? 'Checking…' : 'Check file'}</button>}
        </>
      }
    >
      <div className="stack">
        <Alert>{error}</Alert>
        <ol className="import-steps">
          <li>
            <p>
              Download the class list as a register and fill in each student's status: <strong>P</strong> (present),{' '}
              <strong>L</strong> (late), <strong>E</strong> (excused) or <strong>A</strong> (absent). Add rows for more
              classes by changing the date. A <em>start_time</em> column is optional; without it the course's usual time is used.
            </p>
            <div className="toolbar">
              <label className="field field-inline"><span>Class date</span><input type="date" value={day} max={localToday()} onChange={(e) => setDay(e.target.value)} /></label>
              <button className="btn btn-ghost btn-sm" onClick={() => template('xlsx')}><Icon name="download" size={14} /> Excel register</button>
              <button className="btn btn-ghost btn-sm" onClick={() => template('csv')}><Icon name="download" size={14} /> CSV register</button>
            </div>
          </li>
          <li>
            <p>Choose the completed file (.xlsx or .csv) and check it. Nothing is saved until every row is valid.</p>
            <div className="file-pick">
              <input ref={input} type="file" accept=".csv,.xlsx" hidden onChange={(e) => pick(e.target.files[0])} />
              <button className="btn btn-ghost btn-sm" onClick={() => input.current.click()}><Icon name="plus" size={14} /> Choose file</button>
              <span className="muted small">{file ? file.name : 'No file chosen'}</span>
            </div>
            <label className="check-inline declaration">
              <input type="checkbox" checked={close} onChange={(e) => { setClose(e.target.checked); setCheck(null) }} />
              Close each class afterwards: students not in the file are marked absent and notified (recommended for complete registers).
            </label>
          </li>
        </ol>

        {check && (ready ? (
          <>
            <Alert tone="success">All {check.rows} rows are valid: {check.sessions.length} class{check.sessions.length === 1 ? '' : 'es'}. Check the totals, then save.</Alert>
            <ClassesTable sessions={check.sessions} close={close} />
          </>
        ) : (
          <>
            <Alert>{check.errors.length} of {check.rows} rows have problems. Fix them in the file and check it again.</Alert>
            <div className="import-errors">
              <table className="table table-compact">
                <thead><tr><th>Row</th><th>Matric no.</th><th>Problems</th></tr></thead>
                <tbody>
                  {check.errors.map((r) => (
                    <tr key={r.row}>
                      <td className="num">{r.row}</td>
                      <td className="mono small">{r.matric_number || '—'}</td>
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
        <p className="muted small">Classes that are already closed can't be changed here; request a correction from the session page instead.</p>
      </div>
    </Modal>
  )
}
