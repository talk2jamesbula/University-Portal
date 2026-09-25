export const LEVELS = [100, 200, 300, 400, 500, 600]
export const SEMESTER_NUMBERS = [[1, 'First Semester'], [2, 'Second Semester']]
export const WEEKDAYS = [['MON', 'Mon'], ['TUE', 'Tue'], ['WED', 'Wed'], ['THU', 'Thu'], ['FRI', 'Fri']]

export const EMPTY_OFFERING = {
  semester: '', lecturer: '', capacity: 120, days: '', start_time: '', end_time: '', venue: '',
}

/** Offering form state -> API payload (blank optional fields become null). */
export function offeringPayload(form) {
  return {
    ...form,
    lecturer: form.lecturer || null,
    start_time: form.start_time || null,
    end_time: form.end_time || null,
    capacity: Number(form.capacity) || 0,
  }
}
