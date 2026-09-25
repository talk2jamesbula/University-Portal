import { Alert, Badge, Card, EmptyState, PageHeader, Spinner, Stat } from '../components/ui'
import useApi from '../utils/useApi'

const GRADE_TONE = { A: 'green', B: 'blue', C: 'blue', D: 'amber', E: 'amber', F: 'red' }
const fixed = (n) => (n == null ? '—' : Number(n).toFixed(2))
const score = (n) => (n == null ? '—' : Number(n).toFixed(1).replace(/\.0$/, ''))

export default function Results() {
  const { data, loading, error } = useApi('/academics/results/')

  if (loading && !data) return <Spinner />
  if (error) return <Alert>{error}</Alert>

  return (
    <div className="stack-lg">
      <PageHeader
        title="Results & Academic Record"
        subtitle="Published results · 5-point scale (A 70–100, B 60–69, C 50–59, D 45–49, E 40–44, F 0–39)"
        actions={<button className="btn btn-ghost" onClick={() => window.print()}>Print</button>}
      />

      <div className="stats-grid">
        <Stat icon="award" label="CGPA" value={fixed(data.cgpa)} tone="green" />
        <Stat icon="check" label="Units passed" value={`${data.units_passed} / ${data.units_taken}`} />
        <Stat icon="cap" label="Class of degree (current)" value={data.degree_class || '—'} tone="purple" />
        <Stat icon="shield" label="Academic standing" value={data.standing} tone={data.standing === 'Good standing' ? 'green' : 'amber'} />
      </div>

      {data.semesters.length === 0 ? (
        <EmptyState icon="award" title="No published results yet">Results appear here once Senate approves and publishes them.</EmptyState>
      ) : (
        data.semesters.map((s) => (
          <Card
            key={s.semester.id}
            title={s.semester.name}
            padded={false}
            action={<span className="muted small">GPA <strong className="text-strong">{fixed(s.gpa)}</strong> · {s.units_passed}/{s.units_taken} units passed</span>}
          >
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th><th>Title</th><th className="num">Units</th><th className="num">CA</th>
                  <th className="num">Exam</th><th className="num">Total</th><th>Grade</th><th className="num">GP</th>
                </tr>
              </thead>
              <tbody>
                {s.courses.map((c) => (
                  <tr key={c.code}>
                    <td className="cell-title">{c.code} {c.is_carryover && <Badge tone="red">Carry-over</Badge>}</td>
                    <td>{c.title}</td>
                    <td className="num">{c.units}</td>
                    <td className="num">{score(c.ca_score)}</td>
                    <td className="num">{score(c.exam_score)}</td>
                    <td className="num strong">{score(c.total_score)}</td>
                    <td><Badge tone={GRADE_TONE[c.grade]}>{c.grade}</Badge></td>
                    <td className="num">{c.grade_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ))
      )}
    </div>
  )
}
