/**
 * Written content for the public website, kept in one place so it's easy to edit.
 * Live data (faculties, programmes, news, events, statistics) comes from the API instead.
 *
 * REPLACE the contact details and address below with the university's real ones. Leadership on the
 * About page comes from role appointments in the portal; photos from each person's portal profile.
 */
import { UNIVERSITY_NAME } from '../utils/format'

export const SITE = {
  name: UNIVERSITY_NAME,
  motto: 'Knowledge, Character and Service',
  founded: 2012,
  address: ['Km 12, University Road', 'Abuja, FCT, Nigeria'],
  phone: '+234 800 000 0000',
  email: 'info@bulacode.edu.ng',
  admissionsEmail: 'admissions@bulacode.edu.ng',
  hours: 'Monday – Friday, 8:00 a.m. – 4:00 p.m.',
  // The contact page's Google map. REPLACE with the campus location: an address or place name Google Maps finds,
  // or exact coordinates such as '9.0579,7.4951' (right-click the campus in Google Maps to copy them).
  mapLocation: 'Abuja, Federal Capital Territory, Nigeria',
  mapZoom: 13,
}

export const ABOUT = {
  intro: `${UNIVERSITY_NAME} is a Nigerian university committed to excellent teaching, research that answers
    real problems, and graduates who serve their communities with competence and integrity.`,
  mission: 'To provide accessible, high-quality education and research that develops ethical leaders, drives innovation and contributes to national development.',
  vision: 'To be a leading African university recognised for academic excellence, impactful research and graduates of character.',
  history: [
    `Established in ${SITE.founded} and accredited by the National Universities Commission (NUC), the University began with
      two faculties and a few hundred students.`,
    'It has since grown to four faculties, modern laboratories, an ICT and e-learning centre, and a library with extensive digital resources.',
    'Our students are taught by dedicated academics and supported through every stage of their studies — from admission to convocation.',
  ],
  values: [
    ['Excellence', 'High standards in teaching, learning and research.'],
    ['Integrity', 'Honesty and accountability in everything we do.'],
    ['Innovation', 'Creative solutions to local and global challenges.'],
    ['Service', 'Knowledge put to work for our communities.'],
  ],
}

export const ADMISSIONS = {
  intro: 'We admit candidates into our undergraduate programmes through the Unified Tertiary Matriculation Examination (UTME), Direct Entry and inter-university transfer.',
  routes: [
    {
      title: 'UTME (100 Level)',
      points: [
        'Five credit passes in WAEC, NECO or NABTEB (at most two sittings), including English Language and Mathematics.',
        'Choose the University in the JAMB UTME and meet the cut-off mark for your programme.',
        'Take the University’s post-UTME screening.',
      ],
    },
    {
      title: 'Direct Entry (200 Level)',
      points: [
        'A-Level, IJMB, JUPEB, OND (upper credit) or NCE (merit) in relevant subjects.',
        'The O-Level requirements above.',
        'Register for Direct Entry with JAMB, choosing the University.',
      ],
    },
    {
      title: 'Inter-university transfer',
      points: [
        'At least one completed session at an NUC-accredited university.',
        'A minimum CGPA of 2.40 on a five-point scale.',
        'A letter of good conduct and your academic transcript.',
      ],
    },
  ],
  steps: [
    ['Create an account', 'Register on the admission portal with your JAMB registration number.'],
    ['Complete your application', 'Personal details, O-Level results and programme choice.'],
    ['Upload documents', 'Passport photograph, O-Level results and birth certificate.'],
    ['Pay the application fee', 'Online by card, bank transfer or USSD.'],
    ['Screening', 'Attend screening and track your status online.'],
    ['Admission decision', 'Download your admission letter and pay the acceptance fee.'],
  ],
}

export const RESEARCH = {
  intro: 'Research at the University tackles questions that matter to Nigeria and beyond — in health, technology, sustainable development and the humanities.',
  centres: [
    ['Centre for Applied Computing', 'Data science, artificial intelligence and software for public services.', 'Computer Science'],
    ['Antimicrobial Resistance Research Group', 'Surveillance and prevention of drug-resistant infections.', 'Microbiology'],
    ['Renewable Energy Laboratory', 'Off-grid solar systems and power electronics for rural communities.', 'Electrical & Electronic Engineering'],
    ['Centre for Entrepreneurship', 'Small-business growth, financial inclusion and innovation.', 'Business Administration'],
    ['African Literatures Forum', 'Contemporary African writing, orality and translation.', 'English & Literary Studies'],
  ],
  support: [
    'Seed grants for early-career researchers',
    'Research ethics committee review',
    'Access to shared laboratories and high-performance computing',
    'Support for publishing and conference travel',
  ],
}

export const LIBRARY = {
  intro: 'The University Library supports teaching, learning and research with print collections, digital resources, study spaces and expert help.',
  hours: [
    ['Monday – Friday', '8:00 a.m. – 10:00 p.m.'],
    ['Saturday', '9:00 a.m. – 5:00 p.m.'],
    ['Sunday', '2:00 p.m. – 8:00 p.m.'],
    ['Examination periods', 'Open 24 hours'],
  ],
  services: [
    ['Borrowing', 'Students may borrow up to 5 books for 14 days, renewable online through the student portal.'],
    ['E-resources', 'Access to online journals, e-books and databases on and off campus.'],
    ['Study spaces', 'Quiet reading rooms, group discussion rooms and a 24-hour exam reading room.'],
    ['Research support', 'Help with literature searches, referencing and research data.'],
  ],
}
