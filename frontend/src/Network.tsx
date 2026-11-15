import type { LabEvent, ProcessNode } from './types'

const initialPositions = [[400, 76], [657, 222], [557, 425], [243, 425], [143, 222]]
const stateLabel = { RELEASED: 'THẢ', WANTED: 'MUỐN', HELD: 'GIỮ' }

export default function Network({ nodes, selected, onSelect, events }: {
  nodes: ProcessNode[]; selected: number; onSelect: (id: number) => void; events: LabEvent[]
}) {
  const position = (index: number) => nodes.length === 5 ? initialPositions[index]
    : [400 + 265 * Math.sin(2 * Math.PI * index / nodes.length), 265 - 190 * Math.cos(2 * Math.PI * index / nodes.length)]
  const positions = new Map(nodes.map((n, i) => [n.id, position(i)]))
  const latest = events.filter(e => e.type === 'MESSAGE_SENT' && e.message).slice(-10)
    .filter(e => Date.now() - Date.parse(e.collected_at) < 1800)
  const owners = nodes.filter(n => n.online && n.state === 'HELD')
  const owner = owners.length === 1 ? owners[0] : undefined
  return <div className="network-surface">
    <svg viewBox="0 0 800 510" role="group" aria-label="Mạng tiến trình Ricart và Agrawala">
      <defs>
        <pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#334048" /></pattern>
        <marker id="request-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#f2bd70" /></marker>
        <marker id="reply-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#82ddbc" /></marker>
      </defs>
      <rect width="800" height="510" fill="url(#grid)" />
      {nodes.flatMap((n, i) => nodes.slice(i + 1).map((m) => {
        const [x1,y1] = positions.get(n.id)!, [x2,y2] = positions.get(m.id)!
        return <line key={`${n.id}-${m.id}`} x1={x1} y1={y1} x2={x2} y2={y2} className="peer-edge" />
      }))}
      {latest.map(e => {
        const m = e.message!, from = positions.get(m.sender_id), to = positions.get(m.receiver_id)
        if (!from || !to) return null
        const path = `M ${from[0]} ${from[1]} L ${to[0]} ${to[1]}`
        const color = m.type === 'REQUEST' ? '#f2bd70' : '#82ddbc'
        return <g key={e.event_id} className="transmission">
          <path d={path} fill="none" stroke={color} strokeWidth="1.5" opacity=".55" markerEnd={`url(#${m.type.toLowerCase()}-arrow)`} />
          <circle r="4" fill={color}><animateMotion dur="1.2s" path={path} repeatCount="1" fill="freeze" /></circle>
          <text x={(from[0]+to[0])/2} y={(from[1]+to[1])/2-8} textAnchor="middle" fill={color} fontSize="10" className="mono">{m.type} · T{m.timestamp}</text>
        </g>
      })}
      <g transform="translate(400,255)">
        <circle r="74" fill="#141e23" stroke={owner ? '#82ddbc' : '#35434b'} strokeWidth="1" />
        <circle r="65" fill="none" stroke={owner ? '#82ddbc' : '#35434b'} strokeDasharray="3 7" opacity=".35" />
        <rect x="-12" y="-28" width="24" height="19" rx="4" fill="none" stroke={owner ? '#82ddbc' : '#95a4ad'} strokeWidth="1.6" />
        <path d="M -7 -28 v -5 a 7 7 0 0 1 14 0 v 5" fill="none" stroke={owner ? '#82ddbc' : '#95a4ad'} strokeWidth="1.6" />
        <text y="11" textAnchor="middle" fill="#e7edef" fontSize="12" fontWeight="600">VÙNG TỚI HẠN</text>
        <text y="32" textAnchor="middle" fill={owner ? '#82ddbc' : '#94a2aa'} fontSize="12">{owners.length > 1 ? 'Đang đồng bộ quan sát' : owner ? `P${owner.id} đang giữ` : 'Chưa có chủ sở hữu'}</text>
      </g>
      {nodes.map((n, i) => {
        const [x,y] = position(i)
        return <g key={n.id} transform={`translate(${x - 76},${y - 48})`} role="button" tabIndex={0}
          aria-label={`Chọn P${n.id}, ${n.online ? n.state : 'offline'}, đồng hồ ${n.clock}`}
          onClick={() => onSelect(n.id)} onKeyDown={e => { if(e.key === 'Enter' || e.key === ' ') {e.preventDefault(); onSelect(n.id)} }}
          className={`process-visual ${n.online ? n.state.toLowerCase() : 'offline'} ${selected === n.id ? 'selected' : ''}`}>
          <rect width="152" height="101" rx="10" className="node-bg" />
          <circle cx="18" cy="22" r="3.5" className="node-dot" />
          <text x="29" y="27" className="node-title">P{n.id}</text>
          <text x="136" y="25" textAnchor="end" className="node-state">{n.online ? stateLabel[n.state] : 'OFFLINE'}</text>
          <line x1="13" x2="139" y1="39" y2="39" stroke="#2d3a42" />
          <text x="15" y="60" fill="#8b9ca6" fontSize="10">LAMPORT</text>
          <text x="137" y="62" textAnchor="end" className="node-clock">{String(n.clock).padStart(2, '0')}</text>
          <text x="15" y="83" fill="#a4b0b7" fontSize="10">REPLY {n.replies.length}/{n.expected_replies}</text>
          <text x="137" y="83" textAnchor="end" fill="#a4b0b7" fontSize="10">HOÃN {n.deferred.length}</text>
          {n.request_timestamp !== null && <text x="76" y="118" textAnchor="middle" fill="#f2bd70" fontSize="10" className="mono">Ưu tiên ({n.request_timestamp}, {n.id})</text>}
        </g>
      })}
    </svg>
    <div className="network-foot"><span><i className="dot mint" /> REPLY</span><span><i className="dot amber" /> REQUEST</span><span className="network-foot-note">Chọn một tiến trình để tương tác</span></div>
  </div>
}
