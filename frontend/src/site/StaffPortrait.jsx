import { useId } from 'react'

/**
 * A staff member's photo for the website, or — until they have one — a neutral illustrated
 * silhouette (never a stranger's photo standing in for a named official).
 */
export default function StaffPortrait({ person, size = 'md' }) {
  const gradient = useId()
  return (
    <div className={`staff-portrait staff-portrait-${size}`}>
      {person.photo_url ? (
        <img src={person.photo_url} alt={`Portrait of ${person.name}`} loading="lazy" />
      ) : (
        <svg viewBox="0 0 120 150" role="img" aria-label={`${person.name} (photo coming soon)`}>
          <defs>
            <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#1b3f73" />
              <stop offset="1" stopColor="#0b1d38" />
            </linearGradient>
          </defs>
          <rect width="120" height="150" fill={`url(#${gradient})`} />
          <circle cx="60" cy="56" r="24" fill="#c9d5e8" opacity="0.9" />
          <path d="M16 150c2-30 20-48 44-48s42 18 44 48Z" fill="#c9d5e8" opacity="0.9" />
          <path d="M44 106 60 128l16-22" fill="none" stroke="#e0b54a" strokeWidth="4" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  )
}
