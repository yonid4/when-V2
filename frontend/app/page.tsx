'use client'

import { ArrowRight, RefreshCw, Sparkles } from 'lucide-react'
import Link from 'next/link'

type FooterLink = {
  label: string
  href?: string
}

const footerLinks: FooterLink[] = [
  { label: 'Privacy', href: '/privacy' },
  { label: 'Terms', href: '/terms' },
  { label: 'Support' },
]

export default function LandingPage() {
  const handleGoogleSignIn = () => {
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL}/auth/google`
  }

  return (
    <div className="bg-surface text-on-surface font-body selection:bg-primary-container selection:text-on-primary-container">
      {/* Top Nav */}
      <nav className="fixed top-0 w-full z-50 bg-surface/80 backdrop-blur-md">
        <div className="flex justify-between items-center px-6 py-4 max-w-7xl mx-auto">
          <div className="text-2xl font-bold tracking-tight text-primary font-headline">When.</div>
          <div className="hidden md:flex items-center space-x-12">
            <a
              href="#how-it-works"
              className="font-headline tracking-wide text-sm font-medium text-on-surface-variant hover:text-primary transition-colors duration-300"
            >
              How it works
            </a>
            <a
              href="#features"
              className="font-headline tracking-wide text-sm font-medium text-on-surface-variant hover:text-primary transition-colors duration-300"
            >
              Features
            </a>
          </div>
          <button
            onClick={handleGoogleSignIn}
            className="bg-gradient-to-br from-primary to-primary-container text-on-primary px-6 py-2.5 rounded-full font-headline font-semibold text-sm active:opacity-80 transition-transform shadow-[0_10px_20px_-5px_rgba(155,68,40,0.2)]"
          >
            Get Started
          </button>
        </div>
      </nav>

      <main className="pt-32">
        {/* Hero Section */}
        <section className="max-w-7xl mx-auto px-6 mb-32">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="space-y-8 max-w-xl">
              <h1 className="text-5xl md:text-7xl font-headline font-extrabold tracking-tight text-on-surface leading-[1.1]">
                Group scheduling,{' '}
                <span className="text-primary italic">finally</span> painless
              </h1>
              <p className="text-xl text-on-surface-variant leading-relaxed tracking-wide">
                When. helps friends and colleagues find the perfect time to gather by syncing Google
                Calendars and surfacing the best options automatically.
              </p>
              <div className="flex flex-wrap items-center gap-6">
                <button
                  onClick={handleGoogleSignIn}
                  className="bg-gradient-to-br from-primary to-primary-container text-on-primary px-8 py-4 rounded-xl font-headline font-bold text-lg hover:translate-y-[-4px] transition-all duration-500 shadow-[0_20px_40px_-15px_rgba(155,68,40,0.15)]"
                >
                  Get Started
                </button>
                <a
                  href="#how-it-works"
                  className="flex items-center gap-2 text-primary font-headline font-bold hover:gap-4 transition-all"
                >
                  See how it works
                  <ArrowRight className="w-5 h-5" />
                </a>
              </div>
            </div>

            {/* Availability Grid Mockup */}
            <div className="relative group">
              <div className="absolute -inset-4 bg-primary/5 rounded-[4rem] blur-3xl group-hover:bg-primary/10 transition-colors duration-700" />
              <div className="relative bg-surface-container-lowest p-8 rounded-xl shadow-[0_20px_50px_-20px_rgba(155,68,40,0.12)] border border-outline-variant/10">
                <div className="flex justify-between items-center mb-8">
                  <div className="space-y-1">
                    <h3 className="font-headline font-bold text-lg">Sunday Dinner</h3>
                    <p className="text-xs text-on-surface-variant font-medium tracking-widest uppercase">
                      October 14 – 20
                    </p>
                  </div>
                  <div className="flex -space-x-2">
                    <div className="w-8 h-8 rounded-full border-2 border-white bg-secondary-container flex items-center justify-center text-[10px] font-bold">
                      JD
                    </div>
                    <div className="w-8 h-8 rounded-full border-2 border-white bg-tertiary-container flex items-center justify-center text-[10px] font-bold">
                      AS
                    </div>
                    <div className="w-8 h-8 rounded-full border-2 border-white bg-primary-container flex items-center justify-center text-[10px] font-bold">
                      MK
                    </div>
                  </div>
                </div>

                {/* Heatmap Grid */}
                <div className="grid grid-cols-7 gap-1">
                  {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((day, i) => (
                    <div
                      key={i}
                      className={`text-[10px] text-center font-bold uppercase pb-2 ${i >= 5 ? 'text-primary' : 'text-outline'}`}
                    >
                      {day}
                    </div>
                  ))}
                  {/* Row 1 */}
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-fixed rounded-sm" />
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-container/40 rounded-sm" />
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-container rounded-sm" />
                  <div className="aspect-square bg-primary rounded-sm shadow-sm scale-110" />
                  {/* Row 2 */}
                  <div className="aspect-square bg-primary-fixed rounded-sm" />
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-container/60 rounded-sm" />
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-container/20 rounded-sm" />
                  <div className="aspect-square bg-primary-container rounded-sm" />
                  <div className="aspect-square bg-primary rounded-sm" />
                  {/* Row 3 */}
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-container/30 rounded-sm" />
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-fixed rounded-sm" />
                  <div className="aspect-square bg-surface-container rounded-sm" />
                  <div className="aspect-square bg-primary-container rounded-sm" />
                  <div className="aspect-square bg-primary rounded-sm" />
                </div>

                <div className="mt-8 flex justify-end">
                  <div className="bg-secondary-container text-on-secondary-container px-4 py-1.5 rounded-full text-xs font-bold flex items-center gap-2">
                    <svg
                      className="w-4 h-4"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                    >
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                    </svg>
                    Sunday at 7:00 PM is best
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section
          id="how-it-works"
          className="py-24 bg-surface-container-low rounded-[4rem] mx-4 md:mx-12 overflow-hidden"
        >
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-20 space-y-4">
              <h2 className="text-4xl md:text-5xl font-headline font-extrabold tracking-tight text-on-surface">
                From gathering to great times{' '}
                <br className="hidden md:block" />
                in three steps
              </h2>
            </div>
            <div className="grid md:grid-cols-3 gap-12 relative">
              <div className="space-y-6 group">
                <div className="w-16 h-16 bg-surface-container-lowest rounded-2xl flex items-center justify-center text-primary font-headline font-black text-2xl shadow-sm transition-transform group-hover:rotate-6 duration-500">
                  01
                </div>
                <h3 className="text-2xl font-headline font-bold">Create an event</h3>
                <p className="text-on-surface-variant leading-relaxed">
                  Set a scheduling window, give it a name, and choose the duration. No complex
                  settings required.
                </p>
              </div>
              <div className="space-y-6 group">
                <div className="w-16 h-16 bg-surface-container-lowest rounded-2xl flex items-center justify-center text-primary font-headline font-black text-2xl shadow-sm transition-transform group-hover:-rotate-6 duration-500">
                  02
                </div>
                <h3 className="text-2xl font-headline font-bold">Invite the group</h3>
                <p className="text-on-surface-variant leading-relaxed">
                  Participants sync their Google Calendar in one click and mark their preferred
                  slots with a simple swipe.
                </p>
              </div>
              <div className="space-y-6 group">
                <div className="w-16 h-16 bg-surface-container-lowest rounded-2xl flex items-center justify-center text-primary font-headline font-black text-2xl shadow-sm transition-transform group-hover:rotate-12 duration-500">
                  03
                </div>
                <h3 className="text-2xl font-headline font-bold">Pick the winner</h3>
                <p className="text-on-surface-variant leading-relaxed">
                  When. ranks the best times based on everyone&apos;s availability, including travel time
                  and time zones.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Highlights */}
        <section id="features" className="py-32 max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            {/* Main Feature */}
            <div className="md:col-span-8 bg-surface-container-lowest p-12 rounded-xl flex flex-col justify-between border border-outline-variant/10 hover:translate-y-[-4px] transition-all duration-500">
              <div className="space-y-4">
                <RefreshCw className="w-10 h-10 text-primary" />
                <h3 className="text-3xl font-headline font-extrabold tracking-tight">
                  Real availability, not guesses
                </h3>
                <p className="text-on-surface-variant text-lg max-w-md">
                  Direct Google Calendar sync ensures you&apos;re never looking at stale data. We see the
                  gaps so you don&apos;t have to.
                </p>
              </div>
              <div className="mt-12 flex flex-wrap gap-3">
                <span className="bg-surface-container-high px-4 py-2 rounded-full text-xs font-bold tracking-wider text-on-surface-variant uppercase">
                  Zero Overlaps
                </span>
                <span className="bg-surface-container-high px-4 py-2 rounded-full text-xs font-bold tracking-wider text-on-surface-variant uppercase">
                  Deep Integration
                </span>
              </div>
            </div>

            {/* Secondary 1 */}
            <div className="md:col-span-4 bg-tertiary-fixed p-10 rounded-xl border border-outline-variant/10 hover:translate-y-[-4px] transition-all duration-500 flex flex-col justify-between">
              <svg
                className="w-10 h-10 text-tertiary"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
              </svg>
              <div>
                <h3 className="text-2xl font-headline font-bold mt-4">Mark your preferences</h3>
                <p className="text-on-tertiary-fixed-variant mt-2">
                  Highlight the specific times that work best for you, not just when you&apos;re free.
                </p>
              </div>
            </div>

            {/* Secondary 2 */}
            <div className="md:col-span-4 bg-secondary-container p-10 rounded-xl border border-outline-variant/10 hover:translate-y-[-4px] transition-all duration-500 flex flex-col justify-between">
              <Sparkles className="w-10 h-10 text-secondary" />
              <div>
                <h3 className="text-2xl font-headline font-bold mt-4">Smart time proposals</h3>
                <p className="text-on-secondary-container mt-2">
                  Our algorithm ranks slots based on who&apos;s free and who prefers them.
                </p>
              </div>
            </div>

            {/* Photo card */}
            <div className="md:col-span-8 overflow-hidden rounded-xl h-64 relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuC76nEAw9VcNphL2-1_86HuzTWdAzUxaqTJZXBVlLRivsvvBYpRfBaCSJowQG7x-8cjGoVX_Jr6uwzAeoLtYUatJkGNSwsdd3gnLBUP5NmOk25Vs5y1a7xP0Wu7pi8Njmpue_pl3mHgvqeWTQZYa9qyr1h93b-0c5PvVGNEnyiMdEE8djxojqnFjWpVVdLQdJOd6XUBvqtTzyUES7E9FpyPJXItW9zjBLE449vQOT_GkCT8XmLKbaeitCJsCSKePAZKK6Je3E8KDqrz"
                alt="A group of friends laughing and talking around a wooden dinner table"
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
              <div className="absolute bottom-6 left-8 text-white">
                <p className="font-headline font-bold text-xl">
                  Focus on the gathering, not the grid.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Bottom CTA Banner */}
        <section className="max-w-7xl mx-auto px-6 mb-32">
          <div className="bg-gradient-to-br from-primary to-[#c4563a] rounded-[3rem] p-16 md:p-24 text-center text-on-primary relative overflow-hidden">
            <div className="absolute top-0 right-0 w-96 h-96 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />
            <div className="relative z-10 space-y-10">
              <h2 className="text-4xl md:text-6xl font-headline font-extrabold tracking-tight">
                Ready to stop playing <br /> calendar tag?
              </h2>
              <div className="flex flex-col items-center gap-6">
                <button
                  onClick={handleGoogleSignIn}
                  className="bg-white text-primary px-10 py-5 rounded-xl font-headline font-bold text-xl hover:scale-105 transition-transform shadow-xl"
                >
                  Create your first event
                </button>
                <p className="text-white/80 font-medium tracking-wide">
                  Join 10,000+ groups gathering with When.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="w-full rounded-t-[3rem] mt-20 bg-surface-container-low">
        <div className="flex flex-col md:flex-row justify-between items-center px-12 py-16 w-full max-w-7xl mx-auto gap-12">
          <div className="space-y-4 text-center md:text-left">
            <div className="text-lg font-bold text-primary font-headline">When.</div>
            <p className="text-on-surface-variant max-w-xs font-body tracking-wider text-xs uppercase leading-relaxed">
              © 2024 When. Crafted with tactile hospitality.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-8 md:gap-12">
            {footerLinks.map((link) =>
              link.href ? (
                <Link
                  key={link.label}
                  href={link.href}
                  className="font-body tracking-wider text-xs uppercase text-on-surface-variant hover:text-primary transition-opacity"
                >
                  {link.label}
                </Link>
              ) : (
                <button
                  key={link.label}
                  type="button"
                  className="font-body tracking-wider text-xs uppercase text-on-surface-variant hover:text-primary transition-opacity"
                >
                  {link.label}
                </button>
              )
            )}
          </div>
        </div>
      </footer>
    </div>
  )
}
