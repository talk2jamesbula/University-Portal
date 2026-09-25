import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { RESEARCH } from '../content'
import PageHero from './PageHero'

export default function Research() {
  return (
    <>
      <PageHero kicker="Research" title="Research & innovation">{RESEARCH.intro}</PageHero>
      <section className="site-section">
        <div className="site-container">
          <h2>Research centres and groups</h2>
          <div className="site-programme-grid">
            {RESEARCH.centres.map(([name, text, dept]) => (
              <div key={name} className="site-programme-card site-static-card">
                <Icon name="flask" size={24} />
                <h3>{name}</h3>
                <p>{text}</p>
                <div className="site-programme-meta"><span><Icon name="building" size={14} /> {dept}</span></div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="site-section site-section-alt">
        <div className="site-container site-two-col">
          <div>
            <h2>Supporting our researchers</h2>
            <ul className="site-checklist">
              {RESEARCH.support.map((item) => <li key={item}><Icon name="check" size={16} /> {item}</li>)}
            </ul>
          </div>
          <div className="site-panel">
            <h3>Research news</h3>
            <p>Grants, publications and discoveries are reported in our news.</p>
            <Link to="/news" className="site-more">Read the latest <Icon name="arrowRight" size={14} /></Link>
          </div>
        </div>
      </section>
    </>
  )
}
