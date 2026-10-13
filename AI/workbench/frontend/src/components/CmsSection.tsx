import type { WorkflowResult } from '@/types'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { StatusBadge } from '@/components/StatusBadge'

const titles = {completed: 'Completed — workflow finished', ended: 'Ended — workflow did not continue', stopped: 'Stopped — business stop, not completed', failed: 'Failed — technical failure'}
const reasons: Record<string, string> = {
  tire_customer_open_tcm: 'Open TCM case for tire customer: send an email and handle this referral manually. Automation has stopped.',
  user_declined: 'The operator declined to continue. Automation has stopped.',
  customer_unresolved_or_cem: 'Customer unresolved or CEM: operator action is required. Automation has stopped.',
  incomplete: 'Required information is incomplete. Fix the fields below before continuing.',
  no_referral_attached: 'No referral attachment was found.', operator_cancelled: 'The operator cancelled review.',
}
export function CmsSection({result}: {result?: WorkflowResult | null}) {
  return <section className="cms-section" aria-label="CMS Customer Search">
    <h2>CMS Customer Search</h2>
    {!result ? <p className="empty-text">Waiting for workflow results.</p> : <>
      <div className={`cms-outcome cms-${result.outcome}`} data-outcome={result.outcome} role={result.outcome === 'stopped' || result.outcome === 'failed' ? 'alert' : 'status'}>
        <StatusBadge status={result.outcome} /><h3>{titles[result.outcome]}</h3>
        {result.reason && <><p className="cms-reason">{reasons[result.reason] || result.reason.replaceAll('_', ' ')}</p><p>Reason: {result.reason}</p></>}
        {result.outcome === 'ended' && result.reason === 'incomplete' && <><h4>Missing fields</h4><ul>{result.missing_fields.map((field, i) => <li key={i}>{field}</li>)}</ul>
          {!!result.confirmation_required?.length && <><h4>Confirm appointments</h4><ul>{result.confirmation_required.map((field, i) => <li key={i}>{field}</li>)}</ul></>}</>}
        {result.outcome === 'failed' && (result.error ? <dl><dt>Error stage</dt><dd>{result.error.stage}</dd><dt>Error type</dt><dd>{result.error.type}</dd><dt>Error message</dt><dd>{result.error.message}</dd></dl> : <p>No structured error details were supplied by the workflow.</p>)}
      </div>
      <Card><CardHeader><CardTitle>Resolved customer</CardTitle></CardHeader><CardContent>{result.customer || 'No resolved customer returned.'}</CardContent></Card>
      <h3>Found cases ({result.cases.length})</h3>
      {result.cases.map((item, i) => <Card className="cms-case" key={i} role="article" aria-label={`CMS case ${i + 1}`}><CardContent><dl>
        <dt>Case number</dt><dd>{item.cms_caseNum || 'Not supplied'}</dd>
        <dt>Case type</dt><dd>{item.caseType || 'Not supplied'}</dd>
        <dt>Case status</dt><dd>{item.case_status || 'Not supplied'}</dd>
        <dt>Message</dt><dd>{item.message || 'Not supplied'}</dd>
      </dl></CardContent></Card>)}
      {!result.cases.length && <p>No cases returned.</p>}
    </>}
  </section>
}
