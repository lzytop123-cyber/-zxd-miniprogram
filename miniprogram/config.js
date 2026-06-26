// 环境切换：USE_PROD=true 连服务器，false 连本机
const USE_PROD = true

const PROD_API_BASE = 'https://api.islandspace.xyz/api'

// 本机联调
// - 开发者工具模拟器：127.0.0.1
// - 真机调试/预览：改成你电脑的局域网 IP（cmd 里 ipconfig 查看 IPv4）
const DEV_API_HOST = '192.168.0.104'
const DEV_API_BASE = `http://${DEV_API_HOST}:8000/api`

const API_BASE = USE_PROD ? PROD_API_BASE : DEV_API_BASE

module.exports = {
  USE_PROD,
  API_BASE,
  DEV_API_HOST,
}
