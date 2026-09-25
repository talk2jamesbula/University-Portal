import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Avatar, Badge, Card, PageHeader, Spinner } from '../../components/ui'
import { formatClock, formatDate, formatTime } from '../../utils/format'
import useApi from '../../utils/useApi'
import QrScanner from '../attendance/QrScanner'
import { MODE_TONE, parseCardLink } from './exams'

const SCANNER_TEXT = {
  prompt: "Point the camera at the QR code on the student's exam card.",
  wrong: "That isn't an exam card QR code. Scan the code printed on the card.",
  fallback: 'enter the matric number instead',
  cancel: 'Enter matric number instead',
}

function ExamRow({ exam, student, onAdmitted }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const admit = async () => {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/exams/verify/check-in/', { exam: exam.id, student })
      onAdmitted(exam.id, data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <li className={`verify-exam ${exam.is_today ? 'is-today' : ''} ${exam.eligible ? '' : 'is-blocked'}`}>
      <div className="grow">
        <div className="cell-title">
          {exam.code} <Badge tone={MODE_TONE[exam.mode]}>{exam.mode === 'cbt' ? 'CBT' : 'Paper'}</Badge> {exam.is_today && <Badge tone="blue">Today</Badge>}
        </div>
        <div className="muted small">
          {exam.title} · {formatDate(exam.date, { weekday: 'short', day: 'numeric', month: 'short' })}, {formatTime(exam.start_time)}
        </div>
        <div className="small">{exam.venue ? <>{exam.venue} · seat <strong>{exam.seat_number}</strong></> : <span className="muted">No seat assigned</span>}</div>
        {!exam.eligible && <div className="text-red small">{exam.reasons.join(' ')}</div>}
        {exam.waived && <div className="small">Waiver: {exam.waiver_reason}</div>}
        {error && <div className="text-red small">{error}</div>}
      </div>
      <div className="verify-verdict">
        {exam.eligible ? <span className="verdict verdict-ok">Eligible</span> : <span className="verdict verdict-no">Not eligible</span>}
        {exam.checked_in_at ? (
          <span className="muted small">Admitted {formatClock(exam.checked_in_at)}</span>
        ) : exam.is_today && exam.eligible && (
          <button className="btn btn-primary btn-sm" onClick={admit} disabled={busy}>{busy ? 'Admitting…' : 'Admit to hall'}</button>
        )}
      </div>
    </li>
  )
}

/** Invigilators scan an exam card (or type a matric number) to check who the candidate is and whether they may sit. */
export default function VerifyCard() {
  const [params, setParams] = useSearchParams()
  const [scanning, setScanning] = useState(false)
  const [matric, setMatric] = useState('')
  // Opened from a phone camera scanning the card: /portal/exams/verify?c=<code>
  const [query, setQuery] = useState(() => (params.get('c') ? { code: params.get('c') } : null))
  const { data, error, loading, reload, setData } = useApi(query ? '/exams/verify/' : null, query ?? undefined)
  const result = query ? data : null

  const search = useCallback((q) => {
    setQuery(q)
    reload() // so looking up the same card again fetches fresh eligibility
  }, [reload])

  const onScan = useCallback(({ code }) => {
    setScanning(false)
    search({ code })
  }, [search])

  const next = () => {
    setQuery(null)
    setData(null)
    setMatric('')
    if (params.get('c')) setParams({})
  }

  const admitted = (examId, checkIn) => setData((r) => ({
    ...r,
    exams: r.exams.map((e) => (e.id === examId ? { ...e, checked_in_at: checkIn.checked_in_at } : e)),
  }))

  return (
    <div className="stack-lg verify-page">
      <PageHeader title="Verify exam card" subtitle="Check a candidate's identity and eligibility, then admit them to the hall" />
      {!query && (
        <Card>
          {scanning ? (
            <QrScanner onScan={onScan} onCancel={() => setScanning(false)} parse={parseCardLink} text={SCANNER_TEXT} />
          ) : (
            <div className="stack">
              <button className="btn btn-primary btn-lg" onClick={() => setScanning(true)}><Icon name="camera" size={18} /> Scan exam card</button>
              <div className="divider-text"><span>or</span></div>
              <form className="lookup-form" onSubmit={(e) => { e.preventDefault(); if (matric.trim()) search({ matric: matric.trim() }) }}>
                <input value={matric} onChange={(e) => setMatric(e.target.value)} placeholder="Matric number, e.g. BU/25/CSC/0005" aria-label="Matric number" />
                <button className="btn btn-ghost">Look up</button>
              </form>
            </div>
          )}
        </Card>
      )}
      {query && loading && <Spinner label="Checking…" />}
      {query && !loading && error && (
        <div className="stack">
          <div className="callout callout-danger"><Icon name="alert" /><span>{error}</span></div>
          <button className="btn btn-ghost" onClick={next}>Try again</button>
        </div>
      )}
      {result && !loading && !error && (
        <>
          <Card>
            <div className="verify-student">
              <Avatar name={result.student.name} src={result.student.avatar_url} size={112} />
              <div>
                <h2>{result.student.name}</h2>
                <div className="mono">{result.student.matric_number}</div>
                <div className="muted">{result.student.programme}{result.student.level && ` · ${result.student.level} Level`}</div>
                <div className="muted small">Card {result.card_number} · {result.semester.name}</div>
              </div>
            </div>
            {!result.student.avatar_url && (
              <p className="text-amber small">No photo on record: check the student ID card carefully.</p>
            )}
          </Card>
          <Card title="Examinations" padded={false}>
            {result.exams.length === 0 ? <p className="muted list-padded">No examinations on the timetable for this student.</p> : (
              <ul className="verify-exams">
                {[...result.exams].sort((a, b) => b.is_today - a.is_today).map((e) => (
                  <ExamRow key={e.id} exam={e} student={result.student.id} onAdmitted={admitted} />
                ))}
              </ul>
            )}
          </Card>
          <button className="btn btn-primary btn-lg" onClick={next}><Icon name="qr" size={18} /> Next candidate</button>
        </>
      )}
    </div>
  )
}
