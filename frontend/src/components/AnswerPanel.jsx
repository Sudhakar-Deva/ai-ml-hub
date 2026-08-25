export default function AnswerPanel({ result, loading }) {
  if (loading) return <div className="panel"><p className="muted">generating…</p></div>
  if (!result) return null

  const bad = result.unresolvable_citations?.length > 0

  return (
    <div className={`panel ${result.refused ? 'refused' : ''}`}>
      <h3>
        {result.refused ? 'Refused (no source in corpus)' : 'Answer'}
        {bad && <span className="badge err">unresolvable citation</span>}
      </h3>
      <pre className="answer">{result.answer}</pre>

      {result.citations?.length > 0 && (
        <>
          <h4>Citations</h4>
          <ul className="citations">
            {result.citations.map((c) => (
              <li key={c.chunk_id} className={c.resolves ? '' : 'err'}>
                <code>{c.chunk_id}</code> — {c.form_number} · {c.clause}{' '}
                {c.resolves ? '✅ resolves' : '❌ does not resolve'}
                {c.chunk_text && <details><summary>chunk text</summary><pre>{c.chunk_text}</pre></details>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
