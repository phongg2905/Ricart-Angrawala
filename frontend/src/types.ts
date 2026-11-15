export type NodeState = 'RELEASED' | 'WANTED' | 'HELD'
export interface ProcessNode {
  id: number; state: NodeState; clock: number; online: boolean; pid?: number
  request_id: string | null; request_timestamp: number | null
  replies: number[]; expected_replies: number; deferred: {node_id: number; request_id: string}[]
  completed: number; sent: {REQUEST: number; REPLY: number}; network_errors: Record<string, string>
}
export interface LabEvent {
  collection_id: number; event_id: string; node_id: number; type: string; clock: number
  request_id?: string; explanation: string; observed_at?: string; collected_at: string
  message?: {type: 'REQUEST' | 'REPLY'; sender_id: number; receiver_id: number; timestamp: number; request_timestamp?: number}
}
export interface Snapshot {
  epoch: string; running: boolean; mode: 'local' | 'external'; status: string
  nodes: ProcessNode[]; active_nodes: number; member_count: number
  owners: number[]; requests: number; replies: number; completed: number
  safety: string; safety_note: string; error: string | null; events?: LabEvent[]
}
