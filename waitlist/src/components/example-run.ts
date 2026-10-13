/** One example run of GTMX, step by step, for a made-up Nairobi startup. The
 * accounts are described, not named: this is an illustration, not a client. */

export type StepKind = 'read' | 'market' | 'kept' | 'dropped' | 'account' | 'draft'

export interface RunStep {
  kind: StepKind
  label: string
  finding: string
}

export const EXAMPLE_COMPANY = 'Tumalogix, route planning for delivery fleets, Nairobi'

export const EXAMPLE_STEPS: RunStep[] = [
  { kind: 'read', label: 'Reading tumalogix.co.ke', finding: 'Route planning for last-mile fleets, priced per vehicle' },
  { kind: 'market', label: 'Sizing demand in Kenya, Nigeria, South Africa', finding: 'Best fit: distributors running 10–200 vehicles' },
  { kind: 'kept', label: 'Checking rivals', finding: '3 route-optimisation tools selling into Lagos and Joburg' },
  { kind: 'dropped', label: 'Checking rivals', finding: 'Dropped a freelance marketplace: not a rival' },
  { kind: 'account', label: 'Finding who has a reason to buy now', finding: 'A Lagos FMCG distributor opened a second depot last week' },
  { kind: 'account', label: 'Finding who to contact', finding: 'Head of Logistics, named on their own site' },
  { kind: 'draft', label: 'Draft ready for your review', finding: 'Nothing is sent until you click send' },
]

export const EXAMPLE_DRAFT = {
  subject: 'Your new Ikeja depot',
  body:
    'Hi Funmi, congratulations on the second depot. Splitting one fleet across two depots is usually where routes ' +
    'start costing more than they should. Tumalogix plans both depots’ routes together each morning, on the phones ' +
    'your drivers already carry. Worth 20 minutes next week to see it on your own routes?',
}
