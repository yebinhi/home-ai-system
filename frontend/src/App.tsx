import * as React from 'react';
import { api } from './api';
import type { Event, Generation, Health, Plan, Status } from './types';

const kw = (v?: number) => (Number.isFinite(v) ? `${v!.toFixed(2)} kW` : '—');
const kwh = (v?: number) => (Number.isFinite(v) ? `${v!.toFixed(1)} kWh` : '—');
const money = (v?: number) =>
  Number.isFinite(v) ? new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(v!) : '—';
const clock = (iso: string) => {
  try {
    return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' }).format(new Date(iso));
  } catch {
    return '—';
  }
};

function isPlan(p: Plan | { message: string } | null): p is Plan {
  return Boolean(p && 'slots' in p && Array.isArray((p as Plan).slots));
}

const SAMPLE_EVENTS: Event[] = [
  { id: 'sample-cats', timestamp: '2026-10-15T08:48:00Z', camera: 'Front yard', kind: 'animal', severity: 'low', summary: 'Two cats visited the front yard.', source: 'sample', cover: '/events/cats-0948.jpg' },
  { id: 'sample-vehicle', timestamp: '2026-10-15T07:41:00Z', camera: 'Driveway', kind: 'vehicle', severity: 'medium', summary: 'A car stopped on the driveway.', source: 'sample', cover: '/events/vehicle-0841.jpg' },
  { id: 'sample-person', timestamp: '2026-10-15T06:14:00Z', camera: 'Front door', kind: 'person', severity: 'high', summary: 'A person walked up to the front door.', source: 'sample', cover: '/events/person-0714.jpg' },
  { id: 'sample-parcel-0630', timestamp: '2026-10-15T05:30:00Z', camera: 'Front door', kind: 'package', severity: 'medium', summary: 'A second parcel was left at the door.', source: 'sample', cover: '/events/parcel-0630.jpg' },
  { id: 'sample-parcel-0530', timestamp: '2026-10-15T04:30:00Z', camera: 'Front door', kind: 'package', severity: 'medium', summary: 'A parcel was delivered at the front door.', source: 'sample', cover: '/events/parcel-0530.jpg' },
  { id: 'sample-fox', timestamp: '2026-10-15T02:40:00Z', camera: 'Back garden', kind: 'animal', severity: 'low', summary: 'A fox visited the back garden.', source: 'sample', cover: '/events/fox-0340.jpg' },
];

const MODE_LABEL: Record<string, string> = {
  ForceCharge: 'Force Charge',
  SelfUse: 'Self-Use',
  Feedin: 'Feed-in Priority',
  Backup: 'Backup',
};

function londonClock(ms: number) {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London', hourCycle: 'h23',
  }).format(new Date(ms));
}

function londonParts(ms: number) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/London',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(ms));
  const num = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value ?? '0');
  return { year: num('year'), month: num('month'), day: num('day'), hour: num('hour'), minute: num('minute'), second: num('second') };
}

function londonMidnight(ms: number) {
  const clock = londonParts(ms);
  const shown = Date.UTC(clock.year, clock.month - 1, clock.day, clock.hour, clock.minute, clock.second);
  return Date.UTC(clock.year, clock.month - 1, clock.day) - (shown - ms);
}

function nextLondonMidnight(ms: number) {
  return londonMidnight(londonMidnight(ms) + 26 * 60 * 60 * 1000);
}

function timeRange(startMs: number, endMs: number, dayEnd: number) {
  const end = endMs >= dayEnd - 1000 ? '23:59' : londonClock(endMs);
  return `${londonClock(startMs)}–${end}`;
}

function samplePlan(startIso?: string): Plan {
  const start = startIso ? new Date(startIso) : new Date();
  const modes: Plan['slots'][number]['mode_hint'][] = [
    ...Array(8).fill('ForceCharge'),
    ...Array(12).fill('SelfUse'),
    ...Array(12).fill('Feedin'),
    ...Array(8).fill('Backup'),
    ...Array(8).fill('SelfUse'),
  ];
  return {
    id: 'sample',
    created_at: new Date().toISOString(),
    source: 'SAMPLE',
    simulated: true,
    forecast_quality: 'SAMPLE',
    executable: false,
    horizon_hours: 24,
    step_minutes: 30,
    predicted_import_cost_gbp: 0,
    predicted_export_revenue_gbp: 0,
    predicted_degradation_cost_gbp: 0,
    predicted_net_cost_gbp: 0,
    notes: [],
    slots: modes.map((mode, index) => ({
      start: new Date(start.getTime() + index * 30 * 60 * 1000).toISOString(),
      soc_start_pct: 50,
      soc_end_pct: 50,
      import_kwh: 0,
      export_kwh: 0,
      grid_charge_kwh: 0,
      solar_charge_kwh: 0,
      battery_home_kwh: 0,
      mode_hint: mode,
    })),
  };
}

