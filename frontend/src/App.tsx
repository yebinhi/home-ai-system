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

function clampDock(x: number, y: number, width: number, height: number) {
  const maxX = Math.max(8, window.innerWidth - width - 8);
  const maxY = Math.max(8, window.innerHeight - height - 8);
  return { x: Math.min(Math.max(8, x), maxX), y: Math.min(Math.max(8, y), maxY) };
}

function AssistantDock({
  open, onOpen, messages, busy, input, onInput, onAsk, thread,
}: {
  open: boolean;
  onOpen: (open: boolean) => void;
  messages: { from: 'user' | 'agent'; text: string }[];
  busy: boolean;
  input: string;
  onInput: (value: string) => void;
  onAsk: (event: React.FormEvent) => void;
  thread: React.RefObject<HTMLDivElement | null>;
}) {
  const dock = React.useRef<HTMLDivElement>(null);
  const drag = React.useRef<{ id: number; x: number; y: number; left: number; top: number; moved: boolean } | null>(null);
  const [placed, setPlaced] = React.useState<{ x: number; y: number } | null>(null);
  const [dragging, setDragging] = React.useState(false);

  React.useEffect(() => {
    if (window.innerWidth > 700) return;
    if (!open) {
      setPlaced(null);
      return;
    }
    const frame = requestAnimationFrame(() => {
      const el = dock.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      setPlaced(clampDock(
        (window.innerWidth - rect.width) / 2,
        (window.innerHeight - rect.height) / 2,
        rect.width,
        rect.height,
      ));
    });
    return () => cancelAnimationFrame(frame);
  }, [open]);

  React.useEffect(() => {
    const el = dock.current;
    if (!el || !placed || window.innerWidth <= 700) return;
    const rect = el.getBoundingClientRect();
    const next = clampDock(placed.x, placed.y, rect.width, rect.height);
    if (next.x !== placed.x || next.y !== placed.y) setPlaced(next);
  }, [open, placed]);

  React.useEffect(() => {
    const keepInside = () => {
      const el = dock.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const next = clampDock(rect.left, rect.top, rect.width, rect.height);
      if (Math.abs(next.x - rect.left) > 1 || Math.abs(next.y - rect.top) > 1) setPlaced(next);
    };
    window.addEventListener('resize', keepInside);
    return () => window.removeEventListener('resize', keepInside);
  }, []);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest('input, textarea, form, .dock-bar > button')) return;
    if (open && !target.closest('.dock-bar')) return;
    const el = dock.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, moved: false };
    setDragging(true);
    el.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    const el = dock.current;
    if (!state || state.id !== event.pointerId || !el) return;
    const dx = event.clientX - state.x;
    const dy = event.clientY - state.y;
    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) state.moved = true;
    const rect = el.getBoundingClientRect();
    setPlaced(clampDock(state.left + dx, state.top + dy, rect.width, rect.height));
  };

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = drag.current;
    if (!state || state.id !== event.pointerId) return;
    drag.current = null;
    setDragging(false);
    if (dock.current?.hasPointerCapture(event.pointerId)) dock.current.releasePointerCapture(event.pointerId);
    const dx = event.clientX - state.x;
    const dy = event.clientY - state.y;
    const moved = state.moved || Math.abs(dx) > 5 || Math.abs(dy) > 5;
    if (moved) {
      const el = dock.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      setPlaced(clampDock(state.left + dx, state.top + dy, rect.width, rect.height));
      return;
    }
    if (!open) onOpen(true);
  };

  return (
    <div
      className={`dock ${open ? 'open' : ''} ${placed ? 'placed' : ''} ${dragging ? 'dragging' : ''}`}
      style={placed ? { left: placed.x, top: placed.y } : undefined}
      ref={dock}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      {open ? (
        <>
          <div className="dock-bar">
            <img className="dock-face" src="/avatars/assistant.jpg" alt="" />
            <span className="dock-grip" role="button" aria-label="Move assistant">Assistant</span>
            <button type="button" aria-label="Minimize assistant" onClick={() => onOpen(false)}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" /></svg>
            </button>
          </div>
          <div className="chat" ref={thread}>
            {messages.length === 0 && <p className="hint">Ask about battery, solar, today’s generation, prices, or recorded events.</p>}
            {messages.map((message, index) => (
              <p key={index} className={`msg ${message.from}`}>
                <img src={message.from === 'user' ? '/avatars/you.jpg' : '/avatars/assistant.jpg'} alt="" />
                <span>{message.text}</span>
              </p>
            ))}
            {busy && (
              <p className="msg agent">
                <img src="/avatars/assistant.jpg" alt="" />
                <span>Thinking…</span>
              </p>
            )}
          </div>
          <form onSubmit={onAsk}>
            <input value={input} onChange={(event) => onInput(event.target.value)} placeholder="Ask about your home" aria-label="Message" />
            <button type="submit" className="primary" disabled={busy || !input.trim()}>Send</button>
          </form>
        </>
      ) : (
        <button type="button" className="dock-chip" aria-label="Open assistant">
          <img className="dock-face" src="/avatars/assistant.jpg" alt="" />
          Assistant
        </button>
      )}
    </div>
  );
}

