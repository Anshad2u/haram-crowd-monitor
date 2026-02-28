const liveHandler = require('./live.js')

function pickBestNow(rows, areaType) {
  const filtered = rows.filter((r) => r.areaType === areaType)
  if (filtered.length === 0) return null
  return filtered.sort((a, b) => {
    if (a.statusCode !== b.statusCode) return a.statusCode - b.statusCode
    const aMid = a.estimatedMin != null && a.estimatedMax != null ? (a.estimatedMin + a.estimatedMax) / 2 : 9999
    const bMid = b.estimatedMin != null && b.estimatedMax != null ? (b.estimatedMin + b.estimatedMax) / 2 : 9999
    return aMid - bMid
  })[0]
}

async function handler(req, res) {
  const fakeRes = {
    statusCode: 200,
    body: null,
    headers: {},
    status(code) {
      this.statusCode = code
      return this
    },
    setHeader(key, value) {
      this.headers[key] = value
    },
    json(payload) {
      this.body = payload
      return this
    },
  }

  await liveHandler(req, fakeRes)
  if (fakeRes.statusCode !== 200 || !fakeRes.body?.data) {
    return res.status(500).json({ error: 'Unable to get live data for analysis' })
  }

  const rows = fakeRes.body.data
  const ranked = [...rows].sort((a, b) => {
    if (a.statusCode !== b.statusCode) return a.statusCode - b.statusCode
    const aMid = a.estimatedMin != null && a.estimatedMax != null ? (a.estimatedMin + a.estimatedMax) / 2 : 9999
    const bMid = b.estimatedMin != null && b.estimatedMax != null ? (b.estimatedMin + b.estimatedMax) / 2 : 9999
    return aMid - bMid
  })

  return res.status(200).json({
    fetchedAt: fakeRes.body.fetchedAt,
    bestNow: {
      tawaf: pickBestNow(rows, 'tawaf'),
      sai: pickBestNow(rows, 'sai'),
    },
    rankingNow: ranked,
    note: 'This Vercel dashboard provides live status analysis. Historical week/month/year analysis remains in the local hourly database collector.',
  })
}

module.exports = handler
