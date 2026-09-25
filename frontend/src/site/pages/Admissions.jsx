import { Link } from 'react-router-dom'
import { formatDate, formatMoney } from '../../utils/format'
import useApi from '../../utils/useApi'
import Icon from '../../components/Icon'
import { ADMISSIONS, SITE } from '../content'
import { PHOTOS } from '../photos'
import PageHero from './PageHero'

export default function Admissions() {
  const { data } = useApi('/admissions/cycle/')
  const cycle = data?.cycle
  return (
    <>
      <PageHero kicker="Admissions" title="Study with us">{ADMISSIONS.intro}</PageHero>
      <section className="site-section">
        <div className="site-container">
          <div className="site-photo-banner">
            <img src={PHOTOS.campusLife.src} alt={PHOTOS.campusLife.alt} loading="lazy" />
            <p>Join a community of curious, ambitious students from across Nigeria.</p>
          </div>
          <h2>Entry requirements</h2>
          <div className="site-routes">
            {ADMISSIONS.routes.map((route) => (
              <div key={route.title} className="site-panel">
                <h3>{route.title}</h3>
                <ul className="site-checklist">
                  {route.points.map((point) => <li key={point}><Icon name="check" size={16} /> {point}</li>)}
                </ul>
              </div>
            ))}
          </div>
          <p className="muted">Some programmes have extra subject requirements. See the <Link to="/programmes" className="link">programme pages</Link> or contact the Admissions Office.</p>
        </div>
      </section>
      <section className="site-section site-section-alt">
        <div className="site-container">
          <h2>How to apply</h2>
          {cycle?.is_open ? (
            <div className="site-panel apply-panel">
              <div>
                <h3>Applications for the {cycle.session} session are open</h3>
                <p className="muted">
                  Apply by <strong>{formatDate(cycle.closes_on)}</strong>. The application fee is <strong>{formatMoney(cycle.application_fee)}</strong>
                  {cycle.min_utme_score ? <>, and the minimum UTME score is <strong>{cycle.min_utme_score}</strong></> : null}.
                </p>
              </div>
              <div className="toolbar">
                <Link to="/apply" className="btn btn-primary">Apply now</Link>
                <Link to="/login/applicant" className="btn btn-ghost">Continue an application</Link>
              </div>
            </div>
          ) : (
            <p className="muted">The online application portal opens when applications for the next session begin; watch <Link to="/news" className="link">News</Link> for dates.</p>
          )}
          <ol className="site-steps">
            {ADMISSIONS.steps.map(([title, text], i) => (
              <li key={title}><span>{i + 1}</span><div><strong>{title}</strong><p>{text}</p></div></li>
            ))}
          </ol>
        </div>
      </section>
      <section className="site-cta">
        <div className="site-container site-cta-inner">
          <div>
            <h2>Questions about admission?</h2>
            <p>Email <a href={`mailto:${SITE.admissionsEmail}`}>{SITE.admissionsEmail}</a> or send us a message, {SITE.hours.toLowerCase()}.</p>
          </div>
          <Link to="/contact" className="btn btn-gold">Contact Admissions</Link>
        </div>
      </section>
    </>
  )
}
