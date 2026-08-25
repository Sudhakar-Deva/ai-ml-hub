export default function ResultList({ title, results, loading }) {
  return (
    <div className="panel">
      <h3>{title}</h3>
      {loading && <p className="muted">searching…</p>}
      {!loading && results?.length === 0 && <p className="muted">no results</p>}
      <ol className="results">
        {results?.map((r) => (
          <li key={r.chunk_id}>
            <div className="row">
              <span className="score">{r.score.toFixed(4)}</span>
              <span className="badge">{r.form_number}</span>
              <span className="badge dim">ed. {r.edition_date}</span>
              <span className="badge line">{r.policy_line}</span>
            </div>
            <div className="clause">{r.clause}</div>
            <code className="chunkid">{r.chunk_id}</code>
            <p className="snippet">{r.text.slice(0, 320)}…</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
