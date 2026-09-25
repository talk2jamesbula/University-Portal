import { useState } from 'react'
import { errorMessage, publicApi } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert } from '../../components/ui'
import { SITE } from '../content'
import PageHero from './PageHero'

const TOPICS = [
  ['general', 'General enquiry'], ['admissions', 'Admissions'], ['academic', 'Academic matters'],
  ['finance', 'Fees and payments'], ['technical', 'Portal / technical support'],
]
const place = encodeURIComponent(SITE.mapLocation)
// The keyless Google Maps embed; no API key or billing account needed.
const mapUrl = `https://maps.google.com/maps?q=${place}&z=${SITE.mapZoom}&output=embed`
const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${place}`
const EMPTY = { name: '', email: '', phone: '', topic: 'general', subject: '', message: '', website: '' }

export default function Contact() {
  const [form, setForm] = useState(EMPTY)
  const [status, setStatus] = useState({ tone: 'success', text: '' })
  const [sending, setSending] = useState(false)
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setSending(true)
    try {
      const { data } = await publicApi.post('/contact/', form)
      setStatus({ tone: 'success', text: data.detail })
      setForm(EMPTY)
    } catch (err) {
      const text = err.response?.status === 429
        ? 'You have sent several messages recently. Please try again later or email us.'
        : errorMessage(err)
      setStatus({ tone: 'error', text })
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <PageHero kicker="Contact us" title="Get in touch">
        Questions about admission, programmes, fees or the portal? We're here to help.
      </PageHero>
      <section className="site-section">
        <div className="site-container site-two-col">
          <form className="form site-panel" onSubmit={submit}>
            <h2>Send us a message</h2>
            <Alert tone={status.tone} onClose={() => setStatus({ ...status, text: '' })}>{status.text}</Alert>
            <div className="form-row">
              <label className="field"><span>Full name</span><input value={form.name} onChange={set('name')} required maxLength={120} autoComplete="name" /></label>
              <label className="field"><span>Email</span><input type="email" value={form.email} onChange={set('email')} required autoComplete="email" /></label>
            </div>
            <div className="form-row">
              <label className="field"><span>Phone (optional)</span><input value={form.phone} onChange={set('phone')} maxLength={32} autoComplete="tel" /></label>
              <label className="field"><span>Topic</span>
                <select value={form.topic} onChange={set('topic')}>{TOPICS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              </label>
            </div>
            <label className="field"><span>Subject</span><input value={form.subject} onChange={set('subject')} required maxLength={160} /></label>
            <label className="field"><span>Message</span><textarea rows={6} value={form.message} onChange={set('message')} required maxLength={5000} /></label>
            {/* Hidden from people; bots that fill it in are rejected. */}
            <input className="site-honeypot" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} aria-hidden="true" />
            <div><button className="btn btn-primary" disabled={sending}>{sending ? 'Sending…' : 'Send message'}</button></div>
          </form>
          <aside className="site-stack">
            <div className="site-panel site-contact-card">
              <h3><Icon name="pin" size={18} /> Visit us</h3>
              <address>{SITE.address.map((line) => <span key={line}>{line}</span>)}</address>
              <h3><Icon name="phone" size={18} /> Call</h3>
              <a href={`tel:${SITE.phone.replace(/\s/g, '')}`}>{SITE.phone}</a>
              <h3><Icon name="mail" size={18} /> Email</h3>
              <a href={`mailto:${SITE.email}`}>{SITE.email}</a>
              <a href={`mailto:${SITE.admissionsEmail}`}>{SITE.admissionsEmail} (Admissions)</a>
              <h3><Icon name="clock" size={18} /> Office hours</h3>
              <p>{SITE.hours}</p>
            </div>
          </aside>
        </div>
      </section>
      <section className="site-section site-section-alt">
        <div className="site-container">
          <div className="site-map-header">
            <div>
              <h2>Find us</h2>
              <p className="muted">{SITE.address.join(', ')}</p>
            </div>
            <a className="btn btn-primary" href={directionsUrl} target="_blank" rel="noreferrer">
              <Icon name="pin" size={16} /> Get directions
            </a>
          </div>
          <div className="site-map">
            <iframe
              title={`Map showing the location of ${SITE.name}`}
              src={mapUrl}
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
              allowFullScreen
            />
          </div>
        </div>
      </section>
    </>
  )
}
