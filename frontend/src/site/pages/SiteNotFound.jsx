import { Link } from 'react-router-dom'
import PageHero from './PageHero'

export default function SiteNotFound() {
  return (
    <>
      <PageHero title="Page not found">The page you're looking for doesn't exist or has moved.</PageHero>
      <section className="site-section">
        <div className="site-container site-hero-actions">
          <Link to="/" className="btn btn-primary">Go to the home page</Link>
          <Link to="/contact" className="btn btn-ghost">Contact us</Link>
        </div>
      </section>
    </>
  )
}
