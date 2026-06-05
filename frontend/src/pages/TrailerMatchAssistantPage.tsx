import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiPost, apiPostPublic } from '../api/client'

const CONTACT_MAIL = 'delivery@bohachickrentals.com'

type TowPkg = 'yes' | 'no' | 'unknown'
type Brake = 'yes' | 'no' | 'unknown'
type Exp = 'first_time' | 'some' | 'experienced'
type Load =
  | 'mulch'
  | 'topsoil'
  | 'gravel'
  | 'brush'
  | 'construction'
  | 'household'
  | 'other'
type Amount = 'y1' | 'y2' | 'y3' | 'y4' | 'y5plus' | 'unsure'

type AssistantMode = 'single_trailer' | 'multi_load' | 'contact_required' | 'delivery_suggested'

type AssistantOut = {
  id: string
  mode: AssistantMode
  recommended: { type: string; title: string; blurb: string } | null
  trailer_for_load: string | null
  trailer_for_load_title: string | null
  estimated_trips: number | null
  job_fit: string
  vehicle_fit: string
  driver_fit: string
  overall_confidence: string
  alternative: { type: string; title: string; blurb: string }
  estimated_weight_min_lbs: number | null
  estimated_weight_max_lbs: number | null
  confidence: string
  reasons: string[]
  warnings: string[]
  ctas: string[]
  follow_up_cta: string
  delivery_cta_emphasized: boolean
  delivery_cta_reason: string | null
  recommended_catalog_item_id: string | null
  legal_disclaimer: string
  estimate_disclaimer: string
}

const LOAD_LABELS: Record<Load, string> = {
  mulch: 'Mulch',
  topsoil: 'Topsoil',
  gravel: 'Gravel',
  brush: 'Brush / yard waste',
  construction: 'Construction debris',
  household: 'Household cleanout',
  other: 'Other',
}

const AMOUNT_LABELS: Record<Amount, string> = {
  y1: 'About 1 cubic yard',
  y2: 'About 2 cubic yards',
  y3: 'About 3 cubic yards',
  y4: 'About 4 cubic yards',
  y5plus: 'About 5+ cubic yards',
  unsure: 'Not sure yet',
}

function stepTitle(step: number) {
  if (step === 1) return 'Your tow vehicle'
  if (step === 2) return 'Towing setup'
  if (step === 3) return 'What you are hauling'
  return ''
}

function buildConfirmMail(opts: {
  matchId: string
  trailerTitle: string
  year: number
  make: string
  model: string
  trim: string
  loadLabel: string
  amountLabel: string
}) {
  const subject = encodeURIComponent('Trailer Match — please confirm my load')
  const body = encodeURIComponent(
    [
      `Trailer Match ID: ${opts.matchId}`,
      `Recommended trailer: ${opts.trailerTitle}`,
      `Vehicle: ${opts.year} ${opts.make} ${opts.model}${opts.trim ? ` (${opts.trim})` : ''}`,
      `Load: ${opts.loadLabel}`,
      `Estimated amount: ${opts.amountLabel}`,
      '',
      'Please confirm this is a good fit before I book.',
    ].join('\n'),
  )
  return `mailto:${CONTACT_MAIL}?subject=${subject}&body=${body}`
}

function buildDeliveryQuoteMail(opts: {
  matchId: string
  trailerTitle: string
  year: number
  make: string
  model: string
  trim: string
  loadLabel: string
  amountLabel: string
}) {
  const subject = encodeURIComponent('Delivery quote request (from Trailer Match)')
  const body = encodeURIComponent(
    [
      'I used the Trailer Match Assistant and would like a delivery quote (or help hauling materials).',
      '',
      `Trailer Match ID: ${opts.matchId}`,
      `Recommended rental trailer: ${opts.trailerTitle}`,
      `Vehicle: ${opts.year} ${opts.make} ${opts.model}${opts.trim ? ` (${opts.trim})` : ''}`,
      `Load type: ${opts.loadLabel}`,
      `Estimated amount: ${opts.amountLabel}`,
      '',
      'Job site / delivery address:',
      'Timing:',
      'Questions:',
    ].join('\n'),
  )
  return `mailto:${CONTACT_MAIL}?subject=${subject}&body=${body}`
}

