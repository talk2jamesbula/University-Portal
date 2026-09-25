import { useState } from 'react'
import { publicApi } from '../../api/client'
import { EmptyState, Spinner } from '../../components/ui'
import useApi from '../../utils/useApi'
import { NewsCard } from './Home'
import PageHero from './PageHero'

export default function News() {
  const [page, setPage] = useState(1)
  const { data } = useApi('/news/', { page }, publicApi)

  return (
    <>
      <PageHero kicker="News & Announcements" title="University news">
        Announcements, achievements and stories from across the university.
      </PageHero>
      <section className="site-section">
        <div className="site-container">
          {!data ? <Spinner /> : data.results.length === 0 ? <EmptyState icon="megaphone" title="No news yet" /> : (
            <>
              <div className="site-news-grid site-news-grid-3">
                {data.results.map((item) => <NewsCard key={item.id} item={item} />)}
              </div>
              {(data.previous || data.next) && (
                <div className="site-pager">
                  <button className="btn btn-ghost" disabled={!data.previous} onClick={() => setPage(page - 1)}>Newer</button>
                  <button className="btn btn-ghost" disabled={!data.next} onClick={() => setPage(page + 1)}>Older</button>
                </div>
              )}
            </>
          )}
        </div>
      </section>
    </>
  )
}
