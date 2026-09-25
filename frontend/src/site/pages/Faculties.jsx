import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { publicApi } from '../../api/client'
import Icon from '../../components/Icon'
import { Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import PageHero from './PageHero'

export default function Faculties() {
  const { data: faculties } = useApi('/faculties/', undefined, publicApi)
  const { hash } = useLocation()

  // Links like /faculties#FSC jump to that faculty once the list has loaded.
  useEffect(() => {
    if (faculties && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' })
  }, [faculties, hash])

  return (
    <>
      <PageHero kicker="Academics" title="Faculties & Departments">
        Teaching and research are organised into faculties, each made up of departments that run our degree programmes.
      </PageHero>
      <section className="site-section">
        <div className="site-container site-stack">
          {!faculties ? <Spinner /> : faculties.map((f) => (
            <article key={f.code} id={f.code} className="site-faculty">
              <header>
                <Icon name="building" size={26} />
                <h2>{f.name}</h2>
              </header>
              <div className="site-department-grid">
                {f.departments.map((d) => (
                  <div key={d.code} className="site-department">
                    <h3>Department of {d.name}</h3>
                    <ul>
                      {d.programmes.map((p) => (
                        <li key={p.code}>
                          <Link to={`/programmes/${p.code}`}>{p.title}</Link>
                          <span>{p.duration_years} years</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}
