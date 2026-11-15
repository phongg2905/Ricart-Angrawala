import { useState } from 'react'
import { Activity, ArrowDownLeft, ArrowUpRight, BookOpen, Check, CircleHelp, Clock3, Code2, Download, ExternalLink, FlaskConical, Layers3, LockKeyhole, Network as NetworkIcon, Play, Radio, RotateCcw, Send, ShieldCheck, Square, Terminal, Trash2, UnlockKeyhole, Wifi, X, Zap } from 'lucide-react'
import type { LabEvent, ProcessNode } from './types'
import { useSimulation } from './useSimulation'
import Network from './Network'

const fallback: ProcessNode[] = Array.from({length: 5}, (_, i) => ({
  id: i+1, state: 'RELEASED', online: false, clock: 0, request_id: null, request_timestamp: null,
  replies: [], expected_replies: 4, deferred: [], completed: 0, sent: {REQUEST: 0, REPLY: 0}, network_errors: {},
}))
const labels = { RELEASED: 'Thả', WANTED: 'Muốn', HELD: 'Giữ' }
const eventLabels: Record<string, string> = {NODE_STARTED: 'NODE START', REQUEST_CREATED: 'LOCAL REQUEST', CS_ENTER: 'CS ENTER', CS_EXIT: 'CS EXIT', REPLY_DEFERRED: 'DEFERRED', NETWORK_ERROR: 'NETWORK ERROR', WAIT_WARNING: 'WAIT WARNING', REPLY_IGNORED: 'IGNORED'}

function eventKind(e: LabEvent) { return e.message?.type ?? eventLabels[e.type] ?? e.type }
function localTime(date: string) { return new Date(date).toLocaleTimeString('vi-VN', {hour12: false}) }

