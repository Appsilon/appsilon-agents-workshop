import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Event = { id: number; subject_id: string; term: string; severity: string; onset_date: string; outcome: string; narrative: string | null };
type Response = { items: Event[]; total: number; page: number; page_size: number };
const API = "http://localhost:8000";

function App() {
  const [data, setData] = useState<Response>();
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/adverse-events?page=${page}`).then((response) => response.json()).then(setData).catch(() => setError("Could not load adverse events."));
  }, [page]);

  async function addNarrative(id: number) {
    setError("");
    const response = await fetch(`${API}/adverse-events/${id}/narrative`, { method: "POST" });
    if (!response.ok) setError((await response.json()).detail);
  }

  const lastPage = data ? Math.ceil(data.total / data.page_size) : 1;
  return <main><header><p>Clinical operations</p><h1>Adverse event narratives</h1></header>
    {error && <aside role="alert">{error}</aside>}
    <table><thead><tr><th>Subject</th><th>Term</th><th>Severity</th><th>Onset</th><th>Outcome</th><th>Narrative</th><th>Actions</th></tr></thead>
      <tbody>{data?.items.map((event) => <tr key={event.id}><td>{event.subject_id}</td><td>{event.term}</td><td><span className={`severity ${event.severity.toLowerCase()}`}>{event.severity}</span></td><td>{event.onset_date}</td><td>{event.outcome}</td><td>{event.narrative ?? "Not generated"}</td><td><button onClick={() => addNarrative(event.id)}>+ Add Narrative</button></td></tr>)}</tbody>
    </table>
    <footer><span>{data ? `${data.total} events` : "Loading..."}</span><div><button disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button><span> Page {page} of {lastPage} </span><button disabled={page === lastPage} onClick={() => setPage(page + 1)}>Next</button></div></footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<App />);