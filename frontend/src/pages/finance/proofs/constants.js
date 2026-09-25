export const MAX_PROOF_SIZE = 5 * 1024 * 1024
export const ACCEPTED_FILES = '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png'

export const PAYMENT_METHODS = [
  ['bank_deposit', 'Bank deposit (teller)'],
  ['bank_transfer', 'Bank transfer'],
  ['pos', 'POS'],
  ['cash', 'Cash at the Bursary'],
]
/** Methods where the student must say which bank was used. */
export const NEEDS_BANK = ['bank_deposit', 'bank_transfer']

export const PROOF_STATUS = {
  pending: { label: 'Awaiting review', tone: 'amber' },
  approved: { label: 'Approved', tone: 'green' },
  rejected: { label: 'Rejected', tone: 'red' },
}
