import Link from 'next/link'

export const metadata = {
  title: 'Privacy Policy | When.',
}

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-surface text-on-surface">
      <nav className="sticky top-0 z-50 border-b border-outline-variant/20 bg-surface/80 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-2xl font-bold tracking-tight text-primary font-headline">
            When.
          </Link>
          <div className="flex items-center gap-6 text-sm font-medium text-on-surface-variant">
            <Link href="/privacy" className="text-primary">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-primary transition-colors">
              Terms
            </Link>
          </div>
        </div>
      </nav>
      <div className="mx-auto max-w-4xl px-6 py-16 md:py-20">
        <h1 className="text-4xl font-headline font-extrabold tracking-tight text-primary md:text-5xl">
          Privacy Policy
        </h1>
        <p className="mt-3 text-sm text-on-surface-variant">Effective Date: May 6, 2026</p>
        <p className="text-sm text-on-surface-variant">Last Updated: May 6, 2026</p>
        <p className="text-sm text-on-surface-variant">Application: When. (https://when-now.com)</p>

        <article
          className="mt-10 max-w-none rounded-2xl border border-outline-variant/20 bg-surface-container-low p-6 text-on-surface md:p-8
          [&_h2]:mt-10 [&_h2]:mb-4 [&_h2]:text-2xl [&_h2]:font-extrabold [&_h2]:tracking-tight
          [&_h3]:mt-8 [&_h3]:mb-3 [&_h3]:text-lg [&_h3]:font-bold
          [&_p]:my-4 [&_p]:text-sm [&_p]:leading-7
          [&_ul]:my-4 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6
          [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:space-y-2 [&_ol]:pl-6
          [&_li]:leading-7
          [&_table]:my-5 [&_table]:w-full [&_table]:border-collapse [&_table]:text-sm
          [&_th]:border [&_th]:border-outline-variant/30 [&_th]:bg-surface-container [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-bold
          [&_td]:border [&_td]:border-outline-variant/30 [&_td]:px-3 [&_td]:py-2
          [&_a]:font-semibold [&_a]:underline"
        >
          <h2>Introduction</h2>
          <p>
            When. (&quot;we,&quot; &quot;our,&quot; or &quot;the Service&quot;) is a group scheduling application that helps
            people find meeting times that work for everyone. We take your privacy seriously and
            built When. with a deliberate principle: collect the minimum data necessary, and never
            look at what we do not need.
          </p>
          <p>
            This Privacy Policy explains what we collect, how we use it, how we protect it, and how
            you can remove it. If you have questions, contact us at
            {' '}
            <a href="mailto:whenapp.now@gmail.com">whenapp.now@gmail.com</a>.
          </p>

          <h2>1. Data We Collect</h2>
          <h3>1.1 When You Sign In with Google</h3>
          <ul>
            <li>Your email address</li>
            <li>Your full name</li>
            <li>Your profile picture (avatar) URL</li>
          </ul>
          <p>
            We also generate a unique internal user ID and store your selected timezone. We do not
            access your Google Calendar during sign-in.
          </p>

          <h3>1.2 When You Connect Your Google Calendar</h3>
          <ul>
            <li>The Gmail address of the connected account</li>
            <li>Your Google account identifier</li>
            <li>OAuth access token, refresh token, and expiry timestamp</li>
            <li>A list of your calendars so you can choose which ones to include</li>
          </ul>

          <h3>1.3 What We Collect from Your Calendar</h3>
          <p>
            We read only event start and end times, plus an internal Google event ID used for sync.
            We do not collect event titles, descriptions, locations, attendees, or other event
            content.
          </p>
          <table>
            <thead>
              <tr>
                <th>Field We Store</th>
                <th>Purpose</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>start_time_utc</td>
                <td>When the busy block begins</td>
              </tr>
              <tr>
                <td>end_time_utc</td>
                <td>When the busy block ends</td>
              </tr>
              <tr>
                <td>provider_event_id</td>
                <td>Used only for deduplication and deletion detection</td>
              </tr>
            </tbody>
          </table>
          <p>All-day and cancelled events are skipped.</p>

          <h3>1.4 Data You Choose to Provide</h3>
          <ul>
            <li>Preferred time slots for specific events</li>
            <li>Notes on proposed times</li>
            <li>Acceptance status for invited events</li>
          </ul>

          <h2>2. How We Use Your Data</h2>
          <p>
            We use your data only to help groups find meeting times that work for everyone.
          </p>
          <h3>2.1 Availability Heatmap</h3>
          <ul>
            <li>Reads participant busy slots and preferences</li>
            <li>Computes aggregate availability counts in memory</li>
            <li>Returns only aggregate counts for display</li>
            <li>Does not create extra persistent availability records</li>
          </ul>
          <h3>2.2 Smart Proposal Ranking</h3>
          <ol>
            <li>Generate candidate time slots in 30-minute intervals</li>
            <li>Count overlaps with busy and preferred slots</li>
            <li>Rank by lowest conflicts, then highest preferences, then earliest start</li>
            <li>Save only top 5 suggestions with anonymous counts</li>
          </ol>
          <p>
            We do not use your data for advertising, profiling, or training machine learning models.
          </p>

          <h2>3. How We Store and Protect Your Data</h2>
          <h3>3.1 Infrastructure</h3>
          <ul>
            <li>Stored in PostgreSQL on Supabase</li>
            <li>Encrypted at rest (AES-256)</li>
            <li>Encrypted in transit (TLS)</li>
          </ul>
          <h3>3.2 Row Level Security</h3>
          <p>
            PostgreSQL RLS policies enforce access control so users can only access data they are
            authorized to see.
          </p>
          <h3>3.3 OAuth Tokens</h3>
          <p>
            Google tokens are stored as encrypted records and accessed only by authenticated server
            processes that need them for calendar sync.
          </p>

          <h2>4. Background Calendar Sync</h2>
          <ul>
            <li>Runs once per hour</li>
            <li>Reads events from now up to 90 days ahead</li>
            <li>Extracts only start/end times and Google event IDs</li>
            <li>Deletes busy slots for deleted/cancelled Google events</li>
            <li>Stops access immediately if refresh token is revoked</li>
          </ul>

          <h2>5. Data Retention and Deletion</h2>
          <h3>5.1 Disconnecting a Calendar</h3>
          <ul>
            <li>Revokes Google OAuth tokens immediately</li>
            <li>Deletes associated calendar account record and credentials</li>
            <li>Removes busy slots for that calendar</li>
          </ul>
          <h3>5.2 Deleting an Event</h3>
          <p>
            Deleting an event removes participant lists, preferred slots, proposed times, and notes
            through database cascade rules.
          </p>
          <h3>5.3 Deleting Your Account</h3>
          <ol>
            <li>Disconnect all connected calendars and revoke tokens</li>
            <li>Delete profile and related personal records</li>
            <li>Delete planning-stage events you coordinated</li>
            <li>Anonymize your identity from already confirmed coordinated events</li>
            <li>Remove your participation from other users&apos; events</li>
          </ol>
          <p>
            You can also request deletion by emailing
            {' '}
            <a href="mailto:whenapp.now@gmail.com">whenapp.now@gmail.com</a>
            {' '}
            from your account email.
          </p>

          <h2>6. Third-Party Sharing</h2>
          <p>
            We do not sell, rent, trade, or share your personal or calendar data with third parties.
          </p>
          <p>Limited exceptions include Google, Supabase, and valid legal requirements.</p>

          <h2>7. Google API Services User Data Policy</h2>
          <p>
            When. adheres to the
            {' '}
            <a href="https://developers.google.com/terms/api-services-user-data-policy">
              Google API Services User Data Policy
            </a>
            , including
            {' '}
            <a href="https://developers.google.com/terms/api-services-user-data-policy#additional_requirements_for_specific_api_scopes">
              Limited Use requirements
            </a>
            .
          </p>

          <h2>8. Google OAuth Scopes We Request</h2>
          <h3>Login</h3>
          <table>
            <thead>
              <tr>
                <th>Scope</th>
                <th>Why We Need It</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>openid</td>
                <td>Identify you and create a session</td>
              </tr>
              <tr>
                <td>userinfo.email</td>
                <td>Use your email as login identifier</td>
              </tr>
              <tr>
                <td>userinfo.profile</td>
                <td>Display your name and photo to participants</td>
              </tr>
            </tbody>
          </table>
          <h3>Calendar Connection</h3>
          <table>
            <thead>
              <tr>
                <th>Scope</th>
                <th>Why We Need It</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>calendar.readonly</td>
                <td>Read event start/end times for free/busy and deletion sync handling</td>
              </tr>
              <tr>
                <td>calendar.events</td>
                <td>Create finalized event on your chosen write calendar</td>
              </tr>
            </tbody>
          </table>

          <h2>9. Children&apos;s Privacy</h2>
          <p>
            When. is not directed to children under 13 (or under 16 in the EEA). If you believe a
            child has created an account, contact us and we will delete it.
          </p>

          <h2>10. International Users</h2>
          <p>
            The service operates from infrastructure primarily in the United States and European
            Union. By using the service, you consent to data transfer to these locations.
          </p>

          <h2>11. Your Rights</h2>
          <ul>
            <li>Access your personal data</li>
            <li>Correct inaccurate data</li>
            <li>Delete your data</li>
            <li>Export your data</li>
            <li>Object to or restrict certain processing</li>
            <li>Withdraw Google Calendar consent at any time</li>
          </ul>
          <p>
            To exercise these rights, email
            {' '}
            <a href="mailto:whenapp.now@gmail.com">whenapp.now@gmail.com</a>
            .
          </p>

          <h2>12. Security Incidents</h2>
          <p>
            If we become aware of a security incident affecting your data, we will notify you and
            relevant authorities within legally required timeframes.
          </p>

          <h2>13. Changes to This Policy</h2>
          <ul>
            <li>We update the Last Updated date</li>
            <li>We notify users by email for material changes</li>
            <li>We request renewed consent when required by law</li>
          </ul>

          <h2>14. Contact Us</h2>
          <p>
            For privacy questions, deletion requests, or rights requests, email
            {' '}
            <a href="mailto:whenapp.now@gmail.com">whenapp.now@gmail.com</a>
            .
          </p>
        </article>
      </div>
    </main>
  )
}
