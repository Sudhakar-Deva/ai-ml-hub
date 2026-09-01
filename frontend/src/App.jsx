import { useState } from 'react'
import { ask, evaluate, hitrate, inspect, search } from './api/client.js'
import ResultList from './components/ResultList.jsx'
import AnswerPanel from './components/AnswerPanel.jsx'
import EvalTable from './components/EvalTable.jsx'
import InspectionView from './components/InspectionView.jsx'
import HitRateTable from './components/HitRateTable.jsx'

const STRATEGIES = ['current', 'structure_aware']
const RETRIEVERS = ['dense', 'hybrid']
const TABS = ['Search', 'Ask', 'Inspect', 'hit-rate@3', 'Bench (wk3)']

export default function App() {
  const [tab, setTab] = useState('Inspect')
  const [query, setQuery] = useState('')
  const [strategy, setStrategy] = useState('structure_aware')
  const [retriever, setRetriever] = useState('dense')
  const [policyLine, setPolicyLine] = useState('')
  const [withAnswers, setWithAnswers] = useState(false)
  const [unfiltered, setUnfiltered] = useState(null)
  const [filtered, setFiltered] = useState(null)
  const [answer, setAnswer] = useState(null)
  const [evalData, setEvalData] = useState(null)
  const [report, setReport] = useState(null)
  const [rates, setRates] = useState(null)
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
        search({ query, strategy, retriever }),
        policyLine
          ? search({ query, strategy, retriever, policy_line: policyLine })
          : Promise.resolve(null),
      ])
      setUnfiltered(u.results)
      setFiltered(f?.results ?? null)
    })

  const doAsk = () =>
    run(async () => setAnswer(await ask({ question: query, strategy, retriever })))
  const doEval = () => run(async () => setEvalData(await evaluate()))
  const doInspect = () =>
    run(async () => setReport(await inspect({ retriever, strategy, k: 3, answers: withAnswers })))
  const doRates = () => run(async () => setRates(await hitrate('dense,hybrid')))

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

      {(tab === 'Search' || tab === 'Ask') && (
        <div className="controls">
          <input
            value={query}
            placeholder="e.g. does E-17 apply under HO-0304 ed. 03-24?"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (tab === 'Search' ? doSearch() : doAsk())}
          />
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={retriever} onChange={(e) => setRetriever(e.target.value)}>
            {RETRIEVERS.map((r) => <option key={r} value={r}>{r}</option>)}
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
          <ResultList title={`Unfiltered · ${retriever}`} results={unfiltered} loading={busy} />
          {policyLine && (
            <ResultList
              title={`Filtered · policy_line=${policyLine}`}
              results={filtered}
              loading={busy}
            />
          )}
        </div>
      )}

      {tab === 'Ask' && <AnswerPanel result={answer} loading={busy} />}

      {tab === 'Inspect' && (
        <>
          <div className="controls">
            <select value={retriever} onChange={(e) => setRetriever(e.target.value)}>
              {RETRIEVERS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <label className="check">
              <input
                type="checkbox"
                checked={withAnswers}
                onChange={(e) => setWithAnswers(e.target.checked)}
              />
              run the answer pass (needed to tell R from G — costs one LLM call per question)
            </label>
            <button onClick={doInspect} disabled={busy}>Inspect all 12</button>
          </div>
          <InspectionView report={report} loading={busy} />
        </>
      )}

      {tab === 'hit-rate@3' && (
        <>
          <div className="controls">
            <button onClick={doRates} disabled={busy}>Measure dense vs hybrid</button>
          </div>
          <HitRateTable data={rates} loading={busy} />
        </>
      )}

      {tab === 'Bench (wk3)' && (
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
