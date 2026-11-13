// Coordinates from the original plan, using the same crop as the published markers.
const WIDTH = 779
const HEIGHT = 757
const x = (value) => (value - 125) / WIDTH * 100
const y = (value) => (value - 205) / HEIGHT * 100

const walls = [
  [157, 516, 179, 516], [157, 516, 157, 929], [157, 929, 220, 929],
  [340, 929, 465, 929], [575, 929, 701, 929], [811, 929, 873, 929],
  [873, 238, 873, 929], [809, 238, 873, 238], [571, 238, 703, 238],
  [350, 238, 452, 238], [267, 238, 308, 238], [267, 238, 267, 516],
  [247, 516, 389, 516], [389, 498, 389, 516], [388, 238, 388, 391],
  [267, 385, 330, 385], [157, 612, 327, 612], [386, 612, 402, 612],
  [402, 612, 402, 929], [635, 238, 635, 395], [635, 454, 635, 599],
  [635, 473, 873, 473], [635, 599, 681, 599], [740, 599, 873, 599],
  [635, 663, 635, 929],
]
const windows = [
  [308, 238, 350, 238], [452, 238, 571, 238], [703, 238, 809, 238],
  [220, 929, 340, 929], [465, 929, 575, 929], [701, 929, 811, 929],
]

const lines = [walls, windows].flatMap((segments, kind) =>
  segments.map(([left, top, right, bottom]) => ({
    kind: kind ? 'window' : 'wall',
    style: `left:${x(left)}%;top:${y(top)}%;width:${x(right) - x(left)}%;height:${y(bottom) - y(top)}%;`,
  }))
)

const labels = [
  ['大门 ↓', 214, 516],
  ['女厕', 330, 318],
  ['茶水间', 330, 451],
  ['男厕', 750, 537],
  ['阳光标准区', 520, 427, 'sun'],
  ['阳光标准区', 727, 319, 'sun'],
  ['阳光标准区', 321, 835, 'sun'],
  ['阳光标准区', 519, 835, 'sun'],
  ['挂帘沉浸区', 787, 390, 'curtain'],
  ['挂帘沉浸区', 241, 835, 'curtain'],
  ['挂帘沉浸区', 760, 835, 'curtain'],
].map(([text, left, top, zone]) => ({
  text,
  zone,
  style: `left:${x(left)}%;top:${y(top)}%;`,
}))

function isLigongdaFloor(imageUrl) {
  return /\/seat-maps\/ligongda-35\.png(?:[?#].*)?$/.test(imageUrl)
}

module.exports = { isLigongdaFloor, lines, labels }
