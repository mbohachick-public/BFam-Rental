import { Link } from 'react-router-dom'
import { DBA_NAME, LEGAL_BUSINESS_NAME, SERVICE_AREA_TAGLINE } from '../branding'

export function HomePage() {
  return (
    <div className="container page-home">
      <section className="hero">
        <p className="hero-business muted">
          <strong>{DBA_NAME}</strong>
          <span className="hero-business-sep"> · </span>
          <span>{LEGAL_BUSINESS_NAME}</span>
        </p>
        <h1>Rent the equipment you need</h1>
        <p className="hero-lead">
          Dump trailers, tools, and job-site gear — check live availability and request dates that work
          for you.
        </p>
        <p className="hero-local muted">{SERVICE_AREA_TAGLINE}</p>
        <div className="hero-actions">
          <Link to="/catalog" className="btn btn-primary">
            Browse catalog
          </Link>
        </div>
      </section>
      <section className="features" aria-labelledby="features-heading">
        <h2 id="features-heading" className="visually-hidden">
          Why book with us
        </h2>
        <div className="grid-3">
          <div className="card card-pad">
            <h3>Clear pricing</h3>
            <p className="muted">Cost per day, deposits, and minimum rental shown up front.</p>
          </div>
          <div className="card card-pad">
            <h3>Live calendar</h3>
            <p className="muted">See whether each item is open, booked, or in use by day.</p>
          </div>
          <div className="card card-pad">
            <h3>Request online</h3>
            <p className="muted">Choose dates, get a quote by email, and submit your booking in one flow.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
