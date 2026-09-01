export default function HitRateTable({ data, loading }) {
  if (loading) return <div className="panel"><p className="muted">running 12 questions × each retriever…</p></div>
  if (!data) return null

  const names = Object.keys(data)
  const rows = data[names[0]].records

  return (
    <div className="panel">
      <h3>hit-rate@{data[names[0]].k} — same 12 questions, one variable changed</h3>

      <div className="scores">
        {names.map((n) => (
          <div key={n} className="scorecard">
            <div className="big">{data[n].hits}/{data[n].total}</div>
            <div className="muted">{n}</div>
            <div className="muted">p50 {data[n].p50_latency_ms} ms</div>
          </div>
        ))}
      </div>

      <table className="eval">
        <thead>
          <tr>
            <th>#</th>
            <th>Question</th>
            <th>exact token?</th>
            {names.map((n) => <th key={n}>{n}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.question}</td>
              <td className="muted">{r.exact_token ? 'yes' : 'no'}</td>
              {names.map((n) => {
                const rec = data[n].records[i]
                return (
                  <td key={n} className={rec.hit ? 'hit' : 'miss'}>
                    {rec.hit ? `✅ #${rec.hit_rank}` : '❌ miss'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>

      <h4>The price of the change</h4>
      <table className="eval">
        <thead>
          <tr>
            <th>Retriever</th>
            <th>hit-rate@{data[names[0]].k}</th>
            <th>p50</th>
            <th>p95</th>
            <th>index build (one-time)</th>
            <th>mean pairwise cosine in top-3</th>
          </tr>
        </thead>
        <tbody>
          {names.map((n) => (
            <tr key={n}>
              <td><code>{n}</code></td>
              <td>{data[n].hits}/{data[n].total}</td>
              <td>{data[n].p50_latency_ms} ms</td>
              <td>{data[n].p95_latency_ms} ms</td>
              <td>{data[n].index_build_ms != null ? `${data[n].index_build_ms} ms` : '—'}</td>
              <td>{data[n].mean_redundancy}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        chunker <code>{data[names[0]].strategy}</code> · embed model{' '}
        <code>{data[names[0]].embed_model}</code> · {data[names[0]].repeats_per_question} latency
        samples per question
      </p>
    </div>
  )
}
