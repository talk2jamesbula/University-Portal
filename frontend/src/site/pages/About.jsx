import { publicApi } from '../../api/client'
import { Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import { ABOUT, SITE } from '../content'
import { PHOTOS } from '../photos'
import StaffPortrait from '../StaffPortrait'
import PageHero from './PageHero'

function PeopleGroup({ title, intro, people, size }) {
  if (!people.length) return null
  return (
    <div className="site-leadership-group">
      <h2>{title}</h2>
      {intro && <p className="muted">{intro}</p>}
      <div className={`site-people site-people-${size}`}>
        {people.map((p) => (
          <figure key={`${p.role}-${p.name}`} className="site-person">
            <StaffPortrait person={p} size={size} />
            <figcaption>
              <strong>{p.name}</strong>
              <span>{p.role}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  )
}

/** University leadership, straight from current role appointments and staff profile photos. */
function Leadership() {
  const { data } = useApi('/leadership/', undefined, publicApi)
  return (
    <section className="site-section">
      <div className="site-container site-stack">
        {!data ? <Spinner /> : (
          <>
            <PeopleGroup title="Principal officers" people={data.principal_officers} size="lg" />
            <PeopleGroup title="Deans of faculties" people={data.deans} size="md" />
            <PeopleGroup title="Heads of department" people={data.heads_of_department} size="sm" />
          </>
        )}
      </div>
    </section>
  )
}

export default function About() {
  return (
    <>
      <PageHero kicker="About the University" title={`About ${SITE.name}`}>{ABOUT.intro}</PageHero>
      <section className="site-section">
        <div className="site-container site-two-col">
          <div className="site-prose">
            <h2>Our story</h2>
            {ABOUT.history.map((p) => <p key={p}>{p}</p>)}
            <img className="site-photo" src={PHOTOS.lecture.src} alt={PHOTOS.lecture.alt} loading="lazy" />
          </div>
          <div className="site-panel">
            <h3>Mission</h3>
            <p>{ABOUT.mission}</p>
            <h3>Vision</h3>
            <p>{ABOUT.vision}</p>
            <h3>Motto</h3>
            <p>{SITE.motto}</p>
          </div>
        </div>
      </section>
      <section className="site-section site-section-alt">
        <div className="site-container">
          <h2>Our core values</h2>
          <div className="site-highlights">
            {ABOUT.values.map(([title, text]) => (
              <div key={title} className="site-highlight"><h3>{title}</h3><p>{text}</p></div>
            ))}
          </div>
        </div>
      </section>
      <Leadership />
    </>
  )
}
