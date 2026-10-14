import * as React from 'react';

const paths: Record<string, React.ReactNode> = {
  home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M9 21v-8h6v8"/></>,
  energy: <><path d="M5 20V11M12 20V4M19 20v-9"/></>,
  shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
  chat: <><path d="M21 11.5a8.3 8.3 0 0 1-.8 3.6 8.5 8.5 0 0 1-7.6 4.9 9.7 9.7 0 0 1-3.6-.7L3 21l1.8-5.7a9.7 9.7 0 0 1-.8-3.8A8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5Z"/></>,
  automation: <><circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="m11 7-5 10M13 7l5 10M7 19h10"/></>,
  history: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
  settings: <><path d="M10 3h4l1 3 3 1 3-1 2 4-2 2v3l2 2-2 4-3-1-3 1-1 3h-4l-1-3-3-1-3 1-2-4 2-2v-3l-2-2 2-4 3 1 3-1z"/><circle cx="12" cy="13" r="3"/></>,
  search: <><circle cx="10.8" cy="10.8" r="7"/><path d="m16 16 5 5"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/></>,
  battery: <><rect x="4" y="6" width="16" height="14" rx="2"/><path d="M10 3h4M13 9l-3 5h4l-3 4"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></>,
  arrow: <path d="m9 18 6-6-6-6"/>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.5-5M4 3v5h5M4 13a8 8 0 0 0 14.5 5M20 21v-5h-5"/></>,
  check: <path d="m5 12 4 4 10-10"/>,
  close: <path d="M18 6 6 18M6 6l12 12"/>,
  info: <><circle cx="12" cy="12" r="10"/><path d="M12 11v6M12 7h.01"/></>,
  warning: <><path d="m12 3 10 18H2z"/><path d="M12 9v4m0 4h.01"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
  bolt: <path d="m13 2-9 12h7l-1 8 10-13h-7z"/>,
  cloud: <><path d="M20 16.5A4.5 4.5 0 0 0 17 8a6 6 0 0 0-11.5 2A4.5 4.5 0 0 0 6 19h13a4 4 0 0 0 1-2.5"/></>,
  car: <><path d="M5 11 7 5h10l2 6M4 11h16v7H4z"/><circle cx="7" cy="18" r="1"/><circle cx="17" cy="18" r="1"/></>,
  camera: <><rect x="2" y="5" width="17" height="14" rx="2"/><path d="m19 10 3-2v8l-3-2"/><circle cx="10.5" cy="12" r="3"/></>,
  sparkles: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM19 18l.6 1.4L21 20l-1.4.6L19 22l-.6-1.4L17 20l1.4-.6L19 18Z"/></>,
  send: <><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/></>,
  external: <><path d="M13 5h6v6M19 5l-9 9"/><path d="M19 13v6H5V5h6"/></>,
  list: <><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></>,
  wifi: <><path d="M2 9a16 16 0 0 1 20 0M5 13a11 11 0 0 1 14 0M9 17a5 5 0 0 1 6 0M12 21h.01"/></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/></>,
  link: <><path d="M10 13a5 5 0 0 0 8.2 1l2-2a5 5 0 0 0-7-7l-1.2 1.2M14 11a5 5 0 0 0-8.2-1l-2 2a5 5 0 0 0 7 7l1.2-1.2"/></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
};
export default function Icon({name, size=18, className='', strokeWidth=1.8}:{name:string;size?:number;className?:string;strokeWidth?:number}){
  return <svg aria-hidden="true" className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.info}</svg>;
}
