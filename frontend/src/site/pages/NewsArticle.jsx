import { Link, useParams } from 'react-router-dom'
import { publicApi } from '../../api/client'
import Icon from '../../components/Icon'
import { Alert, Spinner } from '../../components/ui'
import { formatDate } from '../../utils/format'
import useApi from '../../utils/useApi'

export default function NewsArticle() {
  const { id } = useParams()
  const { data: item, error } = useApi(`/news/${id}/`, undefined, publicApi)

  return (
    <section className="site-section">
      <div className="site-container site-article">
        <Link to="/news" className="back-link"><Icon name="arrowLeft" size={16} /> All news</Link>
        {error ? <Alert>That story couldn't be found.</Alert> : !item ? <Spinner /> : (
          <article>
            <p className="site-kicker">{formatDate(item.created_at)}</p>
            <h1>{item.title}</h1>
            {item.body.split(/\n{2,}/).map((para) => <p key={para}>{para}</p>)}
          </article>
        )}
      </div>
    </section>
  )
}
