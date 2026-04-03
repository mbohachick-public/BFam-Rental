import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { adminDelete, adminGet, adminPatch, adminPost, adminPostFormData } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import type { ItemDetail, ItemImage } from '../../types'

const MAX_IMAGES = 10

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
  const [towable, setTowable] = useState(false)
  const [active, setActive] = useState(true)
  const [images, setImages] = useState<ItemImage[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isNew || !id || !adminToken) return
    let cancelled = false
    adminGet<ItemDetail>(`/admin/items/${id}`, adminToken)
      .then((it) => {
        if (cancelled) return
        setTitle(it.title)
        setDescription(it.description)
        setCategory(it.category)
        setCostPerDay(String(it.cost_per_day))
        setMinDays(String(it.minimum_day_rental))
        setDeposit(String(it.deposit_amount))
        setUserReq(it.user_requirements)
        setImages([...it.images].sort((a, b) => a.sort_order - b.sort_order))
        setTowable(Boolean(it.towable))
        setActive(it.active !== false)
      })
      .catch((e: Error) => setError(e.message))
    return () => {
      cancelled = true
    }
  }, [id, isNew, adminToken])

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!adminToken) return
    setSaving(true)
    setError(null)
    const body = {
      title: title.trim(),
      description: description.trim(),
      category: category.trim() || 'general',
      cost_per_day: costPerDay,
      minimum_day_rental: Number(minDays) || 1,
      deposit_amount: deposit,
      user_requirements: userReq.trim(),
      towable,
      active,
    }
    try {
      if (isNew) {
        const created = await adminPost<ItemDetail>('/admin/items', adminToken, {
          ...body,
          image_urls: [],
        })
        navigate(`/admin/items/${created.id}/edit`, { replace: true })
      } else if (id) {
        await adminPatch<ItemDetail>(`/admin/items/${id}`, adminToken, body)
        navigate('/admin/items')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function onPickFiles(ev: React.ChangeEvent<HTMLInputElement>) {
    const files = ev.target.files
    if (!files || !id || !adminToken) return
    const list = Array.from(files)
    ev.target.value = ''
    setError(null)
    setUploading(true)
    try {
      let next = [...images].sort((a, b) => a.sort_order - b.sort_order)
      for (const file of list) {
        if (next.length >= MAX_IMAGES) break
        const fd = new FormData()
        fd.append('file', file)
        const added = await adminPostFormData<ItemImage>(`/admin/items/${id}/images`, adminToken, fd)
        next = [...next, added].sort((a, b) => a.sort_order - b.sort_order)
        setImages(next)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function removeImage(im: ItemImage) {
    if (!id || !adminToken) return
    setError(null)
    try {
      const detail = await adminDelete<ItemDetail>(`/admin/items/${id}/images/${im.id}`, adminToken)
      setImages([...detail.images].sort((a, b) => a.sort_order - b.sort_order))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Remove failed')
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
        <label className="field field-checkbox">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
          />
          <span>Visible in catalog (uncheck to hide from customers while keeping the item for admin)</span>
        </label>

        <div className="field">
          <span className="field-label">Photos (up to {MAX_IMAGES}, JPEG / PNG / WebP)</span>
          {isNew ? (
            <p className="muted" style={{ marginTop: '0.35rem' }}>
              Save the item once, then you can upload photos to the catalog bucket.
            </p>
          ) : (
            <>
              <label className="admin-upload-label">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  multiple
                  disabled={uploading || images.length >= MAX_IMAGES}
                  onChange={onPickFiles}
                />
                <span className="btn btn-secondary btn-sm">
                  {uploading ? 'Uploading…' : 'Choose images'}
                </span>
              </label>
              <p className="muted" style={{ marginTop: '0.35rem' }}>
                {images.length >= MAX_IMAGES
                  ? 'Maximum reached — remove an image to add another.'
                  : `${MAX_IMAGES - images.length} slot${MAX_IMAGES - images.length === 1 ? '' : 's'} left.`}
              </p>
              {images.length > 0 && (
                <ul className="admin-item-images">
                  {images.map((im) => (
                    <li key={im.id}>
                      <img src={im.url} alt="" />
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => removeImage(im)}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>

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
