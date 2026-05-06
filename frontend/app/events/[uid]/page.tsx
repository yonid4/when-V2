import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
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

  return <EventDetailClient uid={uid} />
}
