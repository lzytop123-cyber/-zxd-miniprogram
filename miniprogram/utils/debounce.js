function debounce(fn, wait = 400) {
  let timer = null
  return function debounced(...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn.apply(this, args)
    }, wait)
  }
}

module.exports = { debounce }
