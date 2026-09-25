import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { LIBRARY } from '../content'
import PageHero from './PageHero'

export default function Library() {
  return (
    <>
      <PageHero kicker="Library" title="University Library">{LIBRARY.intro}</PageHero>
      <section className="site-section">
        <div className="site-container site-two-col">
          <div>
            <h2>Services</h2>
            <div className="site-stack">
              {LIBRARY.services.map(([title, text]) => (
                <div key={title} className="site-service">
                  <Icon name="book" size={20} />
                  <div><h3>{title}</h3><p>{text}</p></div>
                </div>
              ))}
            </div>
          </div>
          <aside className="site-panel">
            <h3>Opening hours</h3>
            <dl className="facts">
              {LIBRARY.hours.map(([days, time]) => <Fragment key={days}><dt>{days}</dt><dd>{time}</dd></Fragment>)}
            </dl>
            <p className="muted small">Students renew loans and check fines in the student portal.</p>
            <Link to="/login/student" className="btn btn-primary btn-block">Student Portal</Link>
          </aside>
        </div>
      </section>
    </>
  )
}
