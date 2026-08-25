import { useState } from 'react'
import { ask, evaluate, search } from './api/client.js'
import ResultList from './components/ResultList.jsx'
import AnswerPanel from './components/AnswerPanel.jsx'
import EvalTable from './components/EvalTable.jsx'

const STRATEGIES = ['current', 'structure_aware']
const TABS = ['Search', 'Ask', 'Bench']

export default function App() {
  const [tab, setTab] = useState('Search')
  const [query, setQuery] = useState('')
  const [strategy, setStrategy] = useState('structure_aware')
  const [policyLine, setPolicyLine] = useState('')
  const [unfiltered, setUnfiltered] = useState(null)
  const [filtered, setFiltered] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [evalData, setEvalData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const run = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(String(e.message ?? e))
    } finally {
      setBusy(false)
    }
  }

  // Fires both calls so the unfiltered vs filtered lists sit side by side —
  // that comparison is the metadata-filter deliverable.
  const doSearch = () =>
    run(async () => {
      const [u, f] = await Promise.all([
        search({ query, strategy }),
        policyLine ? search({ query, strategy, policy_line: policyLine }) : Promise.resolve(null),
      ])
      setUnfiltered(u.results)
      setFiltered(f?.results ?? null)
    })

  const doAsk = () => run(async () => setAnswer(await ask({ question: query, strategy })))
  const doEval = () => run(async () => setEvalData(await evaluate()))

  return (
    <div className="app">
      <header>
        <h1>Claims Assistant — Retrieval Bench</h1>
        <nav>
          {TABS.map((t) => (
            <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </nav>
      </header>

      {error && <div className="panel err">{error}</div>}

      {tab !== 'Bench' && (
        <div className="controls">
          <input
            value={query}
            placeholder="e.g. does E-17 apply to water damage from a burst supply line?"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (tab === 'Search' ? doSearch() : doAsk())}
          />
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {tab === 'Search' && (
            <input
              className="narrow"
              value={policyLine}
              placeholder="policy_line filter"
              onChange={(e) => setPolicyLine(e.target.value)}
            />
          )}
          <button onClick={tab === 'Search' ? doSearch : doAsk} disabled={busy || !query}>
            {tab === 'Search' ? 'Search' : 'Ask'}
          </button>
        </div>
      )}

      {tab === 'Search' && (
        <div className="split">
          <ResultList title="Unfiltered" results={unfiltered} loading={busy} />
          {policyLine && (
            <ResultList title={`Filtered · policy_line=${policyLine}`} results={filtered} loading={busy} />
          )}
        </div>
      )}

      {tab === 'Ask' && <AnswerPanel result={answer} loading={busy} />}

      {tab === 'Bench' && (
        <>
          <div className="controls">
            <button onClick={doEval} disabled={busy}>Run all 8 questions × 2 chunkers</button>
          </div>
          <EvalTable data={evalData} loading={busy} />
        </>
      )}
    </div>
  )
}
