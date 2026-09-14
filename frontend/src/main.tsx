import { Fragment, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as HoverCard from "@radix-ui/react-hover-card";
import * as Toast from "@radix-ui/react-toast";
import "./styles.css";

type Event = {
  id: number;
  study_id: string;
  domain: string;
  subject_id: string;
  sequence: number;
  sponsor_id: string;
  reported_term: string;
  modified_term: string | null;
  term: string;
  body_system: string;
  system_organ_class: string;
  location: string | null;
  severity: string;
  serious: string;
  category: string | null;
  subcategory: string | null;
  onset_date: string;
  end_date: string | null;
  ongoing: string;
  relationship: string;
  action_taken: string;
  outcome: string;
  caused_death: string;
  hospitalization: string;
  congenital_anomaly: string;
  narrative: string | null;
};
type Response = {
  items: Event[];
  total: number;
  page: number;
  page_size: number;
};
type Status = { status: string; error: string | null };
type StatusUpdate = Status & { adverseEventId: number };
type Notification = { title: string; description?: string };
function apiOrigin(): string {
  const { protocol, hostname } = window.location;
  // Codespaces/devcontainer port forwarding rewrites the hostname as
  // "<name>-<port>.<forwarding-domain>" instead of changing the port, so a
  // plain port swap only works for a normal (non-forwarded) localhost setup.
  const forwardedPortMatch = hostname.match(/^(.*)-5173(\..+)$/);
  if (forwardedPortMatch) {
    return `${protocol}//${forwardedPortMatch[1]}-8000${forwardedPortMatch[2]}`;
  }
  return `${protocol}//${hostname}:8000`;
}
const API = apiOrigin();

function App() {
  const [data, setData] = useState<Response>();
  const [page, setPage] = useState(1);
  const [statuses, setStatuses] = useState<Record<string, Status>>({});
  const [expandedId, setExpandedId] = useState<number>();
  const [notification, setNotification] = useState<Notification>();
  const [toastOpen, setToastOpen] = useState(false);
  const reportedFailures = useRef(new Set<string>());
  const handledCompletions = useRef(new Set<string>());
  const statusCheckFailed = useRef(false);

  function showNotification(next: Notification) {
    setNotification(next);
    setToastOpen(true);
  }

  function fetchEvents() {
    return fetch(`${API}/adverse-events?page=${page}`)
      .then((response) => response.json())
      .then(setData)
      .catch(() =>
        showNotification({ title: "Could not load adverse events." }),
      );
  }

  useEffect(() => {
    fetchEvents();
  }, [page]);

  useEffect(() => {
    const adverseEventIds = data?.items.map((event) => event.id);
    if (!adverseEventIds?.length) return;
    const stream = new EventSource(
      `${API}/narrative-status/stream?adverseEventIds=${adverseEventIds.join(",")}`,
    );
    stream.onmessage = ({ data: message }) => {
      const update: Record<string, Status> | StatusUpdate = JSON.parse(message);
      statusCheckFailed.current = false;
      const next =
        "adverseEventId" in update && typeof update.adverseEventId === "number"
          ? {
              [update.adverseEventId]: {
                error: update.error,
                status: update.status,
              },
            }
          : update;
      setStatuses((current) => ({ ...current, ...next }));
      let hasCompleted = false;
      Object.entries(next).forEach(([id, job]) => {
        if (job.status === "complete") {
          if (!handledCompletions.current.has(id)) {
            handledCompletions.current.add(id);
            hasCompleted = true;
          }
        } else {
          handledCompletions.current.delete(id);
        }
        if (job.status !== "failed") {
          reportedFailures.current.delete(id);
          return;
        }
        if (reportedFailures.current.has(id)) return;
        reportedFailures.current.add(id);
        showNotification({
          title: "Narrative generation failed",
          description: job.error ?? "Unknown error.",
        });
      });
      if (hasCompleted) fetchEvents();
    };
    stream.onerror = () => {
      if (statusCheckFailed.current) return;
      statusCheckFailed.current = true;
      showNotification({ title: "Could not check narrative status." });
    };
    return () => stream.close();
  }, [data]);

  async function addNarrative(id: number) {
    try {
      const response = await fetch(`${API}/adverse-events/${id}/narrative`, {
        method: "POST",
      });
      const result = await response.json();
      if (!response.ok)
        showNotification({
          title: "Could not start narrative",
          description: result.detail,
        });
      else
        setStatuses((current) => ({
          ...current,
          [id]: { status: result.status, error: null },
        }));
    } catch {
      showNotification({ title: "Could not start narrative generation." });
    }
  }

  const lastPage = data ? Math.ceil(data.total / data.page_size) : 1;
  return (
    <Toast.Provider duration={8000} swipeDirection="right">
      <main>
        <header>
          <div>
            <p className="summit-label">
              <img
                alt="Appsilon"
                className="appsilon-logo"
                src="/appsilon-logo.svg"
              />
              Validated AI for Pharma Summit 2026
            </p>
            <h1>Adverse Events Review</h1>
          </div>
        </header>
        <footer>
          <span>{data ? `${data.total} events` : "Loading..."}</span>
          <div>
            <button disabled={page === 1} onClick={() => setPage(page - 1)}>
              Previous
            </button>
            <span>
              {" "}
              Page {page} of {lastPage}{" "}
            </span>
            <button
              disabled={page === lastPage}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </footer>
        <table>
          <colgroup>
            <col className="subject-column" />
            <col className="term-column" />
            <col className="severity-column" />
            <col className="onset-column" />
            <col className="narrative-column" />
            <col className="actions-column" />
          </colgroup>
          <thead>
            <tr>
              <th>Subject</th>
              <th>Term</th>
              <th>Severity</th>
              <th>Onset</th>
              <th>Narrative</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((event) => {
              const active = ["queued", "running"].includes(
                statuses[event.id]?.status,
              );
              return (
                <Fragment key={event.id}>
                  <tr>
                    <td>
                      <button
                        aria-expanded={expandedId === event.id}
                        aria-label={`Show details for ${event.subject_id}`}
                        className="details-button"
                        onClick={() =>
                          setExpandedId((current) =>
                            current === event.id ? undefined : event.id,
                          )
                        }
                        title="Show event details"
                      >
                        {expandedId === event.id ? "-" : "+"}
                      </button>
                      {event.subject_id}
                    </td>
                    <td>{event.term}</td>
                    <td>
                      <span
                        className={`severity ${event.severity.toLowerCase()}`}
                      >
                        {event.severity}
                      </span>
                    </td>
                    <td>{event.onset_date}</td>
                    <td>
                      {event.narrative ? (
                        <HoverCard.Root openDelay={150}>
                          <HoverCard.Trigger asChild>
                            <button className="narrative-preview">
                              {event.narrative}
                            </button>
                          </HoverCard.Trigger>
                          <HoverCard.Portal>
                            <HoverCard.Content
                              className="narrative-popover"
                              side="top"
                              sideOffset={8}
                            >
                              {event.narrative}
                            </HoverCard.Content>
                          </HoverCard.Portal>
                        </HoverCard.Root>
                      ) : (
                        <span className="narrative-empty">Not generated</span>
                      )}
                    </td>
                    <td>
                      <button
                        disabled={active}
                        onClick={() => addNarrative(event.id)}
                      >
                        {active && <span className="spinner" />}
                        {event.narrative
                          ? "Rewrite Narrative"
                          : "Add Narrative"}
                      </button>
                    </td>
                  </tr>
                  {expandedId === event.id && (
                    <tr className="detail-row">
                      <td colSpan={6}>
                        <dl>
                          {[
                            ["Outcome", event.outcome],
                            ["Study", event.study_id],
                            ["Domain", event.domain],
                            ["Sequence", event.sequence],
                            ["Sponsor ID", event.sponsor_id],
                            ["Reported term", event.reported_term],
                            ["Modified term", event.modified_term],
                            ["Body system", event.body_system],
                            ["System organ class", event.system_organ_class],
                            ["Location", event.location],
                            ["Serious", event.serious],
                            ["Category", event.category],
                            ["Subcategory", event.subcategory],
                            ["End date", event.end_date],
                            ["Ongoing", event.ongoing],
                            ["Relationship", event.relationship],
                            ["Action taken", event.action_taken],
                            ["Caused death", event.caused_death],
                            ["Hospitalization", event.hospitalization],
                            ["Congenital anomaly", event.congenital_anomaly],
                          ].map(([label, value]) => (
                            <div key={label}>
                              <dt>{label}</dt>
                              <dd>{value ?? "Not reported"}</dd>
                            </div>
                          ))}
                        </dl>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </main>
      <Toast.Root
        className="toast"
        onAnimationEnd={() => !toastOpen && setNotification(undefined)}
        onOpenChange={setToastOpen}
        open={toastOpen}
      >
        <Toast.Title className="toast-title">{notification?.title}</Toast.Title>
        {notification?.description && (
          <Toast.Description className="toast-description">
            {notification.description}
          </Toast.Description>
        )}
        <Toast.Close aria-label="Dismiss notification" className="toast-close">
          ×
        </Toast.Close>
      </Toast.Root>
      <Toast.Viewport className="toast-viewport" />
    </Toast.Provider>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
