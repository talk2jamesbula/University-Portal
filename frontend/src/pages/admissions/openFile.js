import api from '../../api/client'

/** Open an authenticated file (PDF or image) in a new tab; a plain link can't carry the JWT. */
export default async function openFile(url) {
  // Open the tab first, while the click still allows opening windows.
  const tab = window.open('', '_blank')
  try {
    const { data } = await api.get(url, { responseType: 'blob' })
    const href = URL.createObjectURL(data)
    if (tab) tab.location = href
    else window.location.assign(href)
    setTimeout(() => URL.revokeObjectURL(href), 60_000)
  } catch (err) {
    tab?.close()
    throw err
  }
}
