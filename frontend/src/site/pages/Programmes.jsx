import { useState } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../api/client'
import Icon from '../../components/Icon'
import { EmptyState, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import PageHero from './PageHero'

export default function Programmes() {
  const { data: faculties } = useApi('/faculties/', undefined, publicApi)
  const [faculty, setFaculty] = useState('')
  const [query, setQuery] = useState('')
  const { data: programmes } = useApi('/programmes/', faculty ? { faculty } : {}, publicApi)
  const q = query.trim().toLowerCase()
  const shown = (programmes || []).filter((p) => !q || `${p.title} ${p.department_name}`.toLowerCase().includes(q))

  return (
    <>
      <PageHero kicker="Academics" title="Academic Programmes">
        Undergraduate degree programmes, their duration and full course curricula.
      </PageHero>
      <section className="site-section">
        <div className="site-container">
          <div className="toolbar site-toolbar">
            <label className="search">
              <Icon name="search" />
              <input placeholder="Search programmes" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search programmes" />
            </label>
            <select value={faculty} onChange={(e) => setFaculty(e.target.value)} aria-label="Faculty">
              <option value="">All faculties</option>
              {faculties?.map((f) => <option key={f.code} value={f.code}>{f.name}</option>)}
            </select>
          </div>
          {!programmes ? <Spinner /> : shown.length === 0 ? <EmptyState title="No programmes match" /> : (
            <div className="site-programme-grid">
              {shown.map((p) => (
                <Link key={p.code} to={`/programmes/${p.code}`} className="site-programme-card">
                  <span className="site-degree">{p.degree}</span>
                  <h3>{p.name}</h3>
                  <p>{p.faculty_name}</p>
                  <div className="site-programme-meta">
                    <span><Icon name="clock" size={14} /> {p.duration_years} years</span>
                    <span><Icon name="building" size={14} /> {p.department_name}</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
    </>
  )
}
