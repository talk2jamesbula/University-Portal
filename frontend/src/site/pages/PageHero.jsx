/** The banner at the top of every inner page of the website. */
export default function PageHero({ kicker, title, children }) {
  return (
    <section className="site-page-hero">
      <div className="site-container">
        {kicker && <p className="site-kicker">{kicker}</p>}
        <h1>{title}</h1>
        {children && <p className="site-lead">{children}</p>}
      </div>
    </section>
  )
}
