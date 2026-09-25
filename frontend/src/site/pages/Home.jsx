import { Link } from 'react-router-dom'
import { publicApi } from '../../api/client'
import Icon from '../../components/Icon'
import { formatDate, parseDate } from '../../utils/format'
import useApi from '../../utils/useApi'
import { ABOUT, SITE } from '../content'
import { PHOTOS } from '../photos'

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

const HIGHLIGHTS = [
  ['cap', 'Accredited programmes', 'NUC-accredited undergraduate degrees across four faculties.'],
  ['flask', 'Research that matters', 'Centres tackling health, energy, technology and enterprise.'],
  ['book', 'Modern learning', 'An ICT and e-learning centre, well-equipped laboratories and a digital library.'],
  ['users', 'Student support', 'Academic advisers, counselling, and a portal for every stage of your studies.'],
]

export function NewsCard({ item }) {
  return (
    <article className="site-news-card">
      <div className="site-news-date">{formatDate(item.created_at)}</div>
      <h3><Link to={`/news/${item.id}`}>{item.title}</Link></h3>
      <p>{item.summary}</p>
      <Link to={`/news/${item.id}`} className="site-more">Read more <Icon name="arrowRight" size={14} /></Link>
    </article>
  )
}

export function EventItem({ event, showDescription = false }) {
  const d = parseDate(event.starts_at)
  return (
    <li className="site-event">
      <div className="site-event-date">
        <span>{d.toLocaleString(undefined, { month: 'short' })}</span>
        <strong>{d.getDate()}</strong>
      </div>
      <div>
        <h3>{event.title}</h3>
        <p>{event.category_label} · {event.location} · {d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</p>
        {showDescription && event.description && <p className="site-event-desc">{event.description}</p>}
      </div>
    </li>
  )
}

export default function Home() {
  const { data } = useApi('/overview/', undefined, publicApi)
  const { data: faculties } = useApi('/faculties/', undefined, publicApi)
  const stats = data?.stats

  return (
    <>
      <section className="site-hero site-hero-photo" style={{ '--hero-image': `url(${PHOTOS.campusLife.src})` }}>
        <div className="site-container site-hero-inner">
          <p className="site-kicker">{data?.current_session ? `${data.current_session} academic session` : 'Welcome'}</p>
          <h1>Learn, discover and lead at {SITE.name}</h1>
          <p className="site-lead">{ABOUT.intro}</p>
          <div className="site-hero-actions">
            <Link to="/programmes" className="btn btn-gold">Explore programmes</Link>
            <Link to="/admissions" className="btn btn-outline-light">Admissions</Link>
          </div>
        </div>
        <div className="site-container">
          <dl className="site-stats">
            <div><dt>Faculties</dt><dd>{stats?.faculties ?? '—'}</dd></div>
            <div><dt>Departments</dt><dd>{stats?.departments ?? '—'}</dd></div>
            <div><dt>Degree programmes</dt><dd>{stats?.programmes ?? '—'}</dd></div>
            <div><dt>Courses taught</dt><dd>{stats?.courses ?? '—'}</dd></div>
          </dl>
        </div>
      </section>

      <section className="site-section">
        <div className="site-container site-highlights">
          {HIGHLIGHTS.map(([icon, title, text]) => (
            <div key={title} className="site-highlight">
              <span className="site-highlight-icon"><Icon name={icon} size={22} /></span>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="site-section">
        <div className="site-container">
          <div className="site-section-head">
            <div><p className="site-kicker">Student life</p><h2>Learning, living and growing together</h2></div>
          </div>
          <div className="site-mosaic">
            {[
              [PHOTOS.lecture, 'In the lecture hall', 'Small-group tutorials and lectures led by committed academics.'],
              [PHOTOS.digitalLearning, 'Digital learning', 'Computer labs, e-learning and computer-based examinations.'],
              [PHOTOS.culture, 'Culture and community', 'Cultural festivals, sports, clubs and student societies.'],
            ].map(([photo, title, text]) => (
              <figure key={title} className="site-mosaic-item">
                <img src={photo.src} alt={photo.alt} loading="lazy" />
                <figcaption><strong>{title}</strong><span>{text}</span></figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section className="site-section site-section-alt">
        <div className="site-container">
          <div className="site-section-head">
            <div>
              <p className="site-kicker">Academics</p>
              <h2>Our faculties</h2>
            </div>
            <Link to="/faculties" className="site-more">All faculties & departments <Icon name="arrowRight" size={14} /></Link>
          </div>
          <div className="site-faculty-grid">
            {faculties?.map((f) => (
              <Link key={f.code} to={`/faculties#${f.code}`} className="site-faculty-card">
                <Icon name="building" size={24} />
                <h3>{f.name}</h3>
                <p>{f.departments.map((d) => d.name).join(' · ')}</p>
                <span className="site-more">{plural(f.departments.reduce((n, d) => n + d.programmes.length, 0), 'programme')} <Icon name="arrowRight" size={14} /></span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="site-section">
        <div className="site-container site-news-events">
          <div>
            <div className="site-section-head">
              <div><p className="site-kicker">Latest</p><h2>News & announcements</h2></div>
              <Link to="/news" className="site-more">All news <Icon name="arrowRight" size={14} /></Link>
            </div>
            <div className="site-news-grid">
              {data?.news.map((item) => <NewsCard key={item.id} item={item} />)}
            </div>
          </div>
          <aside>
            <div className="site-section-head">
              <div><p className="site-kicker">Calendar</p><h2>Upcoming events</h2></div>
            </div>
            <ul className="site-events">
              {data?.events.map((e) => <EventItem key={e.id} event={e} />)}
            </ul>
            <Link to="/events" className="site-more">All events <Icon name="arrowRight" size={14} /></Link>
          </aside>
        </div>
      </section>

      <section className="site-cta">
        <div className="site-container site-cta-inner">
          <div>
            <h2>Ready to join us?</h2>
            <p>See entry requirements, how to apply and key admission dates.</p>
          </div>
          <div className="site-hero-actions">
            <Link to="/admissions" className="btn btn-gold">How to apply</Link>
            <Link to="/contact" className="btn btn-outline-light">Ask a question</Link>
          </div>
        </div>
      </section>
    </>
  )
}
