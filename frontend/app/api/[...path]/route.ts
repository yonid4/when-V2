import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.API_URL ?? 'http://localhost:8000'

async function proxyRequest(req: NextRequest, params: { path: string[] }): Promise<NextResponse> {
  const path = params.path.join('/')
  const search = req.nextUrl.search
  const url = `${BACKEND_URL}/${path}${search}`

  const headers = new Headers()
  const authorization = req.headers.get('authorization')
  if (authorization) {
    headers.set('authorization', authorization)
  }
  const contentType = req.headers.get('content-type')
  if (contentType) {
    headers.set('content-type', contentType)
  }

  let body: BodyInit | null = null
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    body = await req.text()
  }

  const backendRes = await fetch(url, {
    method: req.method,
    headers,
    body: body || undefined,
  })

  const responseHeaders = new Headers()
  const backendContentType = backendRes.headers.get('content-type')
  if (backendContentType) {
    responseHeaders.set('content-type', backendContentType)
  }

  const responseBody = await backendRes.text()

  return new NextResponse(responseBody, {
    status: backendRes.status,
    headers: responseHeaders,
  })
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params)
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params)
}

export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params)
}

export async function PATCH(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params)
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params)
}
