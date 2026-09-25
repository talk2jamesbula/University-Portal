import jsQR from 'jsqr'
import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon'

/** Reads the session and token from an attendance QR link, or null if it isn't one. */
function parseAttendanceLink(text) {
  try {
    const url = new URL(text, window.location.origin)
    const session = Number(url.searchParams.get('s'))
    const token = url.searchParams.get('t')
    return url.pathname.endsWith('/portal/attend') && session && token ? { session, token } : null
  } catch {
    return null
  }
}

/** Camera QR scanner. Calls onScan({ session, token }) once, when it sees an attendance QR code. */
export default function QrScanner({ onScan, onCancel }) {
  const videoRef = useRef(null)
  const supported = Boolean(navigator.mediaDevices?.getUserMedia)
  const [error, setError] = useState(
    supported ? '' : 'This browser cannot use the camera here. Open the portal over HTTPS, or type the 6-digit code instead.',
  )
  const [wrongCode, setWrongCode] = useState(false)

  useEffect(() => {
    let stream
    let timer
    let done = false
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d', { willReadFrequently: true })

    const scan = () => {
      const video = videoRef.current
      if (done || !video) return
      if (video.readyState >= 2 && video.videoWidth) {
        // Downscale large camera frames: faster to decode, and plenty for a QR code on a screen.
        const scale = Math.min(1, 640 / video.videoWidth)
        canvas.width = video.videoWidth * scale
        canvas.height = video.videoHeight * scale
        context.drawImage(video, 0, 0, canvas.width, canvas.height)
        const found = jsQR(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height)
        if (found) {
          const link = parseAttendanceLink(found.data)
          if (link) {
            done = true
            onScan(link)
            return
          }
          setWrongCode(true)
        }
      }
      timer = setTimeout(scan, 200)
    }

    if (!supported) return undefined
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then((s) => {
        stream = s
        if (done || !videoRef.current) return s.getTracks().forEach((t) => t.stop())
        videoRef.current.srcObject = s
        videoRef.current.play().catch(() => {})
        scan()
      })
      .catch((err) => {
        setError(
          err?.name === 'NotAllowedError'
            ? 'Camera access was blocked. Allow the camera for this site in your browser settings, or type the 6-digit code instead.'
            : 'No camera could be started. Type the 6-digit code shown under the QR code instead.',
        )
      })

    return () => {
      done = true
      clearTimeout(timer)
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [onScan, supported])

  return (
    <div className="qr-scanner">
      {error ? (
        <div className="callout callout-danger"><Icon name="alert" /><span>{error}</span></div>
      ) : (
        <div className="qr-viewfinder">
          <video ref={videoRef} muted playsInline aria-label="Camera view" />
          <span className="qr-frame" aria-hidden="true" />
        </div>
      )}
      <p className="muted small">
        {wrongCode ? "That QR code isn't a class attendance code. Point the camera at the QR code on your lecturer's screen."
          : "Point your camera at the QR code on your lecturer's screen."}
      </p>
      <button type="button" className="btn btn-ghost" onClick={onCancel}>Type the code instead</button>
    </div>
  )
}
