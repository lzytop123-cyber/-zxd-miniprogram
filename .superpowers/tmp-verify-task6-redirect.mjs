/** Smoke: empty store permissions must not loop on /dashboard */
const PATH_MODULE = {
  '/dashboard': 'dashboard',
  '/seats': 'seats',
}

function canAccessPath(path, perms) {
  const mod = PATH_MODULE[path.split('?')[0]]
  if (!mod) return false
  return perms.includes(mod)
}

function canAccessRoute(path, perms) {
  const p = path.split('?')[0]
  if (p === '/dashboard') return true
  return canAccessPath(p, perms)
}

function firstAccessiblePath(perms, order) {
  for (const path of order) {
    if (canAccessPath(path, perms)) return path
  }
  return '/dashboard'
}

const order = ['/dashboard', '/receipts', '/seats']
const empty = []
if (!canAccessRoute('/dashboard', empty)) throw new Error('dashboard shell')
if (canAccessRoute('/receipts', empty)) throw new Error('receipts should deny')
if (firstAccessiblePath(empty, order) !== '/dashboard') throw new Error('fallback')
const seatsOnly = ['seats']
if (firstAccessiblePath(seatsOnly, order) !== '/seats') throw new Error('first permitted')
console.log('verify ok')
