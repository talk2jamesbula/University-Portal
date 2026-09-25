import { Link, useParams } from 'react-router-dom'
import { publicApi } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Badge, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import PageHero from './PageHero'

export default function ProgrammeDetail() {
  const { code } = useParams()
  const { data: p, error } = useApi(`/programmes/${code}/`, undefined, publicApi)

  if (error) {
    return (
      <section className="site-section"><div className="site-container">
        <Alert>That programme couldn't be found.</Alert>
        <Link to="/programmes" className="site-more">All programmes</Link>
      </div></section>
    )
  }
  if (!p) return <div className="site-section"><Spinner /></div>

  return (
    <>
      <PageHero kicker={`${p.faculty_name} · Department of ${p.department_name}`} title={p.title}>
        {p.description || `A ${p.duration_years}-year ${p.degree_label} programme.`}
      </PageHero>
      <section className="site-section">
        <div className="site-container site-two-col site-two-col-wide">
          <div>
            <h2>Curriculum</h2>
            <p className="muted">Courses by level and semester. Compulsory courses must be passed; electives are chosen at registration.</p>
            {p.curriculum.map((level) => (
              <div key={level.level} className="site-curriculum-level">
                <h3>{level.level} Level</h3>
                <div className="site-curriculum-semesters">
                  {level.semesters.map((s) => (
                    <div key={s.name} className="card">
                      <div className="card-header"><h2>{s.name}</h2><span className="muted small">{s.units} units</span></div>
                      <table className="table">
                        <tbody>
                          {s.courses.map((c) => (
                            <tr key={c.code}>
                              <td className="cell-title">{c.code}</td>
                              <td>{c.title}</td>
                              <td className="num">{c.units}</td>
                              <td>{c.is_compulsory ? <Badge tone="blue">Core</Badge> : <Badge>Elective</Badge>}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <aside className="site-panel site-sticky">
            <h3>At a glance</h3>
            <dl className="facts">
              <dt>Degree</dt><dd>{p.degree_label}</dd>
              <dt>Duration</dt><dd>{p.duration_years} years</dd>
              <dt>Faculty</dt><dd>{p.faculty_name}</dd>
              <dt>Department</dt><dd>{p.department_name}</dd>
            </dl>
            <Link to="/admissions" className="btn btn-primary btn-block">Entry requirements & how to apply</Link>
            <Link to="/contact" className="site-more">Ask about this programme <Icon name="arrowRight" size={14} /></Link>
          </aside>
        </div>
      </section>
    </>
  )
}
