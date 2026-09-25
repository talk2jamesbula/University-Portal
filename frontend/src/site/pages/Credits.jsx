import { CREDITS } from '../photos'
import PageHero from './PageHero'

export default function Credits() {
  return (
    <>
      <PageHero title="Photo credits">
        Photographs on this website are used under Creative Commons licences. They have been resized and cropped for the web.
      </PageHero>
      <section className="site-section">
        <div className="site-container site-credits">
          {CREDITS.map((c) => (
            <figure key={c.key} className="site-credit">
              <img src={c.image.src} alt={c.image.alt} loading="lazy" />
              <figcaption>
                <strong>“{c.title}”</strong> by {c.author}.{' '}
                Source: <a href={c.source} target="_blank" rel="noreferrer">Wikimedia Commons</a>.{' '}
                Licence: <a href={c.licenseUrl} target="_blank" rel="noreferrer">{c.license}</a>. Resized and cropped.
              </figcaption>
            </figure>
          ))}
        </div>
      </section>
    </>
  )
}
