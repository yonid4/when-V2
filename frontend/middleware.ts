import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_ONLY_PATHS = ['/']
const PUBLIC_PATHS = [...PUBLIC_ONLY_PATHS, '/auth/callback', '/privacy', '/terms']

export function middleware(req: NextRequest): NextResponse {
  const { pathname } = req.nextUrl
  // Presence check only — middleware runs server-side, so it can read the
  // HttpOnly `session` cookie (the JWT itself is verified by the backend).
  const session = req.cookies.get('session')?.value

  // Redirect authenticated users away from public-only pages
  if (PUBLIC_ONLY_PATHS.includes(pathname) && session) {
    return NextResponse.redirect(new URL('/dashboard', req.url))
  }

  // Allow public paths and Next.js internals through without auth check
  if (
    PUBLIC_PATHS.includes(pathname) ||
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/favicon')
  ) {
    return NextResponse.next()
  }

  if (!session) {
    return NextResponse.redirect(new URL('/', req.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
