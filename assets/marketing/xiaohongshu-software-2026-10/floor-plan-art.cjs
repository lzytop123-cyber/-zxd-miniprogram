const fs = require('fs')
const path = require('path')

// Coordinates follow the legacy 900 × 700 floor layout in
// miniprogram/utils/seat-layout.js and components/floor-plan-map/index.wxss.
const positions = {
  21:[92,108],22:[92,168],23:[92,227],24:[92,287],
  20:[258,108],19:[258,168],16:[337,108],17:[337,168],18:[337,227],
  15:[502,108],14:[502,168],9:[584,108],10:[584,168],11:[584,227],
  8:[811,108],7:[811,168],6:[811,227],5:[811,287],4:[811,346],3:[811,406],
  12:[584,408],13:[584,468],27:[92,431],26:[92,515],25:[92,599],28:[258,599],
  1:[734,542],2:[808,542],
}
const status = new Map([[8,'selected'],[3,'reserved'],[11,'occupied'],[19,'reserved']])
const seats = Object.entries(positions).map(([code,[x,y]]) => {
  const state = status.get(+code) || 'available'
  const horizontal = +code <= 2
  const palette = {
    available:['#D4EEDF','#2F8A5F','#2B6748'],
    selected:['#205A3D','#FFFFFF','#174731'],
    reserved:['#F4E5BB','#8B6524','#D0B275'],
    occupied:['#E3E9E3','#7E8F83','#BCC7BE'],
  }[state]
  const [fill,ink,edge] = palette
  const number = String(code).padStart(2,'0')
  return `<g transform="translate(${x} ${y})" aria-label="${number}号座位 ${state}">
    ${horizontal ? `<path d="M-31 -11v22 M31 -11v22" stroke="#9AACA0" stroke-width="4" stroke-linecap="round"/>` : `<path d="M-13 -25h26 M-13 25h26" stroke="#9AACA0" stroke-width="4" stroke-linecap="round"/>`}
    <rect x="-24" y="-17" width="48" height="34" rx="9" fill="${fill}" stroke="${edge}" stroke-width="${state==='selected'?3:1.5}"/>
    <text x="0" y="6" fill="${ink}" font-size="17" font-weight="800" text-anchor="middle">${number}</text>
    ${state==='selected' ? `<circle cx="27" cy="-18" r="6" fill="#65CA91" stroke="#FFFFFF" stroke-width="2"/>` : ''}
  </g>`
}).join('')

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="700" viewBox="0 0 900 700" role="img" aria-label="知行岛自习室座位平面示意图">
<defs>
  <pattern id="floor" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="#DCE9DF" stroke-width=".65"/></pattern>
  <pattern id="service" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M-2 12L12 -2 M4 18L18 4" stroke="#DCE4DD" stroke-width="2"/></pattern>
</defs>
<rect width="900" height="700" rx="18" fill="#F8FBF8"/>
<rect x="31" y="27" width="838" height="648" rx="12" fill="url(#floor)"/>
<!-- Rooms and service areas: based on the product's fixed floor layout -->
<path d="M48 44H295V324H48Z" fill="#EDF7EF"/>
<path d="M295 44H546V324H295Z" fill="#F1F8F1"/>
<path d="M546 44H852V507H546Z" fill="#E6F3E9"/>
<path d="M48 374H295V656H48Z" fill="#EBF6EE"/>
<path d="M295 374H546V587H295Z" fill="#F0F2EF" stroke="#BAC8BE" stroke-width="2"/>
<path d="M295 587H546V656H295Z" fill="url(#service)" stroke="#BAC8BE" stroke-width="2"/>
<path d="M421 587V656" stroke="#BAC8BE" stroke-width="2"/>
<path d="M48 324H546V374H48Z" fill="#FFFFFF"/>
<path d="M546 507H852V596H665V656H546Z" fill="#F8FBF8"/>
<!-- Architectural lines, with corridor openings -->
<path d="M48 44H852V596H665V656H48V44Z" fill="none" stroke="#4E6758" stroke-width="5" stroke-linejoin="round"/>
<path d="M295 44V324 M295 374V656 M546 44V324 M546 374V656" fill="none" stroke="#667F6D" stroke-width="3.5"/>
<path d="M48 324H221 M300 324H427 M507 324H546 M48 374H191 M270 374H368 M447 374H546" fill="none" stroke="#667F6D" stroke-width="3.5"/>
<path d="M556 656H665" stroke="#F8FBF8" stroke-width="9"/>
<path d="M596 656V615M625 656V615" stroke="#8AA497" stroke-width="2"/>
<path d="M596 615q29 0 29 41" fill="none" stroke="#AABDB0" stroke-width="1.5"/>
<!-- Windows -->
<path d="M134 44H215 M384 44H465 M661 44H742 M95 656H174" stroke="#A9D9C3" stroke-width="9"/>
<path d="M134 44H215 M384 44H465 M661 44H742 M95 656H174" stroke="#4E6758" stroke-width="2"/>
<text x="168" y="77" font-family="Microsoft YaHei,Arial" font-size="17" fill="#719581" font-weight="700" text-anchor="middle">沉浸区 A</text>
<text x="421" y="77" font-family="Microsoft YaHei,Arial" font-size="17" fill="#719581" font-weight="700" text-anchor="middle">沉浸区 B</text>
<text x="700" y="79" font-family="Microsoft YaHei,Arial" font-size="18" fill="#5F9274" font-weight="800" text-anchor="middle">标准区</text>
<text x="168" y="411" font-family="Microsoft YaHei,Arial" font-size="17" fill="#719581" font-weight="700" text-anchor="middle">沉浸区 C</text>
<text x="420" y="487" font-family="Microsoft YaHei,Arial" font-size="20" fill="#88998D" font-weight="700" text-anchor="middle">卫生间</text>
<text x="357" y="625" font-family="Microsoft YaHei,Arial" font-size="16" fill="#88998D" text-anchor="middle">茶水间</text>
<text x="483" y="625" font-family="Microsoft YaHei,Arial" font-size="16" fill="#88998D" text-anchor="middle">餐厅</text>
<text x="421" y="355" font-family="Microsoft YaHei,Arial" font-size="15" fill="#A1B4A5" letter-spacing="3" text-anchor="middle">通 道</text>
<text x="611" y="686" font-family="Microsoft YaHei,Arial" font-size="17" fill="#526F5D" font-weight="800" text-anchor="middle">入口 ↑</text>
${seats}
</svg>`

const out = path.join(__dirname, 'floor-plan-art.svg')
fs.writeFileSync(out, svg, 'utf8')
console.log(out)