export function TrailerMatchAssistantPage() {
  const sessionId = useMemo(() => (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : ''), [])
  const [step, setStep] = useState<number>(1)
  const [year, setYear] = useState(new Date().getFullYear())
  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [trim, setTrim] = useState('')
  const [towPackage, setTowPackage] = useState<TowPkg>('unknown')
  const [brake, setBrake] = useState<Brake>('unknown')
  const [experience, setExperience] = useState<Exp>('some')
  const [loadType, setLoadType] = useState<Load>('mulch')
  const [amount, setAmount] = useState<Amount>('y2')
  const [submitting, setSubmitting] = useState(false)
  const [deliveryClickBusy, setDeliveryClickBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AssistantOut | null>(null)

  const canNext1 = make.trim().length > 0 && model.trim().length > 0 && year >= 1980
  const canSubmit = canNext1

  async function submit() {
    setError(null)
    setSubmitting(true)
    try {
      const out = await apiPost<AssistantOut>('/trailer-match/assistant', {
        year,
        make: make.trim(),
        model: model.trim(),
        trim_or_engine: trim.trim() || null,
        tow_package: towPackage,
        brake_controller: brake,
        towing_experience: experience,
        load_type: loadType,
        estimated_amount: amount,
        session_id: sessionId || null,
      })
      try {
        sessionStorage.setItem('trailer_match_request_id', out.id)
      } catch {
        /* ignore */
      }
      setResult(out)
      setStep(4)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setSubmitting(false)
    }
  }

  async function onDeliveryQuoteClick() {
    if (!result) return
    setDeliveryClickBusy(true)
    try {
      await apiPostPublic<{ ok: boolean }>(
        `/trailer-match/requests/${encodeURIComponent(result.id)}/delivery-quote-click`,
        {},
      )
    } catch {
      /* still open mailto */
    } finally {
      setDeliveryClickBusy(false)
    }
    const trailerTitle =
      result.recommended?.title ??
      result.trailer_for_load_title ??
      result.alternative.title ??
      'Trailer to be confirmed'
    window.location.href = buildDeliveryQuoteMail({
      matchId: result.id,
      trailerTitle,
      year,
      make,
      model,
      trim: trim.trim(),
      loadLabel: LOAD_LABELS[loadType],
      amountLabel: AMOUNT_LABELS[amount],
    })
  }

  if (result && step === 4) {
    const recTitle = result.recommended?.title ?? null
    const bookPath = result.recommended_catalog_item_id
      ? `/items/${result.recommended_catalog_item_id}?tmr=${encodeURIComponent(result.id)}`
      : `/catalog`
    const trailerForMail = recTitle ?? result.trailer_for_load_title ?? 'Not selected — please confirm with us'
    const confirmMail = buildConfirmMail({
      matchId: result.id,
      trailerTitle: trailerForMail,
      year,
      make,
      model,
      trim: trim.trim(),
      loadLabel: LOAD_LABELS[loadType],
      amountLabel: AMOUNT_LABELS[amount],
    })
    const askPrimary = result.follow_up_cta === 'ask_confirm'
    const deliveryProminent = result.delivery_cta_emphasized || result.mode === 'delivery_suggested'

    const headline =
      result.mode === 'contact_required'
        ? 'Next step: confirm with us before choosing a trailer'
        : result.mode === 'multi_load'
          ? "Recommended plan: 10′ 7k trailer with multiple smaller loads"
          : result.mode === 'delivery_suggested' && recTitle
            ? `Recommended trailer: ${recTitle}`
            : recTitle
              ? `Recommended trailer: ${recTitle}`
              : 'Trailer recommendation'

    return (
      <div className="container trailer-match-page">
        <div className="card card-pad trailer-match-card">
          <p className="trailer-match-kicker">Trailer Match Assistant</p>
          <h1 className="trailer-match-title">{headline}</h1>
          <p className="muted trailer-match-lead">
            This is planning guidance from our team—not proof that your vehicle can legally or safely tow a particular
            trailer when loaded. Treat capacity and brake-controller needs as something you must verify on your truck
            and hitch.
          </p>

          {result.mode === 'multi_load' && result.estimated_trips != null ? (
            <p className="trailer-match-trips" role="status">
              <strong>Estimated trips on the 10′ 7k:</strong> about {result.estimated_trips} loads for the volume you
              described (rough planning only).
            </p>
          ) : null}

          {result.mode === 'multi_load' && result.trailer_for_load_title && result.trailer_for_load !== '10_7k' ? (
            <p className="muted trailer-match-alt-load">
              Larger trailer that may fit the load in fewer trips: <strong>{result.trailer_for_load_title}</strong>.
              We still recommend the 10′ 7k with lighter loads based on your towing answers—not because the larger
              trailer is wrong for the material alone.
            </p>
          ) : null}

          {result.mode === 'delivery_suggested' ? (
            <p className="muted trailer-match-mode-note" role="note">
              We suggested a smaller trailer than the material alone might allow. Compare with a delivery quote if
              hauling yourself feels uncertain.
            </p>
          ) : null}

          <section className="trailer-match-section" aria-labelledby="why-heading">
            <h2 id="why-heading" className="trailer-match-h2">
              {result.mode === 'multi_load' ? 'Why we suggested this plan' : 'Why this trailer fits your job'}
            </h2>
            <ul className="trailer-match-list">
              {result.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </section>

          <section className="trailer-match-section" aria-labelledby="watch-heading">
            <h2 id="watch-heading" className="trailer-match-h2">
              Things to verify before towing
            </h2>
            {result.warnings.length === 0 ? (
              <p className="muted">
                We didn’t flag extra mechanical watch-outs from your answers—still confirm tow capacity, payload, hitch,
                brakes, and local rules yourself.
              </p>
            ) : (
              <ul className="trailer-match-list trailer-match-warnings">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </section>

          <section className="trailer-match-section" aria-labelledby="weight-heading">
            <h2 id="weight-heading" className="trailer-match-h2">
              Rough material weight (planning only)
            </h2>
            <p className="muted">{result.estimate_disclaimer}</p>
            {result.estimated_weight_min_lbs != null && result.estimated_weight_max_lbs != null ? (
              <p className="trailer-match-weight-range">
                About {result.estimated_weight_min_lbs.toLocaleString()}–{result.estimated_weight_max_lbs.toLocaleString()}{' '}
                lb for the amount and material you selected (very approximate).
              </p>
            ) : (
              <p className="muted">We couldn’t estimate a numeric band for this load type—call us and we’ll help you sanity-check.</p>
            )}
          </section>

          <section className="trailer-match-section" aria-labelledby="alt-heading">
            <h2 id="alt-heading" className="trailer-match-h2">
              Alternative to consider
            </h2>
            <p>
              <strong>{result.alternative.title}</strong> — {result.alternative.blurb}
            </p>
          </section>

          <div className="trailer-match-disclaimer card card-pad muted" role="note">
            {result.legal_disclaimer}
          </div>

          <p className="trailer-match-confidence">
            Overall confidence: <strong>{result.overall_confidence}</strong>
            <span className="muted">
              {' '}
              (job {result.job_fit} · vehicle {result.vehicle_fit} · driver {result.driver_fit})
            </span>
          </p>

          <div className="trailer-match-cta-row">
            {result.mode === 'contact_required' ? (
              <>
                <a className="btn btn-primary" href={confirmMail}>
                  Ask us to confirm
                </a>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={deliveryClickBusy}
                  onClick={() => void onDeliveryQuoteClick()}
                >
                  {deliveryClickBusy ? 'Opening…' : 'Request delivery quote'}
                </button>
              </>
            ) : (
              <>
                <Link className={askPrimary ? 'btn btn-secondary' : 'btn btn-primary'} to={bookPath}>
                  {result.ctas[0] ?? 'Book this trailer'}
                </Link>
                <a className={askPrimary ? 'btn btn-primary' : 'btn btn-secondary'} href={confirmMail}>
                  {result.ctas[1] ?? 'Ask us to confirm'}
                </a>
              </>
            )}
          </div>

          <div
            className={`trailer-match-delivery-block card card-pad${deliveryProminent ? ' trailer-match-delivery-emphasized' : ''}`}
          >
            <h2 className="trailer-match-h2">Not comfortable towing?</h2>
            <p className="muted">
              We may be able to deliver or haul materials for you. Request a delivery quote—it is separate from the trailer
              size above and does not change that recommendation.
            </p>
            {(result.delivery_cta_emphasized || result.mode === 'delivery_suggested') && result.delivery_cta_reason ? (
              <p className="muted trailer-match-delivery-reason" role="note">
                We highlighted this because: {result.delivery_cta_reason}
              </p>
            ) : null}
            <div className="trailer-match-cta-row">
              <button
                type="button"
                className={deliveryProminent ? 'btn btn-secondary' : 'btn btn-ghost'}
                disabled={deliveryClickBusy}
                onClick={() => void onDeliveryQuoteClick()}
              >
                {deliveryClickBusy ? 'Opening…' : 'Request a delivery quote'}
              </button>
              <Link to="/#delivery-quote" className="btn btn-ghost">
                How delivery works
              </Link>
            </div>
          </div>

          <p className="muted trailer-match-foot">
            <Link to="/catalog">Back to catalog</Link>
            {' · '}
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setResult(null); setStep(1) }}>
              Start over
            </button>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="container trailer-match-page">
      <div className="card card-pad trailer-match-card">
        <p className="trailer-match-kicker">Trailer Match Assistant</p>
        <h1 className="trailer-match-title">Find a good dump trailer match</h1>
        <p className="muted trailer-match-lead">
          A few plain-English questions about your truck and load—we’ll suggest which trailer to rent or tow.{' '}
          <strong>Not</strong> a certified safety calculator. We’ll ask about delivery only after you see the match.
        </p>

        <div className="trailer-match-progress" aria-hidden="true">
          {[1, 2, 3].map((s) => (
            <span key={s} className={`trailer-match-dot${step >= s ? ' active' : ''}`} />
          ))}
        </div>
        <p className="trailer-match-step-label muted">
          Step {step} of 3 — {stepTitle(step)}
        </p>

        {error ? <p className="trailer-match-error">{error}</p> : null}

        {step === 1 ? (
          <div className="trailer-match-fields">
            <label className="field">
              <span className="field-label">Year</span>
              <input
                className="input"
                type="number"
                inputMode="numeric"
                min={1980}
                max={2035}
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
              />
            </label>
            <label className="field">
              <span className="field-label">Make</span>
              <input className="input" value={make} onChange={(e) => setMake(e.target.value)} placeholder="e.g. Ford" />
            </label>
            <label className="field">
              <span className="field-label">Model</span>
              <input className="input" value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. F-150" />
            </label>
            <label className="field field-span">
              <span className="field-label">Trim or engine (optional)</span>
              <input
                className="input"
                value={trim}
                onChange={(e) => setTrim(e.target.value)}
                placeholder="Helps us guess light vs. heavy-duty trucks"
              />
            </label>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="trailer-match-fields">
            <fieldset className="field field-span">
              <legend className="field-label">Factory tow package</legend>
              <div className="trailer-match-chip-row">
                {(['yes', 'no', 'unknown'] as const).map((v) => (
                  <label key={v} className="trailer-match-chip">
                    <input type="radio" name="tow" checked={towPackage === v} onChange={() => setTowPackage(v)} />
                    {v === 'yes' ? 'Yes' : v === 'no' ? 'No' : 'Not sure'}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset className="field field-span">
              <legend className="field-label">In-dash trailer brake controller</legend>
              <p className="muted field-span">Electric-brake trailers usually need a working controller installed and set up correctly.</p>
              <div className="trailer-match-chip-row">
                {(['yes', 'no', 'unknown'] as const).map((v) => (
                  <label key={v} className="trailer-match-chip">
                    <input type="radio" name="brake" checked={brake === v} onChange={() => setBrake(v)} />
                    {v === 'yes' ? 'Yes' : v === 'no' ? 'No' : 'Not sure'}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset className="field field-span">
              <legend className="field-label">Towing experience</legend>
              <div className="trailer-match-chip-row">
                {(
                  [
                    ['first_time', 'First time'],
                    ['some', 'Some experience'],
                    ['experienced', 'Experienced'],
                  ] as const
                ).map(([v, label]) => (
                  <label key={v} className="trailer-match-chip">
                    <input type="radio" name="exp" checked={experience === v} onChange={() => setExperience(v)} />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="trailer-match-fields">
            <label className="field field-span">
              <span className="field-label">Load type</span>
              <select className="input" value={loadType} onChange={(e) => setLoadType(e.target.value as Load)}>
                {(Object.keys(LOAD_LABELS) as Load[]).map((k) => (
                  <option key={k} value={k}>
                    {LOAD_LABELS[k]}
                  </option>
                ))}
              </select>
            </label>
            <label className="field field-span">
              <span className="field-label">Estimated amount</span>
              <select className="input" value={amount} onChange={(e) => setAmount(e.target.value as Amount)}>
                {(Object.keys(AMOUNT_LABELS) as Amount[]).map((k) => (
                  <option key={k} value={k}>
                    {AMOUNT_LABELS[k]}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted field-span">
              Cubic yards are approximate—use your best guess. If you are not sure, pick “Not sure yet” and we will stay conservative.
            </p>
            <div className="trailer-match-recap card card-pad muted field-span">
              <strong>Recap:</strong> {year} {make} {model}
              {trim.trim() ? ` (${trim.trim()})` : ''} · {LOAD_LABELS[loadType]} · {AMOUNT_LABELS[amount]}
            </div>
          </div>
        ) : null}

        <div className="trailer-match-nav">
          {step > 1 && step < 4 ? (
            <button type="button" className="btn btn-ghost" onClick={() => setStep((s) => Math.max(1, s - 1))}>
              Back
            </button>
          ) : (
            <span />
          )}
          {step < 3 ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={(step === 1 && !canNext1) || submitting}
              onClick={() => setStep((s) => Math.min(3, s + 1))}
            >
              Continue
            </button>
          ) : (
            <button type="button" className="btn btn-primary" disabled={!canSubmit || submitting} onClick={() => void submit()}>
              {submitting ? 'Working…' : 'Get recommendation'}
            </button>
          )}
        </div>

        <p className="muted trailer-match-foot">
          <Link to="/catalog">Back to catalog</Link>
        </p>
      </div>
    </div>
  )
}
