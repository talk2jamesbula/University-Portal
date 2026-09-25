import { AreaChart, BarList, Columns, Donut, Funnel } from '../components/charts'
import Icon from '../components/Icon'
import { Alert, Card, Spinner, Stat } from '../components/ui'
import { formatDateTime, formatMoney } from '../utils/format'
import useApi from '../utils/useApi'

const naira = new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN', notation: 'compact', maximumFractionDigits: 1 })
const compactMoney = (v) => naira.format(v)
const percent = (v) => (v == null ? '—' : `${Number(v).toFixed(1).replace(/\.0$/, '')}%`)
const gpa = (v) => Number(v).toFixed(2)

const GRADE_COLORS = ['var(--chart-good)', 'var(--chart-1)', 'var(--chart-2)', 'var(--chart-warn)', 'var(--chart-warn)', 'var(--chart-bad)']
const STATUS_COLORS = {
  active: 'var(--chart-good)', probation: 'var(--chart-warn)', suspended: 'var(--chart-bad)', deferred: 'var(--chart-4)',
  withdrawn: 'var(--chart-muted)', expelled: 'var(--chart-bad)', completed: 'var(--chart-1)', graduated: 'var(--chart-3)',
}

function ChartCard({ title, subtitle, children, wide }) {
  return (
    <Card className={`chart-card ${wide ? 'chart-card-wide' : ''}`} title={title} action={subtitle && <span className="muted small">{subtitle}</span>}>
      {children}
    </Card>
  )
}

/** Charts for the management dashboard (VC, Registrar, Bursar, Deans). */
export default function Analytics() {
  const { data, loading, error, reload } = useApi('/reports/analytics/')
  if (error) return <Alert>{error}</Alert>
  if (loading && !data) return <Spinner label="Loading analytics…" />

  const { students, registration, finance, admissions, academics, attendance } = data
  return (
    <section className="analytics stack-lg" aria-labelledby="analytics-title">
      <div className="analytics-header">
        <div>
          <h2 id="analytics-title">Analytics</h2>
          <p className="muted small">{data.scope}{data.semester ? ` · ${data.semester}` : ''} · updated {formatDateTime(data.generated_at)}</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={reload} disabled={loading}><Icon name="trend" size={14} /> {loading ? 'Refreshing…' : 'Refresh'}</button>
      </div>

      <div className="stats-grid">
        <Stat icon="users" label="Students in session" value={students.total.toLocaleString()} />
        {registration && <Stat icon="register" label="Registered this semester" value={percent(registration.rate)} hint={`${registration.not_registered} not yet registered`} tone={registration.rate >= 80 ? 'green' : 'amber'} />}
        {finance && <Stat icon="wallet" label="Fees collected" value={percent(finance.collection_rate)} hint={`${formatMoney(finance.outstanding)} outstanding`} tone="green" />}
        {attendance && <Stat icon="check" label="Attendance this semester" value={percent(attendance.overall)} tone={attendance.overall >= 75 ? 'green' : 'red'} />}
        {academics && !finance && <Stat icon="award" label="Pass rate (latest results)" value={percent(academics.pass_rate)} tone="purple" />}
      </div>

      <div className="chart-grid">
        {finance && (
          <ChartCard title="Fee collections" subtitle="Last 12 months" wide>
            <AreaChart data={finance.monthly} format={compactMoney} />
          </ChartCard>
        )}
        <ChartCard title="Students by faculty">
          <BarList data={students.by_faculty} />
        </ChartCard>
        <ChartCard title="Students by level">
          <Columns data={students.by_level} />
        </ChartCard>
        <ChartCard title="Academic status" subtitle="All students">
          <Donut data={students.by_status} colors={students.by_status.map((s) => STATUS_COLORS[s.key])} centerLabel="students" />
        </ChartCard>
        {registration && (
          <ChartCard title="Course registration by level" subtitle="% registered">
            <Columns data={registration.by_level} format={percent} max={100} color="var(--chart-2)" />
          </ChartCard>
        )}
        {academics && (
          <ChartCard title="Grade distribution" subtitle={academics.semester}>
            <Columns data={academics.grade_distribution} colors={GRADE_COLORS} />
            <p className="chart-note">Pass rate <strong>{percent(academics.pass_rate)}</strong> across {academics.results} results</p>
          </ChartCard>
        )}
        {academics && (
          <ChartCard title="Average GPA by department" subtitle={academics.semester}>
            <BarList data={[...academics.gpa_by_department].sort((a, b) => b.value - a.value)} format={gpa} max={5} color="var(--chart-3)" />
          </ChartCard>
        )}
        {attendance && (
          <ChartCard title="Attendance by faculty" subtitle="Line = 75% minimum">
            <BarList data={attendance.by_faculty} format={percent} max={100} marker={75}
                     colors={attendance.by_faculty.map((f) => (f.value < 75 ? 'var(--chart-bad)' : 'var(--chart-good)'))} />
          </ChartCard>
        )}
        {admissions && (
          <ChartCard title="Admissions funnel" subtitle={`${admissions.session} admission`}>
            <Funnel data={admissions.funnel} />
          </ChartCard>
        )}
        {admissions && (
          <ChartCard title="Applications submitted per week" subtitle={admissions.session}>
            <Columns data={admissions.weekly} color="var(--chart-4)" height={150} />
          </ChartCard>
        )}
        {admissions && (
          <ChartCard title="Most popular programmes" subtitle="Submitted applications">
            <BarList data={admissions.by_programme} color="var(--chart-4)" />
          </ChartCard>
        )}
        {finance && (
          <ChartCard title="Payments by method">
            <Donut data={finance.by_method} format={compactMoney} centerLabel="collected" />
          </ChartCard>
        )}
        {finance && (
          <ChartCard title="Outstanding fees by faculty">
            <BarList data={finance.outstanding_by_faculty} format={compactMoney} color="var(--chart-warn)" />
          </ChartCard>
        )}
        <ChartCard title="Gender" subtitle="Students in session">
          <Donut data={students.by_gender} colors={['var(--chart-5)', 'var(--chart-1)']} centerLabel="students" />
        </ChartCard>
      </div>
    </section>
  )
}
