import { cookies } from 'next/headers'
import { redirect, notFound } from 'next/navigation'
import { fetchEvent } from './fetchers'
import EventDetailClient from './EventDetailClient'

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ uid: string }>
}) {
  const [{ uid }, cookieStore] = await Promise.all([params, cookies()])
  const token = cookieStore.get('token')?.value

  if (!token) {
    redirect('/')
  }

  const event = await fetchEvent(uid, token)

  if (!event) {
    notFound()
  }

  return <EventDetailClient event={event} />
}
