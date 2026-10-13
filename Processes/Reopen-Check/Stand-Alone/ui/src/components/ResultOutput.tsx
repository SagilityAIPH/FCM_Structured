function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function isTable(value: unknown): value is { title: string; rows: string[][] } {
  return isRecord(value) && typeof value.title === "string" && Array.isArray(value.rows) &&
    value.rows.every((row: unknown) => Array.isArray(row) && row.every((cell: unknown) => typeof cell === "string"))
}

export function ResultOutput({ value }: { value: unknown }) {
  const envelope = isRecord(value) ? value : {}
  const result = isRecord(envelope.result) ? envelope.result : {}
  const tables = Array.isArray(envelope.extracted_tables) ? envelope.extracted_tables.filter(isTable) : []
  const summary = [
    ["Status", result.status],
    ["Customer", result.customer],
    ["Reason", result.reason],
    ["Error", envelope.error],
    ["Last stage", envelope.stage],
  ].filter(([, item]) => typeof item === "string" && item.length > 0)

  return (
    <div className="space-y-3 p-4 text-xs">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        {summary.map(([label, item]) => (
          <div key={String(label)} className="contents">
            <dt className="font-semibold">{String(label)}</dt>
            <dd className="whitespace-pre-wrap break-words">{String(item)}</dd>
          </div>
        ))}
      </dl>
      {tables.length === 0 && <p>No customer-search table was captured for this run.</p>}
      {tables.map((table, index) => (
        <section key={index} className="space-y-2">
          <h4 className="font-semibold">{table.title}{tables.length > 1 ? ` (${index + 1})` : ""}</h4>
          {table.rows.length === 0 ? <p>No results found.</p> : (
            <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={table.title}>
              <table className="w-full border-collapse text-left">
                <caption className="sr-only">{table.title}</caption>
                <tbody>
                  {table.rows.map((row, rowIndex) => (
                    <tr key={rowIndex} className="even:bg-(--color-surface-muted)">
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className="whitespace-pre-wrap border border-(--color-border) px-2 py-1 align-top">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
      <details>
        <summary className="cursor-pointer font-semibold">Full result JSON (copied and saved)</summary>
        <pre className="mt-2 whitespace-pre-wrap break-words font-(family-name:--font-mono)">{JSON.stringify(value, null, 2)}</pre>
      </details>
    </div>
  )
}
