import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <div className="container page-home">
      <section className="hero">
        <h1>Rent the equipment you need</h1>
        <p className="hero-lead">
          Dump trailers, tools, and job-site gear — check live availability and request dates that work
          for you.
        </p>
        <div className="hero-actions">
          <Link to="/catalog" className="btn btn-primary">
            Browse catalog
          </Link>
        </div>
      </section>
      <section className="features grid-3">
        <div className="card card-pad">
          <h3>Clear pricing</h3>
          <p className="muted">Cost per day, deposits, and minimum rental shown up front.</p>
        </div>
        <div className="card card-pad">
          <h3>Live calendar</h3>
          <p className="muted">See whether each item is open, booked, or in use by day.</p>
        </div>
        <div className="card card-pad">
          <h3>Duration savings</h3>
          <p className="muted">Longer rentals include a built-in discount (see item details).</p>
        </div>
      </section>
    </div>
  )
}
