export default function EvalTable({ data, loading }) {
  if (loading) return <div className="panel"><p className="muted">running all 8 questions against both strategies…</p></div>
  if (!data) return null

  const strategies = Object.keys(data)
  const rows = data[strategies[0]].records

  return (
    <div className="panel">
      <h3>hit-in-top-5 — same 8 questions, both chunkers</h3>
      <div className="scores">
        {strategies.map((s) => (
          <div key={s} className="scorecard">
            <div className="big">{data[s].hits}/{data[s].total}</div>
            <div className="muted">{s}</div>
          </div>
        ))}
      </div>

      <table className="eval">
        <thead>
          <tr>
            <th>#</th>
            <th>Question</th>
            <th>Expected</th>
            {strategies.map((s) => <th key={s}>{s}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.question}</td>
              <td><code>{r.expected.form_number}</code> · {r.expected.clause_contains}</td>
              {strategies.map((s) => {
                const rec = data[s].records[i]
                return (
                  <td key={s} className={rec.hit ? 'hit' : 'miss'}>
                    {rec.hit ? `✅ #${rec.hit_rank}` : '❌ miss'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">embed model: <code>{data[strategies[0]].embed_model}</code> · k={data[strategies[0]].k}</p>
    </div>
  )
}
