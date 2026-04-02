'use client'

import { Calendar } from 'lucide-react'

export default function LandingPage() {
  const handleGoogleSignIn = () => {
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL}/auth/google`
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden bg-surface text-on-surface">
      {/* Ambient background blobs */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] w-[60%] h-[60%] rounded-full bg-primary/5 blur-[120px]" />
        <div className="absolute -bottom-[10%] -right-[5%] w-[40%] h-[40%] rounded-full bg-tertiary-container/5 blur-[100px]" />
      </div>

      <div className="relative z-10 w-full max-w-md flex flex-col items-center text-center">
        {/* Logo */}
        <div className="mb-12">
          <h1 className="text-8xl font-extrabold text-primary tracking-tighter [text-shadow:0_0_40px_rgba(155,68,40,0.1)]">
            When.
          </h1>
          <p className="mt-6 text-lg text-on-surface-variant font-medium tracking-wide max-w-xs mx-auto">
            Find a time that works for everyone.
          </p>
        </div>

        {/* Login card */}
        <div className="w-full bg-surface-container-lowest rounded-3xl p-8 shadow-[0_20px_40px_-15px_rgba(155,68,40,0.06)] ring-1 ring-outline-variant/10">
          <button
            onClick={handleGoogleSignIn}
            className="w-full group flex items-center justify-center gap-4 bg-surface hover:bg-surface-container-high transition-all duration-300 py-4 px-6 rounded-2xl ring-1 ring-outline-variant/20 active:scale-[0.98]"
          >
            <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
            <span className="font-semibold text-on-surface tracking-wide">Sign in with Google</span>
          </button>
        </div>

        {/* Decorative stacked cards */}
        <div className="mt-16 relative w-full h-64 opacity-60 pointer-events-none">
          <div className="absolute left-1/2 top-0 -translate-x-[40%] w-48 h-60 bg-secondary-container rounded-2xl rotate-6 shadow-sm border border-secondary/10" />
          <div className="absolute left-1/2 top-4 -translate-x-[60%] w-48 h-60 bg-tertiary-container rounded-2xl -rotate-3 shadow-md border border-tertiary/10">
            <div className="p-4 flex flex-col gap-2">
              <div className="h-2 w-24 bg-on-tertiary-container/20 rounded-full" />
              <div className="h-2 w-16 bg-on-tertiary-container/10 rounded-full" />
              <div className="mt-4 flex flex-wrap gap-1">
                <div className="w-6 h-6 rounded-full bg-primary/20" />
                <div className="w-6 h-6 rounded-full bg-secondary/20" />
                <div className="w-6 h-6 rounded-full bg-tertiary/20" />
              </div>
            </div>
          </div>
          <div className="absolute left-1/2 top-8 -translate-x-1/2 w-52 h-64 bg-surface-container-lowest rounded-2xl rotate-1 shadow-xl flex flex-col items-center justify-center p-6">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-primary-container mb-4 flex items-center justify-center">
              <Calendar className="w-6 h-6 text-on-primary" />
            </div>
            <div className="w-32 h-3 bg-surface-container-high rounded-full mb-2" />
            <div className="w-20 h-2 bg-surface-container-low rounded-full" />
          </div>
        </div>

        <footer className="mt-auto pt-12">
          <p className="text-sm text-outline font-medium tracking-wide">
            Making moments happen, one calendar at a time.
          </p>
        </footer>
      </div>
    </main>
  )
}
