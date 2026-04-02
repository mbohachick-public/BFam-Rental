import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { adminPatch, adminPost, apiGet } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import type { ItemDetail } from '../../types'

export function AdminItemFormPage() {
  const { id } = useParams<{ id: string }>()
  const isNew = id === undefined
  const navigate = useNavigate()
  const { adminToken } = useAuth()

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('general')
  const [costPerDay, setCostPerDay] = useState('0')
  const [minDays, setMinDays] = useState('1')
  const [deposit, setDeposit] = useState('0')
  const [userReq, setUserReq] = useState('')
  const [imageUrls, setImageUrls] = useState('')
  const [towable, setTowable] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isNew || !id) return
    let cancelled = false
    apiGet<ItemDetail>(`/items/${id}`)
      .then((it) => {
        if (cancelled) return
        setTitle(it.title)
        setDescription(it.description)
        setCategory(it.category)
        setCostPerDay(String(it.cost_per_day))
        setMinDays(String(it.minimum_day_rental))
        setDeposit(String(it.deposit_amount))
        setUserReq(it.user_requirements)
        setImageUrls(it.images.map((i) => i.url).join('\n'))
        setTowable(Boolean(it.towable))
      })
      .catch((e: Error) => setError(e.message))
    return () => {
      cancelled = true
    }
  }, [id, isNew])

  function parseUrls(raw: string): string[] {
    return raw
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
  }

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!adminToken) return
    setSaving(true)
    setError(null)
    const urls = parseUrls(imageUrls)
    const body = {
      title: title.trim(),
      description: description.trim(),
      category: category.trim() || 'general',
      cost_per_day: costPerDay,
      minimum_day_rental: Number(minDays) || 1,
      deposit_amount: deposit,
      user_requirements: userReq.trim(),
      towable,
      image_urls: urls,
    }
    try {
      if (isNew) {
        const created = await adminPost<ItemDetail>('/admin/items', adminToken, body)
        navigate(`/admin/items/${created.id}/edit`, { replace: true })
      } else if (id) {
        await adminPatch<ItemDetail>(`/admin/items/${id}`, adminToken, {
          ...body,
          image_urls: urls,
        })
        navigate('/admin/items')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-admin-form">
      <p className="breadcrumb">
        <Link to="/admin/items">Items</Link>
        <span aria-hidden> / </span>
        <span>{isNew ? 'New' : 'Edit'}</span>
      </p>
      <h1>{isNew ? 'Add item' : 'Edit item'}</h1>
      <form className="card card-pad form-stack" onSubmit={save}>
        <label className="field">
          <span className="field-label">Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="field">
          <span className="field-label">Category</span>
          <input value={category} onChange={(e) => setCategory(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Description</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
        </label>
        <div className="filters-grid">
          <label className="field">
            <span className="field-label">Cost per day</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={costPerDay}
              onChange={(e) => setCostPerDay(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span className="field-label">Minimum days</span>
            <input
              type="number"
              min={1}
              step={1}
              value={minDays}
              onChange={(e) => setMinDays(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span className="field-label">Deposit</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={deposit}
              onChange={(e) => setDeposit(e.target.value)}
              required
            />
          </label>
        </div>
        <label className="field">
          <span className="field-label">User requirements</span>
          <textarea value={userReq} onChange={(e) => setUserReq(e.target.value)} rows={3} />
        </label>
        <label className="field field-checkbox">
          <input
            type="checkbox"
            checked={towable}
            onChange={(e) => setTowable(e.target.checked)}
          />
          <span>Towable (customers must upload a license plate photo when booking)</span>
        </label>
        <label className="field">
          <span className="field-label">Image URLs (one per line)</span>
          <textarea value={imageUrls} onChange={(e) => setImageUrls(e.target.value)} rows={4} />
        </label>
        {error && <p className="error-msg">{error}</p>}
        <div className="booking-actions">
          <Link to="/admin/items" className="btn btn-secondary">
            Cancel
          </Link>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  )
}
