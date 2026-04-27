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
          Dump trailers, equipment trailers and material delivery — check live availability and
          request dates that work for you.
        </p>
        <p className="hero-local muted">{SERVICE_AREA_TAGLINE}</p>
        <p className="muted small">
          For material deliveries (top soil, mulch, gravel, compost) please email{' '}
          <a href="mailto:delivery@bohachickrentals.com">delivery@bohachickrentals.com</a>.
        </p>
        <div className="hero-actions">
          <Link to="/catalog" className="btn btn-primary">
            Rental Catalog
          </Link>
        </div>
      </section>
      <section className="features" aria-labelledby="features-heading">
        <h2 id="features-heading" className="visually-hidden">
          Why book with us
        </h2>
        <div className="grid-3">
          <div className="card card-pad">
            <h3>Fully online rental experience</h3>
            <p className="muted">
              Browse the catalog, request dates, upload documents, review your quote, e-sign your
              agreement, and complete rental and deposit payments online—so you can move forward on your
              schedule without a trip to the office.
            </p>
          </div>
          <div className="card card-pad">
            <h3>Delivery when you need it</h3>
            <p className="muted">
              On eligible equipment, you can request delivery to your job site when you book. Your quote
              shows a road-mile-based delivery fee together with rental, applicable tax, and
              deposit—so you see the full picture before you submit a request.
            </p>
          </div>
          <div className="card card-pad">
            <h3>Bulk supplies—not only rentals</h3>
            <p className="muted">
              Beyond equipment rentals, we deliver bulk landscape and job-site materials such as topsoil,
              mulch, gravel, and compost. Email{' '}
              <a href="mailto:delivery@bohachickrentals.com">delivery@bohachickrentals.com</a> with what
              you need, where to deliver, and timing—we’ll follow up with availability and pricing.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
