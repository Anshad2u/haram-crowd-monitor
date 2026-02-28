const SOURCE_URL = 'https://trasul.gph.gov.sa/haram-api/public/api/pry/TawafSaiStatus'

const STATUS_LABEL = {
  1: 'Light',
  2: 'Medium',
  3: 'Heavy',
  4: 'Not Available',
}

const STATUS_COLOR = {
  1: 'Green',
  2: 'Brown / Orange',
  3: 'Red',
  4: 'Dark Grey',
}

const LOCATION_MAP = {
  1: { areaType: 'tawaf', areaNameEn: 'Mataf Courtyard (Around Kaaba)', levelCode: 'G' },
  2: { areaType: 'tawaf', areaNameEn: 'Ground Floor Tawaf', levelCode: 'G' },
  3: { areaType: 'tawaf', areaNameEn: 'First Floor Tawaf', levelCode: '1' },
  5: { areaType: 'tawaf', areaNameEn: 'Roof Tawaf', levelCode: '2' },
  7: { areaType: 'sai', areaNameEn: "Ground Floor Sa'i", levelCode: 'G' },
  8: { areaType: 'sai', areaNameEn: "First Floor Sa'i", levelCode: '1' },
  10: { areaType: 'sai', areaNameEn: "Second Floor Sa'i", levelCode: '2' },
}

function normalizeGates(doorNo) {
  if (!doorNo) return null
  const nums = String(doorNo).match(/\d+/g)
  return nums ? nums.join(', ') : null
}

async function handler(req, res) {
  try {
    const upstream = await fetch(SOURCE_URL, {
      method: 'GET',
      headers: {
        'user-agent': 'haram-crowd-monitor/1.0',
        accept: 'application/json',
      },
    })

    if (!upstream.ok) {
      return res.status(502).json({ error: `Upstream returned ${upstream.status}` })
    }

    const rows = await upstream.json()
    const now = new Date().toISOString()

    const data = rows
      .map((row) => {
        const locationId = Number(row.id)
        const map = LOCATION_MAP[locationId]
        if (!map) return null

        const statusCode = Number(row.status ?? 4)
        const available = statusCode !== 4
        const timeExpect = available ? Number(row.time_expect ?? null) : null

        return {
          locationId,
          areaType: map.areaType,
          areaNameEn: map.areaNameEn,
          levelCode: map.levelCode,
          statusCode,
          statusLabel: STATUS_LABEL[statusCode] ?? 'Unknown',
          color: STATUS_COLOR[statusCode] ?? 'Unknown',
          estimatedMin: Number.isFinite(timeExpect) ? timeExpect - 5 : null,
          estimatedMax: Number.isFinite(timeExpect) ? timeExpect + 5 : null,
          gates: normalizeGates(row.door_no),
          sourceUpdatedAt: row.updated_at ?? null,
        }
      })
      .filter(Boolean)
      .sort((a, b) => a.locationId - b.locationId)

    res.setHeader('Cache-Control', 's-maxage=45, stale-while-revalidate=60')
    return res.status(200).json({
      fetchedAt: now,
      source: SOURCE_URL,
      count: data.length,
      data,
    })
  } catch (error) {
    return res.status(500).json({ error: error.message || 'Unknown server error' })
  }
}

module.exports = handler
