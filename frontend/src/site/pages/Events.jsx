import { useState } from 'react'
import { publicApi } from '../../api/client'
import { EmptyState, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import { EventItem } from './Home'
import PageHero from './PageHero'

export default function Events() {
  const [past, setPast] = useState(false)
  const { data: events } = useApi('/events/', past ? { past: true } : {}, publicApi)

  return (
    <>
      <PageHero kicker="Events" title="Events & academic calendar">
        Ceremonies, deadlines, lectures and campus life.
      </PageHero>
      <section className="site-section">
        <div className="site-container site-narrow">
          <div className="chips">
            <button className={`chip ${!past ? 'active' : ''}`} onClick={() => setPast(false)}>Upcoming</button>
            <button className={`chip ${past ? 'active' : ''}`} onClick={() => setPast(true)}>Past</button>
          </div>
          {!events ? <Spinner /> : events.length === 0 ? <EmptyState icon="calendar" title={past ? 'No past events' : 'No upcoming events'} /> : (
            <ul className="site-events site-events-page">
              {events.map((e) => <EventItem key={e.id} event={e} showDescription />)}
            </ul>
          )}
        </div>
      </section>
    </>
  )
}
