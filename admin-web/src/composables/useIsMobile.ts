import { readonly, ref } from 'vue'

const MOBILE_QUERY = '(max-width: 768px)'

const isMobileRef = ref(
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(MOBILE_QUERY).matches
    : false,
)

let initialized = false

function ensureListener() {
  if (initialized || typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return
  }
  initialized = true
  const mql = window.matchMedia(MOBILE_QUERY)
  isMobileRef.value = mql.matches
  const onChange = (e: MediaQueryListEvent) => {
    isMobileRef.value = e.matches
  }
  if (typeof mql.addEventListener === 'function') {
    mql.addEventListener('change', onChange)
  } else if (typeof (mql as any).addListener === 'function') {
    ;(mql as any).addListener(onChange)
  }
}

export function useIsMobile() {
  ensureListener()
  return readonly(isMobileRef)
}
