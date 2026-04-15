import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { auth0Configured } from '../../auth0/config'
import { useAuth } from '../../context/AuthContext'
import { useCustomerSession } from '../../context/CustomerSessionContext'

export function AdminLoginPage() {
  const { adminToken, setAdminToken, setAdminAuth0Session } = useAuth()
  const customer = useCustomerSession()
  const location = useLocation()
  const navigate = useNavigate()
  const from = (location.state as { from?: string } | null)?.from ?? '/admin/items'
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)

  const auth0On = auth0Configured() && customer.mode === 'auth0'

  if (adminToken?.trim()) {
    return <Navigate to={from} replace />
  }

  if (auth0On && customer.isAuthenticated && !customer.isLoading) {
    return (
      <div className="container page-admin-login">
        <div className="card card-pad admin-login-card">
          <h1>Admin</h1>
          <p className="muted">
            You are signed in as <strong>{customer.userEmail ?? 'your account'}</strong>. Continue if this user
            is allowed as an admin in the API (Auth0 role/email — see backend README).
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setError(null)
              setAdminAuth0Session(true)
              navigate(from, { replace: true })
            }}
          >
            Continue to admin
          </button>
          <p className="muted small" style={{ marginTop: '1.25rem' }}>
            Or use the stub token below for local testing (same value as <code>ADMIN_STUB_TOKEN</code> on the API).
          </p>
          <StubAdminForm
            token={token}
            setToken={setToken}
            error={error}
            setError={setError}
            setAdminToken={setAdminToken}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="container page-admin-login">
      <div className="card card-pad admin-login-card">
        <h1>Admin sign-in</h1>
        {auth0On ? (
          <>
            <p className="muted">
              Sign in with your account (top of the site), then return here and choose <strong>Continue to admin</strong>,
              or enter the API stub token for automation and local dev.
            </p>
            {customer.isLoading ? (
              <p className="muted">Loading…</p>
            ) : (
              <button type="button" className="btn btn-primary" onClick={() => customer.login()}>
                Sign in with Auth0
              </button>
            )}
          </>
        ) : (
          <p className="muted">
            Enter the same value as <code>ADMIN_STUB_TOKEN</code> in the API <code>.env</code>. Enable Auth0 in the
            SPA to sign in as an admin user instead.
          </p>
        )}
        <StubAdminForm
          token={token}
          setToken={setToken}
          error={error}
          setError={setError}
          setAdminToken={setAdminToken}
        />
      </div>
    </div>
  )
}

function StubAdminForm({
  token,
  setToken,
  error,
  setError,
  setAdminToken,
}: {
  token: string
  setToken: (v: string) => void
  error: string | null
  setError: (v: string | null) => void
  setAdminToken: (v: string | null) => void
}) {
  function submit(e: React.FormEvent) {
    e.preventDefault()
    const t = token.trim()
    if (!t) {
      setError('Enter the admin token.')
      return
    }
    setError(null)
    setAdminToken(t)
  }

  return (
    <form onSubmit={submit} style={{ marginTop: '1rem' }}>
      <label className="field" htmlFor="bfam-admin-stub-token">
        <span className="field-label">Admin token (stub)</span>
        <input
          id="bfam-admin-stub-token"
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          autoComplete="off"
        />
      </label>
      {error && <p className="error-msg">{error}</p>}
      <button type="submit" className="btn btn-secondary" style={{ marginTop: '0.5rem' }}>
        Continue with stub token
      </button>
    </form>
  )
}
