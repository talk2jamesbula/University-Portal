/** Shared admissions labels and options. */

export const STATUS_TONE = {
  draft: 'neutral',
  submitted: 'blue',
  under_review: 'blue',
  screening: 'purple',
  approved: 'green',
  waitlisted: 'amber',
  rejected: 'red',
  admitted: 'green',
  accepted: 'green',
}

export const STATUS_LABEL = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under review',
  screening: 'Screening',
  approved: 'Approved',
  waitlisted: 'Waitlisted',
  rejected: 'Rejected',
  admitted: 'Admitted',
  accepted: 'Accepted',
}

/** The happy path, for the applicant's progress tracker. */
export const JOURNEY = ['draft', 'submitted', 'under_review', 'screening', 'approved', 'admitted', 'accepted']

export const DOCUMENT_STATUS_TONE = { pending: 'amber', verified: 'green', rejected: 'red' }

export const DOCUMENT_KINDS = [
  ['passport', 'Passport photograph', 'A recent colour photo with a plain background (JPG or PNG).'],
  ['olevel', 'O-Level result', 'WAEC, NECO or NABTEB result or certificate. Upload both if you used two sittings (as one PDF).'],
  ['jamb_result', 'JAMB UTME result slip', 'The result slip printed from the JAMB portal.'],
  ['birth_certificate', 'Birth certificate', 'Birth certificate or sworn declaration of age.'],
  ['lga_certificate', 'Certificate of state of origin', 'From your local government area (optional).'],
  ['other', 'Other supporting document', 'e.g. A-Level or OND result for Direct Entry, or a transcript for transfer (optional).'],
]

export const ENTRY_MODES = [
  ['utme', 'UTME (100 Level)'],
  ['direct_entry', 'Direct Entry (200 Level)'],
  ['transfer', 'Inter-university transfer'],
]

export const EXAMS = ['WAEC', 'NECO', 'NABTEB', 'GCE']
export const GRADES = ['A1', 'B2', 'B3', 'C4', 'C5', 'C6', 'D7', 'E8', 'F9']
export const SUBJECTS = [
  'English Language', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'Agricultural Science', 'Further Mathematics',
  'Economics', 'Geography', 'Government', 'Literature in English', 'Christian Religious Studies', 'Islamic Studies',
  'Civic Education', 'Commerce', 'Financial Accounting', 'Technical Drawing', 'Computer Studies', 'Data Processing',
  'Yoruba', 'Igbo', 'Hausa', 'French', 'History',
]

export const STATES = [
  'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 'Borno', 'Cross River', 'Delta', 'Ebonyi',
  'Edo', 'Ekiti', 'Enugu', 'FCT', 'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Kogi', 'Kwara',
  'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamfara',
]

export const formatSize = (bytes) => (bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`)
