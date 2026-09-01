const LABEL_HINT = {
  R: 'retrieval fetched bad context — the gold chunk never reached the model',
  G: 'model misused good context — the gold chunk WAS in the top-3',
  'Not-In-Corpus': 'nothing indexed answers this question',
  pass: 'gold chunk retrieved',
}

function Tally({ tally, total }) {
  return (
    <div className="scores">
      {['R', 'G', 'Not-In-Corpus', 'pass'].map((label) => (
        <div key={label} className={`scorecard label-${label === 'Not-In-Corpus' ? 'nic' : label}`}>
          <div className="big">{tally[label]}</div>
          <div className="muted">{label}</div>
        </div>
      ))}
      <div className="scorecard">
        <div className="big">{total}</div>
        <div className="muted">questions</div>
      </div>
    </div>
  )
}

export default function InspectionView({ report, loading }) {
  if (loading) return <div className="panel"><p className="muted">running the golden set through retrieval…</p></div>
  if (!report) return null

  return (
    <>
      <div className="panel">
        <h3>
          Failure tally — <code>{report.retriever}</code> · top-{report.k}
          {!report.answers_generated && (
            <span className="badge">retrieval evidence only — no answer pass</span>
          )}
        </h3>
        <Tally tally={report.tally} total={report.rows.length} />
        <p className="muted">
          A label is decided by where the gold chunk actually landed, not by how the answer read.
          G is only reachable with the answer pass on: gold in the top-3 and the answer still wrong.
        </p>
      </div>

      {report.rows.map((row) => (
        <div key={row.id} className={`panel inspect ${row.label === 'pass' ? '' : 'failed'}`}>
          <h3>
            {row.id}
            <span className={`badge label label-${row.label === 'Not-In-Corpus' ? 'nic' : row.label}`}>
              {row.label}
            </span>
            {row.exact_token && <span className="badge">exact token</span>}
            <span className="muted">{LABEL_HINT[row.label]}</span>
          </h3>

          <p className="question">{row.question}</p>

          <div className="split">
            <div>
              <h4>Retrieved top-{report.k}</h4>
              <ol className="results">
                {row.top_k.map((h) => (
                  <li key={h.chunk_id} className={h.is_gold ? 'gold' : ''}>
                    <div className="row">
                      <span className="score">{Number(h.score).toFixed(4)}</span>
                      <span className="badge dim">{h.score_kind}</span>
                      {h.dense_rank != null && <span className="badge">dense #{h.dense_rank}</span>}
                      {h.bm25_rank != null && <span className="badge">bm25 #{h.bm25_rank}</span>}
                      <span className="badge line">{h.form_number} ed. {h.edition_date}</span>
                      {h.is_gold && <span className="badge hit-badge">gold chunk</span>}
                    </div>
                    <div className="clause">{h.clause}</div>
                    <code className="chunkid">{h.chunk_id}</code>
                    <p className="snippet">{h.snippet}…</p>
                  </li>
                ))}
              </ol>
            </div>

            <div>
              <h4>Known-correct chunk</h4>
              <code className="chunkid">{row.gold_chunk_id}</code>
              <p className="clause">{row.gold_clause}</p>
              <p className="muted">
                {row.gold_rank ? `retrieved at rank #${row.gold_rank}` : 'not in the top-3'}
              </p>

              <h4>Evidence</h4>
              <p className="snippet">{row.evidence}</p>

              {row.generation && (
                <>
                  <h4>Answer</h4>
                  {row.generation.error ? (
                    <p className="err">{row.generation.error}</p>
                  ) : (
                    <>
                      <pre className="answer">{row.generation.answer}</pre>
                      <p className="muted">
                        refused={String(row.generation.refused)} · passes known-answer check=
                        {String(row.generation.correct)}
                      </p>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </>
  )
}
