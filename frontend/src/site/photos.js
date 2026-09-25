/**
 * Student photos used on the website, with the attribution their Creative Commons licences require.
 * These are stock images from Wikimedia Commons; replace them with the university's own campus photos
 * (and update CREDITS) when available.
 */
import campusLife from '../assets/students/campus-life.jpg'
import culture from '../assets/students/culture.jpg'
import digitalLearning from '../assets/students/digital-learning.jpg'
import lecture from '../assets/students/lecture.jpg'

export const PHOTOS = {
  campusLife: { src: campusLife, alt: 'A group of smiling students chatting outside a campus building' },
  lecture: { src: lecture, alt: 'Students listening attentively in a lecture hall' },
  digitalLearning: { src: digitalLearning, alt: 'A student working on a laptop with a tutor beside him' },
  culture: { src: culture, alt: 'Two students in colourful costumes at a campus cultural festival' },
}

const LICENSES = {
  'CC BY 4.0': 'https://creativecommons.org/licenses/by/4.0/',
  'CC BY-SA 4.0': 'https://creativecommons.org/licenses/by-sa/4.0/',
}

export const CREDITS = [
  ['campusLife', 'Students of the University of Ilorin', 'Haylad', 'CC BY-SA 4.0',
    'https://commons.wikimedia.org/wiki/File:Students_of_the_University_OF_Ilorin._26.jpg'],
  ['lecture', 'Students at Lecture Hall', 'Zahraswaty', 'CC BY 4.0',
    'https://commons.wikimedia.org/wiki/File:Students_at_Lecture_Hall.jpg'],
  ['digitalLearning', 'Tutorcbt 001', 'IBORO', 'CC BY-SA 4.0',
    'https://commons.wikimedia.org/wiki/File:Tutorcbt_001.jpg'],
  ['culture', 'University of Lagos students festival 15', 'Agbebiyi Adekunle Tadek', 'CC BY-SA 4.0',
    'https://commons.wikimedia.org/wiki/File:University_of_Lagos_students_festival_15.jpg'],
].map(([key, title, author, license, source]) => ({
  key, title, author, license, source, licenseUrl: LICENSES[license], image: PHOTOS[key],
}))