function EventReel({ events }: { events: Event[] }) {
  const scroller = React.useRef<HTMLDivElement>(null);
  const drag = React.useRef<{ pointer: number; x: number; left: number } | null>(null);
  const [index, setIndex] = React.useState(0);
  const [dragging, setDragging] = React.useState(false);

  const sync = () => {
    const el = scroller.current;
    if (!el || el.clientWidth === 0) return;
    setIndex(Math.min(events.length - 1, Math.max(0, Math.round(el.scrollLeft / el.clientWidth))));
  };

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== 'mouse' || event.button !== 0) return;
    const el = scroller.current;
    if (!el) return;
    drag.current = { pointer: event.pointerId, x: event.clientX, left: el.scrollLeft };
    setDragging(true);
    el.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const el = scroller.current;
    const state = drag.current;
    if (!el || !state || state.pointer !== event.pointerId) return;
    el.scrollLeft = state.left - (event.clientX - state.x);
  };

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    const el = scroller.current;
    const state = drag.current;
    if (!el || !state || state.pointer !== event.pointerId) return;
    drag.current = null;
    setDragging(false);
    if (el.hasPointerCapture(event.pointerId)) el.releasePointerCapture(event.pointerId);
    const width = el.clientWidth || 1;
    const dx = event.clientX - state.x;
    let next = Math.round(state.left / width);
    if (dx <= -48) next += 1;
    else if (dx >= 48) next -= 1;
    next = Math.max(0, Math.min(events.length - 1, next));
    el.scrollTo({ left: next * width, behavior: 'smooth' });
    setIndex(next);
  };

  return (
    <div className="event-reel">
      <div
        className={`event-reel-track ${dragging ? 'dragging' : ''}`}
        ref={scroller}
        onScroll={sync}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        aria-label="Security events. Swipe left for the next one."
      >
        {events.map((event) => (
          <article key={event.id}>
            {event.cover ? <img src={event.cover} alt="" draggable={false} /> : <div className="event-photo" />}
            <p>{event.summary}</p>
            <span>{event.camera} · {clock(event.timestamp)} · {event.kind.replaceAll('_', ' ')} · {event.severity}</span>
          </article>
        ))}
      </div>
      {events.length > 1 && (
        <div className="event-dots" aria-hidden="true">
          {events.map((event, dot) => <i key={event.id} className={dot === index ? 'on' : ''} />)}
        </div>
      )}
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
  const [chatOpen, setChatOpen] = React.useState(false);

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
  const [section, setSection] = React.useState('solar');
  React.useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight });
  }, [messages, chatBusy]);
  React.useEffect(() => {
    const nodes = ['solar', 'security']
      .map((id) => document.getElementById(id))
      .filter((node): node is HTMLElement => Boolean(node));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible?.target.id) setSection(visible.target.id);
    }, { rootMargin: '-15% 0px -50% 0px', threshold: [0.2, 0.5] });
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  const showSection = (id: string) => {
    setSection(id);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const soc = status ? `${Math.round(status.soc_pct)}%` : '—';
  const live = Boolean(health?.ok);
  const demo = health?.mode === 'DEMO';
  const shownEvents = events.length ? events : SAMPLE_EVENTS;
  const high = shownEvents.filter((event) => event.severity === 'high').length;
  const people = shownEvents.filter((event) => event.kind.includes('person')).length;
  const vehicles = shownEvents.filter((event) => event.kind.includes('vehicle')).length;

  const nav = [
    ['solar', 'Solar', 'M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8ZM12 2v2M12 20v2M2 12h2M20 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4'],
    ['security', 'Security', 'M12 3 5 6v6c0 4 2.7 6.8 7 8 4.3-1.2 7-4 7-8V6l-7-3Z'],
    ['assistant', 'Assistant', 'M5 6h14v9H8l-3 3V6Z'],
  ] as const;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="side-brand">
          <h1>Home</h1>
          <span className={live ? 'pill' : 'pill down'}><i />{offline ? 'Offline' : demo ? 'Demo' : 'Live'}</span>
        </div>
        <nav>
          {nav.map(([id, label, icon]) => (
            <button
              key={id}
              type="button"
              className={id === 'assistant' ? (chatOpen ? 'on' : '') : (section === id ? 'on' : '')}
              onClick={() => (id === 'assistant' ? setChatOpen((value) => !value) : showSection(id))}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d={icon} /></svg>
              {label}
            </button>
          ))}
        </nav>
        <button type="button" className="refresh" onClick={() => void update()}>Refresh</button>
      </aside>
      <main className="home">
      <header className="top">
        <h1>Home</h1>
        <div className="top-meta">
          <span className={live ? 'live' : 'down'}>{offline ? 'Offline' : demo ? 'Demo data' : 'Live'}</span>
          <button type="button" onClick={() => void update()}>Refresh</button>
        </div>
      </header>

      {offline && <p className="banner">Backend is not reachable.</p>}

      <section className="block" id="solar" aria-label="Solar">
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

      <section className="block" id="security" aria-label="Security">
        <p className="label">Security</p>
        <div className="card">
          <p className="foot security-line">{shownEvents.length} events · {high} high · {people} {people === 1 ? 'person' : 'people'} · {vehicles} {vehicles === 1 ? 'vehicle' : 'vehicles'}</p>
          <EventReel events={shownEvents} />
        </div>
      </section>

      </main>
      <AssistantDock
        open={chatOpen}
        onOpen={setChatOpen}
        messages={messages}
        busy={chatBusy}
        input={chatInput}
        onInput={setChatInput}
        onAsk={(event) => void ask(event)}
        thread={thread}
      />
    </div>
  );
}
