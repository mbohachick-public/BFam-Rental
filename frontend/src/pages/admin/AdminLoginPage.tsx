import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export function AdminLoginPage() {
  const { adminToken, setAdminToken } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/admin/items'
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (adminToken) {
    return <Navigate to={from} replace />
  }

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
    <div className="container page-admin-login">
      <div className="card card-pad admin-login-card">
        <h1>Admin sign-in (stub)</h1>
        <p className="muted">
          Enter the same value as <code>ADMIN_STUB_TOKEN</code> in the API <code>.env</code>. Auth0
          will replace this later.
        </p>
        <form onSubmit={submit}>
          <label className="field">
            <span className="field-label">Admin token</span>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              autoComplete="off"
            />
          </label>
          {error && <p className="error-msg">{error}</p>}
          <button type="submit" className="btn btn-primary">
            Continue
          </button>
        </form>
      </div>
    </div>
  )
}
