const fs = require('fs')
const path = require('path')
const { spawn } = require('child_process')

const ffmpeg = 'F:\\ana\\envs\\xiaozhi-esp32-server\\Library\\bin\\ffmpeg.exe'
const frames = path.join(__dirname, 'video-frames')
const soundtrack = path.join(__dirname, 'video-music-original.wav')
const output = path.join(__dirname, 'zhixingdao-xiaohongshu-vertical-1080x1920.mp4')
const slideSeconds = 3.2
const fadeSeconds = 0.35
const seconds = 7 * slideSeconds - 6 * fadeSeconds

function makeSoundtrack() {
  const rate = 22050
  const count = Math.ceil(seconds * rate)
  const data = Buffer.alloc(44 + count * 2)
  data.write('RIFF', 0)
  data.writeUInt32LE(data.length - 8, 4)
  data.write('WAVEfmt ', 8)
  data.writeUInt32LE(16, 16)
  data.writeUInt16LE(1, 20)
  data.writeUInt16LE(1, 22)
  data.writeUInt32LE(rate, 24)
  data.writeUInt32LE(rate * 2, 28)
  data.writeUInt16LE(2, 32)
  data.writeUInt16LE(16, 34)
  data.write('data', 36)
  data.writeUInt32LE(count * 2, 40)
  const chords = [
    [130.81, 196, 261.63, 329.63],
    [110, 164.81, 220, 261.63],
    [87.31, 130.81, 174.61, 220],
    [98, 146.83, 196, 246.94],
  ]
  const melody = [392, 493.88, 523.25, 493.88, 440, 392, 329.63, 392, 349.23, 440, 523.25, 440, 392, 329.63, 293.66, 329.63]
  for (let i = 0; i < count; i++) {
    const t = i / rate
    const chord = chords[Math.floor(t / 4.8) % chords.length]
    let pad = 0
    for (const f of chord) pad += Math.sin(2 * Math.PI * f * t) + 0.18 * Math.sin(2 * Math.PI * f * 2 * t)
    pad *= 0.011
    const step = Math.floor(t / 0.4)
    const local = t - step * 0.4
    const f = melody[step % melody.length]
    const pluck = 0.09 * Math.exp(-local * 8) * (Math.sin(2 * Math.PI * f * local) + 0.22 * Math.sin(4 * Math.PI * f * local))
    const beat = t % 0.8
    const kick = 0.045 * Math.exp(-beat * 26) * Math.sin(2 * Math.PI * (70 - 32 * beat) * beat)
    const pulse = Math.sin(2 * Math.PI * 0.18 * t) * 0.005
    const fade = Math.min(1, t / 0.55, (seconds - t) / 0.9)
    const sample = Math.max(-1, Math.min(1, (pad + pluck + kick + pulse) * Math.max(0, fade)))
    data.writeInt16LE(Math.round(sample * 32767), 44 + 2 * i)
  }
  fs.writeFileSync(soundtrack, data)
}

function makeVideo() {
  const args = ['-y', '-hide_banner', '-loglevel', 'warning']
  for (let i = 0; i < 7; i++) args.push('-loop', '1', '-framerate', '24', '-t', String(slideSeconds), '-i', path.join(frames, `scene-${String(i).padStart(2, '0')}.png`))
  args.push('-i', soundtrack)
  const filters = []
  for (let i = 0; i < 7; i++) {
    filters.push(`[${i}:v]zoompan=z='min(1.028,1+on*0.00037)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=24,format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v${i}]`)
  }
  for (let i = 1; i < 7; i++) {
    const previous = i === 1 ? 'v0' : `x${i - 1}`
    filters.push(`[${previous}][v${i}]xfade=transition=fade:duration=${fadeSeconds}:offset=${(i * (slideSeconds - fadeSeconds)).toFixed(2)}[x${i}]`)
  }
  args.push('-filter_complex', filters.join(';'), '-map', '[x6]', '-map', '7:a', '-c:v', 'libopenh264', '-b:v', '5500k', '-maxrate', '6500k', '-bufsize', '11000k', '-pix_fmt', 'yuv420p', '-r', '24', '-af', 'volume=8dB', '-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-t', String(seconds), '-movflags', '+faststart', output)
  const child = spawn(ffmpeg, args, { stdio: 'inherit' })
  child.on('exit', code => { if (code !== 0) process.exit(code || 1); else console.log(output) })
}

makeSoundtrack()
makeVideo()
