import { useEffect, useState } from 'react'

/** The value, updated only after it has stopped changing for `delay` ms (for search boxes). */
export default function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}
