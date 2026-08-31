import { test, expect } from '@playwright/test'

import { safeAppReturnTo } from '../src/auth0/returnTo'

const ITEM = '/items/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'

test.describe('Auth0 returnTo allowlist', () => {
  test('allows known in-app paths', () => {
    expect(safeAppReturnTo('/')).toBe('/')
    expect(safeAppReturnTo('/catalog')).toBe('/catalog')
    expect(safeAppReturnTo('/trailer-match')).toBe('/trailer-match')
    expect(safeAppReturnTo(ITEM)).toBe(ITEM)
    expect(safeAppReturnTo('/my-rentals')).toBe('/my-rentals')
    expect(safeAppReturnTo(`${ITEM}?x=1`)).toBe(`${ITEM}?x=1`)
  })

  test('rejects external and malformed returnTo (no open redirect)', () => {
    expect(safeAppReturnTo('https://evil.example')).toBe('/')
    expect(safeAppReturnTo('http://evil.example/phish')).toBe('/')
    expect(safeAppReturnTo('//evil.example')).toBe('/')
    expect(safeAppReturnTo('///evil.example')).toBe('/')
    expect(safeAppReturnTo('javascript:alert(1)')).toBe('/')
    expect(safeAppReturnTo('\\evil.example')).toBe('/')
    expect(safeAppReturnTo('/\\evil.example')).toBe('/')
    expect(safeAppReturnTo('https://bohachickrentals.com/catalog')).toBe('/')
    expect(safeAppReturnTo('/items/not-a-uuid')).toBe('/')
    expect(safeAppReturnTo('/login')).toBe('/')
    expect(safeAppReturnTo('/catalog/../https://evil.example')).toBe('/')
    expect(safeAppReturnTo('')).toBe('/')
    expect(safeAppReturnTo(undefined)).toBe('/')
    expect(safeAppReturnTo('/catalog%2f%2fevil.example')).toBe('/')
  })
})
