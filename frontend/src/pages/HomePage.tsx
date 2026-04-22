import { Link } from 'react-router-dom'
import { LEGAL_BUSINESS_NAME, SERVICE_AREA_TAGLINE } from '../branding'

export function HomePage() {
  return (
    <div className="container">
      <section className="hero">
        <p className="hero-business muted">
          <strong>{LEGAL_BUSINESS_NAME}</strong>
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
            <h3>Quotes with tax &amp; deposit</h3>
            <p className="muted">
              Per-day rate, minimum rental, security deposit, and sales tax on your quote—so you can see
              the numbers before you book.
            </p>
          </div>
          <div className="card card-pad">
            <h3>Day-by-day availability</h3>
            <p className="muted">
              Each item has a calendar with status by date: open, booked, out for use, and more—request
              only the dates that are actually free.
            </p>
          </div>
          <div className="card card-pad">
            <h3>Request, e-sign, and pay</h3>
            <p className="muted">
              Submit a booking with the documents we need, sign your rental agreement when your request
              is approved, and pay the rental and deposit with secure Stripe checkouts.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
