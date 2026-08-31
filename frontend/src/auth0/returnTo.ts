/**
 * Restrict Auth0 appState.returnTo to same-origin application paths.
 * Rejects protocol-relative URLs, other origins, and unknown routes (open-redirect).
 */

const UUID =
  "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

const ALLOWED_PATH = new RegExp(
  `^(?:` +
    `/` +
    `|` +
    `/catalog` +
    `|` +
    `/trailer-match` +
    `|` +
    `/payment-success` +
    `|` +
    `/items/${UUID}` +
    `|` +
    `/booking/${UUID}/complete` +
    `|` +
    `/my-rentals` +
    `|` +
    `/my-rentals/${UUID}` +
    `|` +
    `/booking-actions/[A-Za-z0-9_-]+/(?:sign|complete)` +
    `|` +
    `/admin(?:/[A-Za-z0-9_-]+)*` +
    `)$`,
)

const DUMMY_ORIGIN = "https://brs.invalid"

function isAllowedPath(pathname: string): boolean {
  return ALLOWED_PATH.test(pathname)
}

/** Return a safe in-app path (pathname + search) or `/`. Never an external URL. */
export function safeAppReturnTo(raw: string | undefined | null): string {
  if (typeof raw !== "string") return "/"
  const trimmed = raw.trim()
  if (!trimmed) return "/"
  if (trimmed.includes("\\") || trimmed.includes("://")) return "/"
  if (!trimmed.startsWith("/") || trimmed.startsWith("//")) return "/"

  let url: URL
  try {
    url = new URL(trimmed, DUMMY_ORIGIN)
  } catch {
    return "/"
  }
  if (url.origin !== DUMMY_ORIGIN) return "/"
  if (url.username || url.password) return "/"
  if (!isAllowedPath(url.pathname)) return "/"
  return `${url.pathname}${url.search}`
}
