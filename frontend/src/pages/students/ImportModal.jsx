import { useRef, useState } from 'react'
import api, { blobErrorMessage, downloadFile, errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Modal } from '../../components/ui'

/** Save the one-time login details as a CSV on the Registry's computer. */
function downloadCredentials(created) {
  const rows = [['Name', 'Matric number', 'Email', 'Temporary password'], ...created.map((c) => [c.name, c.matric_number, c.email, c.temporary_password])]
  const csv = rows.map((r) => r.map((v) => `"${String(v ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
  const href = URL.createObjectURL(new Blob(['﻿', csv], { type: 'text/csv' }))
  const link = document.createElement('a')
  link.href = href
  link.download = 'student-login-details.csv'
  link.click()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

/**
 * Import students from CSV or Excel: check the file first (nothing is saved), fix any errors, then import.
 * Nothing is imported unless every row is valid.
 */
export default function ImportModal({ onClose, onImported }) {
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [check, setCheck] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const send = async (dryRun) => {
    setBusy(dryRun ? 'check' : 'import')
    setError('')
    const body = new FormData()
    body.append('file', file)
    body.append('dry_run', dryRun ? 'true' : '')
    try {
      const { data } = await api.post('/students/import/', body)
      if (dryRun || data.errors.length) setCheck(data)
      else {
        setResult(data)
        onImported()
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy('')
    }
  }
  const template = (fmt) => downloadFile('/students/import-template/', { file: fmt }, `student-import-template.${fmt}`)
    .catch(async (err) => setError(await blobErrorMessage(err)))

  if (result) {
    return (
      <Modal title="Upload complete" onClose={onClose} footer={<button className="btn btn-primary" onClick={onClose}>Done</button>}>
        <div className="stack">
          <Alert tone="success">{result.created.length} students were imported.</Alert>
          <p className="muted">
            Each student has a temporary password. Download the login details now: they are shown only once. Keep the file safe
            and delete it after you have given students their details.
          </p>
          <button className="btn btn-primary align-start" onClick={() => downloadCredentials(result.created)}>
            <Icon name="download" size={16} /> Download login details (CSV)
          </button>
        </div>
      </Modal>
    )
  }

  const ready = check && check.errors.length === 0
  return (
    <Modal
      wide
      title="Bulk upload students"
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          {ready
            ? <button className="btn btn-primary" onClick={() => send(false)} disabled={Boolean(busy)}>{busy === 'import' ? 'Importing…' : `Import ${check.valid} students`}</button>
            : <button className="btn btn-primary" onClick={() => send(true)} disabled={!file || Boolean(busy)}>{busy === 'check' ? 'Checking…' : 'Check file'}</button>}
        </>
      }
    >
      <div className="stack">
        <Alert>{error}</Alert>
        <ol className="import-steps">
          <li>
            Download the template and fill in one student per row. Required columns: first name, last name, email, gender,
            programme code, level, entry session and current session. Matric numbers and Student IDs are assigned
            automatically, so there's no column for them.
            <div className="toolbar">
              <button className="btn btn-ghost btn-sm" onClick={() => template('xlsx')}><Icon name="download" size={14} /> Excel template</button>
              <button className="btn btn-ghost btn-sm" onClick={() => template('csv')}><Icon name="download" size={14} /> CSV template</button>
            </div>
          </li>
          <li>
            Choose the file (.xlsx or .csv, up to 2,000 students) and check it. Nothing is saved until every row is valid.
            <div className="file-pick">
              <input ref={input} type="file" accept=".csv,.xlsx" hidden onChange={(e) => { setFile(e.target.files[0] || null); setCheck(null) }} />
              <button className="btn btn-ghost btn-sm" onClick={() => input.current.click()}><Icon name="plus" size={14} /> Choose file</button>
              <span className="muted small">{file ? file.name : 'No file chosen'}</span>
            </div>
          </li>
        </ol>

        {check && (ready ? (
          <Alert tone="success">All {check.rows} rows are valid. Ready to import.</Alert>
        ) : (
          <>
            <Alert>{check.errors.length} of {check.rows} rows have problems. Fix them in the file and check it again.</Alert>
            <div className="import-errors">
              <table className="table table-compact">
                <thead><tr><th>Row</th><th>Name</th><th>Problems</th></tr></thead>
                <tbody>
                  {check.errors.map((r) => (
                    <tr key={r.row}>
                      <td className="num">{r.row}</td>
                      <td>{r.name || <span className="muted">—</span>}</td>
                      <td className="small">
                        {Object.entries(r.errors).map(([field, messages]) => (
                          <div key={field}><strong>{field.replaceAll('_', ' ')}:</strong> {[].concat(messages).join(' ')}</div>
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
