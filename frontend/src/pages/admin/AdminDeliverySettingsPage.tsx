import { useCallback, useEffect, useState } from 'react'
import { adminGet, adminPatch } from '../../api/client'
import { useAdminApiReady } from '../../hooks/useAdminApiReady'
import type { DeliverySettingsOut } from '../../types'

function moneyLike(s: string) {
  const n = Number(s)
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
    : s
}

export function AdminDeliverySettingsPage() {
  const adminApiReady = useAdminApiReady()
  const [settings, setSettings] = useState<DeliverySettingsOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [ok, setOk] = useState<string | null>(null)

  const [enabled, setEnabled] = useState(false)
  const [originAddress, setOriginAddress] = useState('')
  const [pricePerMile, setPricePerMile] = useState('')
  const [minimumFee, setMinimumFee] = useState('')
  const [freeMiles, setFreeMiles] = useState('')
  const [maxMiles, setMaxMiles] = useState('')

  const load = useCallback(() => {
    if (!adminApiReady) return
    setError(null)
    adminGet<DeliverySettingsOut>('/admin/delivery-settings')
      .then((s) => {
        setSettings(s)
        setEnabled(s.enabled)
        setOriginAddress(s.origin_address)
        setPricePerMile(String(s.price_per_mile))
        setMinimumFee(String(s.minimum_fee))
        setFreeMiles(String(s.free_miles))
        setMaxMiles(s.max_delivery_miles != null ? String(s.max_delivery_miles) : '')
      })
      .catch((e: Error) => setError(e.message))
  }, [adminApiReady])

  useEffect(() => {
    load()
  }, [load])

  async function save() {
    if (!adminApiReady) return
    setSaving(true)
    setOk(null)
    setError(null)
    try {
      const maxRaw = maxMiles.trim()
      const body: Record<string, unknown> = {
        enabled,
        origin_address: originAddress.trim(),
        price_per_mile: pricePerMile.trim() || '0',
        minimum_fee: minimumFee.trim() || '0',
        free_miles: freeMiles.trim() || '0',
        max_delivery_miles: maxRaw === '' ? null : maxRaw,
      }
      const next = await adminPatch<DeliverySettingsOut>('/admin/delivery-settings', body)
      setSettings(next)
      setOk('Saved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-admin-delivery">
      <div className="page-head">
        <h1>Delivery pricing</h1>
      </div>
      <p className="muted">
        One-way road miles come from Google Distance Matrix (API key in backend env only). Tax applies
        to rental subtotal plus delivery fee. Customers see delivery only on items marked
        delivery-available.
      </p>
      {error && <p className="error-msg">{error}</p>}
      {ok && <p className="success-msg">{ok}</p>}
      {settings && (
        <div className="card card-pad booking-form">
          <p className="small">
            Google Maps:{' '}
            <strong>{settings.google_maps_configured ? 'API key set' : 'not configured'}</strong>
            {settings.google_maps_configured ? '' : ' — set GOOGLE_MAPS_API_KEY in backend .env.'}
          </p>
          <div className="booking-grid">
            <label className="field field-checkbox field-span">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
              />
              <span>Enable delivery pricing</span>
            </label>
            <label className="field field-span">
              <span className="field-label">Origin address (shop / yard)</span>
              <input
                type="text"
                value={originAddress}
                onChange={(e) => setOriginAddress(e.target.value)}
                autoComplete="off"
              />
            </label>
            <label className="field">
              <span className="field-label">Price per mile (after free miles)</span>
              <input
                type="text"
                inputMode="decimal"
                value={pricePerMile}
                onChange={(e) => setPricePerMile(e.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Minimum delivery fee</span>
              <input
                type="text"
                inputMode="decimal"
                value={minimumFee}
                onChange={(e) => setMinimumFee(e.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Free miles (one-way)</span>
              <input
                type="text"
                inputMode="decimal"
                value={freeMiles}
                onChange={(e) => setFreeMiles(e.target.value)}
              />
            </label>
            <label className="field field-span">
              <span className="field-label">Max delivery miles (optional cap)</span>
              <input
                type="text"
                inputMode="decimal"
                value={maxMiles}
                onChange={(e) => setMaxMiles(e.target.value)}
                placeholder="Leave empty for no limit"
              />
            </label>
          </div>
          <p className="muted small">
            Example at {moneyLike(pricePerMile || '0')}/mi after {freeMiles || '0'} free miles, minimum{' '}
            {moneyLike(minimumFee || '0')}.
          </p>
          <button type="button" className="btn btn-primary" disabled={saving} onClick={save}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      )}
    </div>
  )
}