function Schedule({ plan }: { plan: Plan }) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);

  const midnight = londonMidnight(now);
  const dayEnd = nextLondonMidnight(now);
  const dayMs = dayEnd - midnight;
  const pct = (ms: number) => ((ms - midnight) / dayMs) * 100;
  const step = (plan.step_minutes || 30) * 60 * 1000;
  const spans: { mode: string; start: number; end: number }[] = [];
  plan.slots.forEach((slot, index) => {
    const start = new Date(slot.start).getTime();
    const next = plan.slots[index + 1];
    const nextStart = next ? new Date(next.start).getTime() : start + step;
    const end = nextStart - start <= step + 1000 ? nextStart : start + step;
    const from = Math.max(start, midnight);
    const to = Math.min(end, dayEnd);
    if (to <= from) return;
    const previous = spans[spans.length - 1];
    if (previous && previous.mode === slot.mode_hint && Math.abs(previous.end - from) < 1000) previous.end = to;
    else spans.push({ mode: slot.mode_hint, start: from, end: to });
  });
  const ticks = Array.from({ length: 25 }, (_, hour) => ({
    hour,
    pct: (hour / 24) * 100,
    label: hour % 3 === 0 ? (hour === 24 ? '23:59' : `${String(hour).padStart(2, '0')}:00`) : '',
    sparse: hour % 6 !== 0,
  }));
  const callouts = spans.map((span, index) => {
    const name = MODE_LABEL[span.mode] || span.mode;
    const center = pct((span.start + span.end) / 2);
    const align = center < 12 ? 'start' : center > 88 ? 'end' : 'mid';
    return { ...span, name, center, align, side: index % 2 === 0 ? 'above' : 'below' };
  });
  const above = callouts.filter((item) => item.side === 'above');
  const below = callouts.filter((item) => item.side === 'below');
  const markers = (items: typeof callouts) => items.map((item) => (
    <div key={`${item.mode}-${item.start}`} className={`callout ${item.side}`} style={{ left: `${item.center}%` }}>
      {item.side === 'below' && <i className={`seg-${item.mode}`} />}
      <span className={item.align}>{item.name}</span>
      {item.side === 'above' && <i className={`seg-${item.mode}`} />}
    </div>
  ));
  const nowPct = Math.min(100, Math.max(0, pct(now)));
  const nowEdge = nowPct < 8 ? 'start' : nowPct > 92 ? 'end' : '';
  return (
    <div className="timeline">
      {above.length > 0 && <div className="callouts">{markers(above)}</div>}
      <div className="track">
        <div className="schedule" role="img" aria-label={`Today's work modes, now ${londonClock(now)}`}>
          {spans.map((span) => {
            const name = MODE_LABEL[span.mode] || span.mode;
            return (
              <span
                key={`${span.mode}-${span.start}`}
                className={`seg seg-${span.mode}`}
                style={{ left: `${pct(span.start)}%`, width: `${pct(span.end) - pct(span.start)}%` }}
                title={`${name}, ${timeRange(span.start, span.end, dayEnd)}`}
              />
            );
          })}
        </div>
        <div className={`now ${nowEdge}`} style={{ left: `${nowPct}%` }}>
          <span>{londonClock(now)}</span>
          <i />
        </div>
      </div>
      {below.length > 0 && <div className="callouts below">{markers(below)}</div>}
      <div className="ruler" aria-hidden="true">
        {ticks.map((tick) => (
          <div key={tick.hour} className={`tick ${tick.hour === 0 ? 'tick-start' : ''} ${tick.hour === 24 ? 'tick-end' : ''}`} style={{ left: `${tick.pct}%` }}>
            <i />
            {tick.label && <span className={tick.sparse ? 'sparse' : ''}>{tick.label}</span>}
          </div>
        ))}
      </div>
      <ul className="periods">
        {spans.map((span) => (
          <li key={`${span.mode}-${span.start}`}>
            <i className={`swatch seg-${span.mode}`} />
            <span>{timeRange(span.start, span.end, dayEnd)}</span>
            <strong>{MODE_LABEL[span.mode] || span.mode}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EventList({ events }: { events: Event[] }) {
  return (
    <div className="event-list">
      {events.map((event) => (
        <article key={event.id} className={`sev-${event.severity}`}>
          {event.cover && <img src={event.cover} alt="" />}
          <div>
            <strong>{event.camera}</strong>
            <span>{clock(event.timestamp)} · {event.kind.replaceAll('_', ' ')} · {event.severity}</span>
            <p>{event.summary}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

export default function App() {
  const [health, setHealth] = React.useState<Health | null>(null);
  const [status, setStatus] = React.useState<Status | null>(null);
  const [generation, setGeneration] = React.useState<Generation | null>(null);
  const [plan, setPlan] = React.useState<Plan | null>(null);
  const [events, setEvents] = React.useState<Event[]>([]);
  const [offline, setOffline] = React.useState(false);
  const [preview, setPreview] = React.useState(false);
  const [chatInput, setChatInput] = React.useState('');
  const [messages, setMessages] = React.useState<{ from: 'user' | 'agent'; text: string }[]>([]);
  const [chatBusy, setChatBusy] = React.useState(false);

  const update = React.useCallback(async () => {
    const results = await Promise.allSettled([api.health(), api.status(), api.generation(), api.plan(), api.events()]);
    if (results[0].status === 'fulfilled') {
      setHealth(results[0].value);
      setOffline(false);
    } else {
      setHealth(null);
      setOffline(true);
    }
    setStatus(results[1].status === 'fulfilled' ? results[1].value : null);
    setGeneration(results[2].status === 'fulfilled' ? results[2].value : null);
    setPlan(results[3].status === 'fulfilled' && isPlan(results[3].value) ? results[3].value : null);
    setEvents(results[4].status === 'fulfilled' ? results[4].value : []);
  }, []);

  React.useEffect(() => {
    void update();
    const timer = setInterval(() => void update(), 120000);
    return () => clearInterval(timer);
  }, [update]);

  const ask = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || chatBusy) return;
    setMessages((old) => [...old, { from: 'user', text: message }]);
    setChatInput('');
    setChatBusy(true);
    try {
      const reply = await api.chat(message);
      setMessages((old) => [...old, { from: 'agent', text: reply.answer }]);
    } catch {
      setMessages((old) => [...old, { from: 'agent', text: 'The assistant is unavailable. Check the OpenAI key and MCP services.' }]);
    } finally {
      setChatBusy(false);
    }
  };

  const thread = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight });
  }, [messages, chatBusy]);

  const soc = status ? `${Math.round(status.soc_pct)}%` : '—';
  const live = Boolean(health?.ok);
  const demo = health?.mode === 'DEMO';
  const shownEvents = events.length ? events : SAMPLE_EVENTS;
  const high = shownEvents.filter((event) => event.severity === 'high').length;
  const people = shownEvents.filter((event) => event.kind.includes('person')).length;
  const vehicles = shownEvents.filter((event) => event.kind.includes('vehicle')).length;

  return (
    <main className="home">
      <header className="top">
        <h1>Home</h1>
        <div className="top-meta">
          <span className={live ? 'live' : 'down'}>{offline ? 'Offline' : demo ? 'Demo data' : 'Live'}</span>
          <button type="button" onClick={() => void update()}>Refresh</button>
        </div>
      </header>

      {offline && <p className="banner">Backend is not reachable.</p>}

      <section className="block" aria-label="Solar">
        <p className="label">Solar</p>
        <div className="card">
          <div className="metrics">
            <div className="primary"><span>Battery</span><strong>{soc}</strong></div>
            <div className="primary"><span>Solar now</span><strong>{kw(status?.solar_kw)}</strong></div>
            <div><span>Today</span><strong>{kwh(generation?.today_kwh)}</strong></div>
            <div><span>This month</span><strong>{kwh(generation?.month_kwh)}</strong></div>
          </div>
          <p className="foot">
            Load {kw(status?.load_kw)} · Grid {kw(status?.grid_kw)} · Battery {kw(status?.battery_kw)} · Lifetime {kwh(generation?.cumulative_kwh)}
          </p>
          <div className="split">
            <div className="row">
              <h2>Energy plan</h2>
              <div className="actions">
                <button type="button" onClick={() => setPreview((value) => !value)}>{preview ? 'Your plan' : 'Sample modes'}</button>
              </div>
            </div>
            {preview || plan ? (
              <>
                <p className="hint">{preview ? 'Sample modes, to check the timeline. Not your tariff, and not sent to Fox.' : `Updated automatically at 22:00. Projected net cost ${money(plan!.predicted_net_cost_gbp)}. Simulation only, not sent to Fox.`}</p>
                <Schedule plan={preview ? samplePlan(new Date(londonMidnight(Date.now())).toISOString()) : plan!} />
              </>
            ) : (
              <p className="hint">No plan yet.</p>
            )}
          </div>
        </div>
      </section>

      <section className="block" aria-label="Security">
        <p className="label">Security</p>
        <div className="card">
          <p className="foot security-line">{shownEvents.length} events · {high} high · {people} {people === 1 ? 'person' : 'people'} · {vehicles} {vehicles === 1 ? 'vehicle' : 'vehicles'}</p>
          <EventList events={shownEvents} />
        </div>
      </section>

      <section className="block" aria-label="Assistant">
        <p className="label">Assistant</p>
        <div className="card chat-card">
          <div className="chat" ref={thread}>
            {messages.length === 0 && <p className="hint">Ask about battery, solar, today’s generation, prices, or recorded events.</p>}
            {messages.map((message, index) => (
              <p key={index} className={message.from}>{message.text}</p>
            ))}
            {chatBusy && <p className="agent">Thinking…</p>}
          </div>
          <form onSubmit={(event) => void ask(event)}>
            <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask about your home" aria-label="Message" />
            <button type="submit" className="primary" disabled={chatBusy || !chatInput.trim()}>Send</button>
          </form>
        </div>
      </section>
    </main>
  );
}
