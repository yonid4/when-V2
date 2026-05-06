export const metadata = {
    title: 'Terms of Service | When.',
  }
  
  export default function TermsPage() {
    return (
      <main className="min-h-screen bg-surface text-on-surface">
        <div className="mx-auto max-w-4xl px-6 py-16 md:py-20">
          <h1 className="text-4xl font-headline font-extrabold tracking-tight text-primary md:text-5xl">
            Terms of Service
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
            <h2>1. Agreement to Terms</h2>
            <p>
              By accessing or using When. (&quot;the Service&quot;), you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use the Service.
            </p>
            <p>
              <strong>Personal Project Notice:</strong> When. is a non-commercial, personal project. It is provided for portfolio demonstration and personal utility.
            </p>
  
            <h2>2. Description of Service</h2>
            <p>
              When. is an event coordination tool that integrates with Google Calendar to help users visualize group availability.
            </p>
  
            <h2>3. Google API Services & Data</h2>
            <p>
              The Service integrates with Google API Services to read and write event data. 
            </p>
            <ul>
              <li>
                The Service&apos;s use and transfer to any other app of information received from Google APIs will adhere to the{' '}
                <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noopener noreferrer">
                  Google API Services User Data Policy
                </a>
                , including the <strong>Limited Use requirements</strong>.
              </li>
              <li>
                You may revoke permissions at any time via your Google account settings or by disconnecting your calendar within the app.
              </li>
            </ul>
  
            <h2>4. User Responsibilities</h2>
            <p>
              You are responsible for your account security and all activities under your login. You agree not to:
            </p>
            <ul>
              <li>Use the Service for illegal activities or to distribute malicious content.</li>
              <li>Attempt to disrupt the Service&apos;s infrastructure or security.</li>
              <li>Misrepresent your identity or use others&apos; account information.</li>
            </ul>
  
            <h2>5. Intellectual Property</h2>
            <p>
              The Service and its original code/design are the property of the developer. You retain ownership of your personal data, but grant us a limited license to process it solely to provide the Service functionality.
            </p>
  
            <h2>6. No Warranty</h2>
            <p>
              THE SERVICE IS PROVIDED <strong>&quot;AS IS&quot;</strong> WITHOUT WARRANTIES OF ANY KIND. The developer does not guarantee that the Service will be error-free, secure, or available at all times. Use of the Service is at your own risk.
            </p>
  
            <h2>7. Limitation of Liability</h2>
            <p>
              TO THE FULLEST EXTENT PERMITTED BY LAW, THE DEVELOPER SHALL NOT BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES (INCLUDING DATA LOSS OR FINANCIAL LOSS) ARISING FROM YOUR USE OF THE SERVICE. 
            </p>
            <p>
              In no event shall the total liability to you for all damages exceed **$0.00**, as this is a free personal project.
            </p>
  
            <h2>8. Indemnification</h2>
            <p>
              You agree to defend and hold the developer harmless from and against any claims, damages, obligations, losses, liabilities, costs, or debt, and expenses (including attorney&apos;s fees) resulting from: (i) your use and access of the Service; or (ii) a breach of these Terms.
            </p>
  
            <h2>9. Termination & Account Deletion</h2>
            <p>
              <strong>By the Developer:</strong> I reserve the right to modify or terminate the Service at any time, for any reason, without notice. 
            </p>
            <p>
              <strong>By the User:</strong> You may stop using the Service at any time. You can delete your account and all associated data directly through the &quot;Delete Account&quot; feature in your account settings. Once deleted, this action is permanent and data cannot be recovered.
            </p>
  
            <h2>10. Governing Law</h2>
            <p>
              These Terms are governed by the laws of the State of California, USA, without regard to its conflict of law provisions.
            </p>
  
            <h2>11. Contact Information</h2>
            <p>
              If you have any questions about these Terms, please contact:
              {' '}
              <a href="mailto:whenapp.now@gmail.com">whenapp.now@gmail.com</a>.
            </p>
          </article>
        </div>
      </main>
    )
  }