export default function App() {
  const {snapshot: s, events, connected, error, busy, action, call, clear, dismiss} = useSimulation()
  const [selected, setSelected] = useState(1)
  const [automatic, setAutomatic] = useState(true)
  const [duration, setDuration] = useState(3)
  const [group, setGroup] = useState('pair')
  const [filter, setFilter] = useState('ALL')
  const [nodeFilter, setNodeFilter] = useState('ALL')
  const [tab, setTab] = useState('overview')
  const nodes = s?.nodes ?? fallback
  const current = nodes.find(n => n.id === selected) ?? nodes[0]
  const external = s?.mode === 'external'
  const ready = connected && !!s?.running && !s?.error
  const waiting = nodes.filter(n => n.online && n.state === 'WANTED').sort((a,b) => (a.request_timestamp! - b.request_timestamp!) || a.id-b.id)
  const visibleEvents = events.filter(e => (filter === 'ALL' || (filter === 'CS' ? e.type.startsWith('CS_') : e.message?.type === filter)) && (nodeFilter === 'ALL' || e.node_id === Number(nodeFilter))).slice(-150).reverse()
  const options = {duration: automatic ? duration : null}

  function concurrent() {
    const targets = (group === 'pair' ? nodes.slice(0,2) : nodes).filter(n => n.state === 'RELEASED' && n.online)
    return Promise.allSettled(targets.map(n => call(`nodes/${n.id}/request`, options))).then(results => {
      const failed = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected')
      if (failed.length) throw new Error(failed.map(r => r.reason.message).join('; '))
    })
  }
  function exportEvents() {
    const url = URL.createObjectURL(new Blob([events.map(e => JSON.stringify(e)).join('\n')], {type:'application/x-ndjson'}))
    const link = document.createElement('a'); link.href = url; link.download = 'ricart-agrawala-events.jsonl'; link.click(); URL.revokeObjectURL(url)
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="#" className="brand-mark" aria-label="Distributed Systems Lab"><Layers3 size={24}/></a>
      <div className="sidebar-divider"/>
      <button aria-label="Tổng quan" title="Tổng quan" className={tab === 'overview' ? 'nav-item active' : 'nav-item'} onClick={() => setTab('overview')}><NetworkIcon size={21}/></button>
      <button aria-label="Lý thuyết thuật toán" title="Lý thuyết thuật toán" className={tab === 'theory' ? 'nav-item active' : 'nav-item'} onClick={() => setTab('theory')}><BookOpen size={21}/></button>
      <button aria-label="Hướng dẫn demo" title="Hướng dẫn demo" className={tab === 'guide' ? 'nav-item active' : 'nav-item'} onClick={() => setTab('guide')}><Terminal size={21}/></button>
      <div className="sidebar-bottom"><span className="version-tag">v1.0</span><button className="nav-item" aria-label="Trợ giúp" onClick={() => setTab('guide')}><CircleHelp size={21}/></button><div className="avatar">DS</div></div>
    </aside>

    <div className="workspace">
      <header className="topbar"><div className="breadcrumb"><span>Distributed Systems Lab</span><span className="slash">/</span><strong>Mutual Exclusion</strong></div><div className="topbar-right"><span className="course-tag"><FlaskConical size={13}/> PHÒNG THỰC HÀNH</span><span className={`connection ${connected ? '' : 'disconnected'}`}><i className="dot"/>{connected ? 'Đã kết nối' : 'Đang kết nối lại'}</span></div></header>
      <main>
        <section className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/> THUẬT TOÁN PHÂN TÁN <span className="muted">/ 01</span></div><h1>Ricart <span className="amp">&</span> Agrawala<span className="title-dot">.</span></h1><p>Khám phá cách các tiến trình phối hợp để cùng chia sẻ một vùng tới hạn.</p></div><div className="heading-actions"><button className="button ghost" onClick={() => setTab(tab === 'theory' ? 'overview' : 'theory')}><BookOpen size={15}/> Tìm hiểu thuật toán <ExternalLink size={12}/></button><span className="protocol-tag">TCP <span>·</span> LAMPORT <span>·</span> NO COORDINATOR</span></div></section>

        {(error || s?.error) && <div className="error-banner" role="alert"><Activity size={17}/><span>{error || s?.error}</span>{error && <button aria-label="Đóng thông báo" onClick={dismiss}><X size={17}/></button>}</div>}
        {!connected && <div className="notice"><Wifi size={15}/> Mất kết nối giám sát. Các node tiếp tục chạy độc lập; dữ liệu hiển thị có thể đã cũ.</div>}
        {connected && s?.status === 'DEGRADED' && <div className="notice"><Wifi size={15}/> Thiếu node trong membership. Node còn hoạt động vẫn có thể gửi yêu cầu nhưng phải chờ đủ quyền; timeout không tự cấp quyền.</div>}
        {connected && nodes.some(n => !n.online && n.connection_error) && <div className="node-diagnostics" role="status"><strong>Node chưa kết nối được</strong><ul>{nodes.filter(n => !n.online && n.connection_error).map(n => <li key={n.id}><b>P{n.id}</b> · {n.connection_error}</li>)}</ul><p>Đổi IP hoặc file cấu hình cần khởi động lại các tiến trình liên quan. Mở được dashboard chưa có nghĩa cổng TCP của node đã mở.</p></div>}

        {tab !== 'overview' ? <Educational tab={tab} onBack={() => setTab('overview')}/> : <>
        <section className="metrics-grid" aria-label="Thống kê phiên">
          <Metric icon={<Radio size={17}/>} label="TIẾN TRÌNH HOẠT ĐỘNG" value={<>{s?.active_nodes ?? 0}<small> / {nodes.length}</small></>} detail={s?.running ? 'Membership cố định trong phiên' : 'Sẵn sàng khởi động phiên'} />
          <Metric icon={<ArrowUpRight size={17}/>} label="THÔNG ĐIỆP REQUEST" value={s?.requests ?? 0} detail="Thông điệp yêu cầu quyền" />
          <Metric icon={<ArrowDownLeft size={17}/>} label="THÔNG ĐIỆP REPLY" value={s?.replies ?? 0} detail="Thông điệp cấp quyền" />
          <Metric icon={<Check size={17}/>} label="LƯỢT TRUY CẬP HOÀN TẤT" value={s?.completed ?? 0} detail={<><span className="mini-pill">2(N − 1)</span> thông điệp / lượt</>} />
        </section>

        <div className="primary-grid">
          <section className="panel network-panel"><div className="panel-heading"><div><h2><NetworkIcon size={17}/> Mạng tiến trình</h2><p>Các node giao tiếp trực tiếp qua TCP</p></div><span className={`status-chip ${s?.running ? 'live' : ''}`}><i className="dot"/>{s?.status === 'DEGRADED' ? 'THIẾU NODE' : s?.running ? 'ĐANG CHẠY' : 'CHƯA KHỞI ĐỘNG'}</span></div>
            {s && <div className="session-info"><span>Phiên <b className="mono">{s.session_id}</b> · {s.member_count} node</span><span title={s.config_path}>Cấu hình: {s.config_path?.split(/[\\/]/).pop() ?? '—'}</span></div>}
            <Network nodes={nodes} selected={selected} onSelect={setSelected} events={events}/>
            <div className="state-legend"><span><i className="dot gray"/> RELEASED <em>Thả</em></span><span><i className="dot amber"/> WANTED <em>Muốn</em></span><span><i className="dot mint"/> HELD <em>Giữ</em></span><span className="legend-note"><Activity size={12}/> Animation từ sự kiện quan sát</span></div>
          </section>

          <section className="panel control-panel"><div className="panel-heading"><div><h2><Sliders/> Điều khiển mô phỏng</h2><p>Thực nghiệm và quan sát thuật toán</p></div></div>
            <div className="control-body">
              <div className="lifecycle-actions"><button className="button start-button" disabled={busy || !connected || !!s?.running} onClick={() => action(() => call('simulation/start'))}><Play size={14} fill="currentColor"/> Khởi động</button><button className="button stop-button" disabled={busy || !connected || !s?.running || external} onClick={() => action(() => call('simulation/stop'))}><Square size={12} fill="currentColor"/> Dừng</button><button className="icon-button" aria-label="Reset toàn bộ phiên" title="Reset toàn bộ phiên" disabled={busy || !connected || external} onClick={() => action(() => call('simulation/reset'))}><RotateCcw size={16}/></button></div>
              <div className="control-divider"/>
              <div className="field-label">CHẾ ĐỘ THỰC THI <span>01</span></div>
              <div className="segmented"><button className={automatic ? 'selected' : ''} onClick={() => setAutomatic(true)}><Zap size={13}/> Tự động</button><button className={!automatic ? 'selected' : ''} onClick={() => setAutomatic(false)}><UnlockKeyhole size={13}/> Thủ công</button></div>
              <label className="duration-field"><span>Thời gian giữ vùng tới hạn</span><span className="duration-input"><input aria-label="Thời gian giữ vùng tới hạn (giây)" type="number" min="0.05" max="120" step="0.5" disabled={!automatic} value={duration} onChange={e => setDuration(Math.min(120, Math.max(.05, Number(e.target.value) || .05)))}/><span>giây</span></span></label>
              <div className="control-divider"/>
              <div className="field-label">TIẾN TRÌNH ĐƯỢC CHỌN <span>02</span></div>
              <div className="node-picker">{nodes.map(n => <button key={n.id} className={selected === n.id ? 'selected' : ''} onClick={() => setSelected(n.id)}>P{n.id}</button>)}</div>
              <div className="selected-status"><span><i className={`dot ${!current.online ? 'gray' : current.state === 'HELD' ? 'mint' : current.state === 'WANTED' ? 'amber' : 'gray'}`}/> {current.online ? labels[current.state] : 'Offline'}</span><span className="mono">C = {current.clock}</span></div>
              <button className="button request-button" disabled={busy || !ready || !current.online || current.state !== 'RELEASED'} onClick={() => action(() => call(`nodes/${current.id}/request`, options))}><Send size={15}/> Yêu cầu vùng tới hạn <span>P{current.id}</span></button>
              <button className="button release-button" disabled={busy || !connected || !current.online || current.state !== 'HELD'} onClick={() => action(() => call(`nodes/${current.id}/release`))}><UnlockKeyhole size={14}/> Giải phóng vùng tới hạn</button>
              <div className="control-divider"/>
              <div className="concurrent-heading"><span>Thử yêu cầu đồng thời</span><select aria-label="Nhóm yêu cầu đồng thời" value={group} onChange={e => setGroup(e.target.value)}><option value="pair">P1 + P2</option><option value="all">Tất cả node</option></select></div>
              <button className="button concurrent-button" disabled={busy || !ready || !(group === 'pair' ? nodes.slice(0,2) : nodes).every(n => n.state === 'RELEASED')} onClick={() => action(concurrent)}><Layers3 size={14}/> Gửi yêu cầu đồng thời <ArrowUpRight size={14}/></button>
              <div className="control-note"><CircleHelp size={13}/><span>{automatic ? 'Node tự giải phóng sau thời gian đã chọn.' : 'Chọn node đang HELD và nhấn Giải phóng.'} Quyền được quyết định tại từng node.</span></div>
            </div>
          </section>
        </div>

        <div className="secondary-grid">
          <section className="panel clocks-panel"><div className="panel-heading"><div><h2><Clock3 size={17}/> Đồng hồ Lamport</h2><p>Cập nhật độc lập tại mỗi tiến trình</p></div><span className="formula mono">Cᵢ ← max(Cᵢ, T) + 1</span></div>
            <div className="table-scroll"><table className="clock-table"><thead><tr><th>TIẾN TRÌNH</th><th>ĐỒNG HỒ</th><th>TRẠNG THÁI</th><th>ƯU TIÊN (T, ID)</th><th>REPLY</th><th>HOÃN CHO</th></tr></thead><tbody>{nodes.map(n => <tr key={n.id} className={selected === n.id ? 'selected-row' : ''} onClick={() => setSelected(n.id)}><td><span className="table-node">P{n.id}</span></td><td className="mono clock-number">{String(n.clock).padStart(2,'0')}</td><td><span className={`state-badge ${n.online ? n.state.toLowerCase() : 'offline'}`}>{n.online ? n.state : 'OFFLINE'}</span></td><td className="mono">{n.request_timestamp === null ? <span className="muted">—</span> : `(${n.request_timestamp}, ${n.id})`}</td><td className="mono">{n.replies.length}<span className="muted">/{n.expected_replies}</span></td><td className="mono muted">{n.deferred.length ? n.deferred.map(d => `P${d.node_id}`).join(', ') : '—'}</td></tr>)}</tbody></table></div>
            <div className="clock-explanation"><Code2 size={14}/><span>{waiting.length ? <>Yêu cầu ưu tiên đang chờ: <b>P{waiting[0].id} ({waiting[0].request_timestamp}, {waiting[0].id})</b>. Vẫn cần đủ {waiting[0].expected_replies} REPLY để vào.</> : 'Sự kiện cục bộ / gửi: C + 1. Khi nhận: max(C, T) + 1. T yêu cầu giữ nguyên.'}</span></div>
          </section>

          <section className="panel safety-panel"><div className="safety-icon"><ShieldCheck size={24}/></div><div><span className="eyebrow">LOẠI TRỪ TƯƠNG HỖ</span><h3>{s?.safety === 'NO_VIOLATION_OBSERVED' ? 'Chưa quan sát vi phạm' : 'Chờ xác nhận quan sát'}</h3><p>Chỉ một tiến trình được giữ vùng tới hạn khi tất cả thành viên hoạt động đúng.</p></div><div className="safety-owner"><span>ĐANG GIỮ VÙNG TỚI HẠN</span><strong>{!s?.owners.length ? <><LockKeyhole size={14}/> Chưa có</> : s.owners.length === 1 ? <><LockKeyhole size={14}/> P{s.owners[0]}</> : 'Đang đồng bộ'}</strong></div><p className="safety-footnote">Snapshot bất đồng bộ không chứng minh an toàn. Audit trong kiểm thử kiểm tra các khoảng HELD độc lập.</p></section>
        </div>

        <section className="panel events-panel"><div className="panel-heading"><div><h2><Terminal size={17}/> Nhật ký sự kiện <span className="count-badge">{events.length}</span></h2><p>Thứ tự thu thập không nhất thiết là thứ tự nhân quả toàn cục.</p></div><div className="event-actions"><select aria-label="Lọc sự kiện theo node" value={nodeFilter} onChange={e => setNodeFilter(e.target.value)}><option value="ALL">Tất cả node</option>{nodes.map(n => <option key={n.id} value={n.id}>P{n.id}</option>)}</select><button className="icon-button" aria-label="Xuất nhật ký JSONL" title="Xuất nhật ký JSONL" onClick={exportEvents} disabled={!events.length}><Download size={15}/></button><button className="icon-button" aria-label="Xóa nhật ký hiển thị" title="Chỉ xóa nhật ký hiển thị" onClick={clear} disabled={!events.length}><Trash2 size={15}/></button></div></div>
          <div className="event-tabs">{[['ALL','Tất cả sự kiện'],['REQUEST','REQUEST'],['REPLY','REPLY'],['CS','Vùng tới hạn']].map(([value,label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label}</button>)}<span><i className="dot mint"/> LIVE STREAM</span></div>
          <div className="event-list" role="log" aria-label="Sự kiện phân tán">{!visibleEvents.length ? <div className="empty-events"><Terminal size={26}/><strong>Chờ những thông điệp đầu tiên</strong><p>Khởi động mô phỏng và gửi một yêu cầu để quan sát thuật toán.</p></div> : visibleEvents.map(e => <div className={`event-row ${e.type === 'NETWORK_ERROR' || e.type === 'WAIT_WARNING' ? 'warning-event' : ''}`} key={e.event_id}><span className="event-time mono" title={e.observed_at}>{localTime(e.observed_at ?? e.collected_at)}</span><span className="event-process mono">P{e.node_id}</span><span className={`event-type ${e.message?.type === 'REQUEST' ? 'amber-text' : e.message?.type === 'REPLY' || e.type.startsWith('CS_') ? 'mint-text' : ''}`}>{eventKind(e)}</span><div className="event-description"><span>{e.explanation}</span><small className="mono">#{e.collection_id} · {e.message ? `P${e.message.sender_id} → P${e.message.receiver_id} · ` : ''}{e.request_id ? `req ${e.request_id.slice(0,8)}` : e.event_id.slice(0,8)}</small></div><span className="event-clock mono">L {e.clock}</span></div>)}</div>
        </section>

        <section className="learn-strip"><div className="learn-symbol"><BookOpen size={20}/></div><div><h3>Không có bộ điều phối trung tâm. Chỉ có sự đồng thuận về quyền.</h3><p>Mỗi tiến trình tự quyết định bằng REQUEST, REPLY và cặp ưu tiên Lamport.</p></div><button onClick={() => setTab('theory')}>Khám phá cách hoạt động <ArrowUpRight size={15}/></button></section>
        </>}
        <footer><span><Layers3 size={13}/> DISTRIBUTED SYSTEMS LAB <span className="footer-sep">/</span> Ricart & Agrawala Simulator</span><span>Thiết kế để học. Xây dựng để kiểm chứng. <span className="footer-sep">·</span> 1981 → {new Date().getFullYear()}</span></footer>
      </main>
    </div>
  </div>
}

function Metric({icon, label, value, detail}: {icon: React.ReactNode; label:string; value:React.ReactNode; detail:React.ReactNode}) {
  return <div className="metric"><div className="metric-top"><span>{label}</span>{icon}</div><div className="metric-value mono">{value}</div><div className="metric-detail">{detail}</div></div>
}
function Sliders() {return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M4 7h16M4 17h16"/><rect x="7" y="4" width="4" height="6" rx="1" fill="#172126"/><rect x="14" y="14" width="4" height="6" rx="1" fill="#172126"/></svg>}

function Educational({tab, onBack}: {tab:string; onBack:()=>void}) {
  return <section className="panel education"><div className="education-header"><span className="eyebrow">TÀI LIỆU PHÒNG THỰC HÀNH</span><button className="button ghost" onClick={onBack}>← Trở lại mô phỏng</button></div>{tab === 'theory' ? <>
    <h2>Một vùng tới hạn. N quyết định độc lập.</h2><p className="education-lead">Ricart & Agrawala (1981) giải quyết loại trừ tương hỗ bằng quyền từ tất cả các tiến trình còn lại. Dashboard chỉ quan sát và chuyển lệnh của người dùng.</p>
    <div className="theory-grid"><article><span className="chapter">01 / TRẠNG THÁI</span><h3>RELEASED → WANTED → HELD</h3><p><b>Thả:</b> không tranh chấp, trả lời REQUEST ngay. <b>Muốn:</b> chờ quyền, so sánh ưu tiên. <b>Giữ:</b> trong vùng tới hạn, hoãn mọi REPLY mới. Khi rời HELD, gửi hết REPLY đã hoãn.</p></article><article><span className="chapter">02 / ĐỒNG HỒ</span><h3>Thời gian logic, không phải thời gian thực</h3><p>Sự kiện cục bộ và gửi thông điệp làm C tăng 1. Nhận thông điệp T cập nhật C = max(C, T) + 1. Timestamp yêu cầu được lưu cố định, khác timestamp của mỗi thông điệp gửi.</p></article><article><span className="chapter">03 / THỨ TỰ</span><h3>Cặp (timestamp, process_id)</h3><p>Cặp nhỏ hơn có ưu tiên. (7, 1) đứng trước (7, 2), và (6, 5) đứng trước cả hai. Khi WANTED, trả lời ngay cho yêu cầu có ưu tiên trước mình; nếu không thì hoãn. Ưu tiên nhỏ nhất vẫn cần đủ quyền.</p></article><article><span className="chapter">04 / QUYỀN TRUY CẬP</span><h3>Chờ đúng N − 1 REPLY</h3><p>REQUEST và REPLY đi trực tiếp qua TCP. Mỗi REPLY được đối chiếu request ID và sender ID. Quyền trùng, quyền cũ và thông điệp khác phiên không được cấp thêm lượt.</p></article><article><span className="chapter">05 / CHI PHÍ</span><h3>2(N − 1) thông điệp / lượt</h3><p>Với 5 tiến trình: 4 REQUEST + 4 REPLY = 8 thông điệp cho mỗi lượt thành công, không tính management, ACK TCP ứng dụng hoặc giám sát. 5 lượt hoàn tất cần 40 thông điệp trong hệ khỏe mạnh.</p></article><article><span className="chapter">06 / GIỚI HẠN</span><h3>Một node lỗi có thể chặn toàn hệ</h3><p>Thuật toán giả định membership cố định và truyền tin tin cậy. Node mất kết nối có thể khiến WANTED chờ vô hạn. Timeout chỉ cảnh báo, không tự cấp quyền. Phục hồi lỗi và thay đổi membership nằm ngoài MVP.</p></article></div>
    <div className="worked-example"><h3>Ví dụ: P1 và P2 cùng yêu cầu ở T = 1</h3><ol><li>P1 lưu (1, 1), P2 lưu (1, 2); cả hai gửi REQUEST cho các peer.</li><li>P3 đang RELEASED nên gửi REPLY cho cả hai.</li><li>P2 trả lời P1 vì (1, 1) nhỏ hơn (1, 2). P1 hoãn REPLY cho P2.</li><li>P1 đủ 2 REPLY và vào HELD. P2 tiếp tục WANTED.</li><li>P1 rời vùng tới hạn, gửi REPLY đã hoãn. P2 đủ quyền và vào HELD.</li></ol></div>
  </> : <><h2>Kịch bản demo cho nhóm 5 thành viên.</h2><p className="education-lead">Chạy các thí nghiệm trực tiếp, đối chiếu trạng thái, đồng hồ và nhật ký node. Mỗi phần khoảng 2 phút.</p><div className="demo-steps">{[
    ['01','Giới thiệu & lý thuyết','Thành viên 1','Mở phần Thuật toán. Trình bày ba trạng thái, cặp ưu tiên, N − 1 quyền và giả định truyền tin tin cậy.'],
    ['02','Mạng phân tán','Thành viên 2','Chỉ ra năm PID khác nhau trong GET /api/nodes. Các node nghe cổng 5001–5005, trao đổi JSON theo dòng qua TCP; backend không cấp quyền.'],
    ['03','Một yêu cầu & hoãn REPLY','Thành viên 3','Chọn Thủ công, P1 → Yêu cầu. Đợi HELD, gửi yêu cầu P2. Quan sát WANTED và HOÃN tại P1. Giải phóng P1 để P2 vào, rồi giải phóng P2.'],
    ['04','Năm tiến trình cạnh tranh','Thành viên 4','Chọn Tự động, 3 giây, Tất cả node → Gửi yêu cầu đồng thời. Theo dõi ưu tiên, REPLY, đồng hồ và từng lượt HELD. Xuất nhật ký JSONL.'],
    ['05','Kiểm thử & giới hạn','Thành viên 5','Trình bày pytest, audit từng node và 60 lượt stress. Minh họa node lỗi bằng dừng một PID ở terminal: peer còn lại chờ quyền, không tự vào HELD. Reset toàn bộ sau demo lỗi.'],
  ].map(([number,title,member,description]) => <article key={number}><span className="step-number mono">{number}</span><div><span className="chapter">{member}</span><h3>{title}</h3><p>{description}</p></div></article>)}</div><div className="worked-example"><h3>Câu hỏi thường gặp</h3><p><b>Backend có giữ khóa không?</b> Không. Mỗi node đếm quyền và tự chuyển sang HELD.</p><p><b>Tại sao không bỏ qua node lỗi?</b> Bỏ qua quyền sẽ phá vỡ giả định an toàn. Cần cơ chế membership / phục hồi khác ngoài thuật toán gốc.</p><p><b>Đồng hồ nhỏ hơn luôn vào trước?</b> Cặp ưu tiên giải quyết các yêu cầu cạnh tranh đã biết; không có thứ tự toàn cục cho các yêu cầu không liên quan.</p><p><b>LAN đã kiểm chứng chưa?</b> Có cấu hình và hướng dẫn LAN; cần chạy thực tế trên nhiều máy để xác nhận môi trường cụ thể.</p></div></>}
  </section>
}
