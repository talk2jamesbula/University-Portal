import { Link } from 'react-router-dom'
import { EmptyState } from '../components/ui'

export default function NotFound() {
  return (
    <EmptyState icon="search" title="Page not found">
      The page you're looking for doesn't exist. <Link to="/portal" className="link">Return to the dashboard</Link>.
    </EmptyState>
  )
}
