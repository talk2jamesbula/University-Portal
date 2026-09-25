import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api, { errorMessage } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Card, PageHeader } from '../../components/ui'
import QrScanner from './QrScanner'

/** A random id kept on this device, so one phone checking in several students can be flagged. */
function deviceId() {
  try {
    let id = localStorage.getItem('attendance-device')
    if (!id) {
      // randomUUID needs HTTPS (or localhost); fall back on plain-HTTP campus networks
      id = crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
      localStorage.setItem('attendance-device', id)
    }
    return id
  } catch {
    return ''
  }
}

/**
 * Student check-in: scan the lecturer's QR code with the in-page camera scanner (or the phone's own
 * camera, which opens this page with ?s=<session>&t=<token>), or type the 6-digit code shown in class.
 */
export default function CheckIn() {
  const [params, setParams] = useSearchParams()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [scanning, setScanning] = useState(false)
  const scanned = useRef(false)

  const submit = useCallback(async (payload) => {
    setBusy(true)
    setError('')
    try {
      const { data } = await api.post('/attendance/check-in/', { ...payload, device_id: deviceId() })
      setResult(data)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }, [])

  const onScan = useCallback((link) => {
    setScanning(false)
    submit(link)
  }, [submit])

  useEffect(() => {
    const session = params.get('s')
    const token = params.get('t')
    if (!session || !token || scanned.current) return
    scanned.current = true // React's strict mode runs effects twice; scan once
    setParams({}, { replace: true }) // the link stops working in seconds, so don't leave it in history
    submit({ session: Number(session), token })
  }, [params, setParams, submit])

  const onSubmit = (e) => {
    e.preventDefault()
    if (!/^\d{6}$/.test(code)) return setError('Enter the 6-digit code shown in class.')
    submit({ code })
  }

  return (
    <div className="stack-lg checkin-page">
      <PageHeader title="Class check-in" subtitle="Scan the QR code on the lecturer's screen, or type the code shown under it." />
      {result ? (
        <Card>
          <div className="checkin-result">
            <span className={`checkin-icon ${result.status === 'late' ? 'tone-amber' : 'tone-green'}`}><Icon name="check" size={32} /></span>
            <h2>{result.message}</h2>
            <p className="muted">
              {result.created ? `Recorded as ${result.status_label.toLowerCase()}.` : 'Your attendance was already recorded; nothing was changed.'}
            </p>
            <div className="toolbar">
              <Link to="/portal/attendance" className="btn btn-primary">View my attendance</Link>
              <button className="btn btn-ghost" onClick={() => { setResult(null); setCode('') }}>Check in to another class</button>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          {scanning ? <QrScanner onScan={onScan} onCancel={() => setScanning(false)} /> : (
          <form className="form" onSubmit={onSubmit}>
            <Alert>{error}</Alert>
            {busy && !code && <p className="muted">Checking you in…</p>}
            <button type="button" className="btn btn-primary btn-lg" onClick={() => { setError(''); setScanning(true) }} disabled={busy}>
              <Icon name="qr" size={20} /> Scan QR code
            </button>
            <div className="divider-text"><span>or enter the code</span></div>
            <label className="field">
              <span>Attendance code</span>
              <input
                className="code-input"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="000000"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                aria-describedby="code-help"
              />
            </label>
            <p id="code-help" className="muted small">The code changes every few seconds. Enter the one on screen now.</p>
            <button className="btn btn-ghost" disabled={busy || code.length !== 6}>
              <Icon name="check" size={16} /> {busy ? 'Checking in…' : 'Check in'}
            </button>
          </form>
          )}
        </Card>
      )}
    </div>
  )
}
