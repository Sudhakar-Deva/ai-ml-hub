const json = async (res) => {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export const search = (body) =>
  fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json)

export const ask = (body) =>
  fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json)

export const getChunk = (strategy, chunkId) =>
  fetch(`/api/chunk/${strategy}/${encodeURIComponent(chunkId)}`).then(json)

export const evaluate = () => fetch('/api/evaluate').then(json)

export const goldenSet = () => fetch('/api/golden-set').then(json)

// The inspection view. `answers: true` costs one LLM call per question and is
// what makes a G label decidable instead of assumed.
export const inspect = (body) =>
  fetch('/api/inspect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json)

export const hitrate = (retrievers = 'dense,hybrid') =>
  fetch(`/api/hitrate?retrievers=${encodeURIComponent(retrievers)}`).then(json)

export const health = () => fetch('/api/health').then(json)
