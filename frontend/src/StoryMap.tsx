import type { FC } from 'react'

// ── Static story graph (mirrors story.json structure) ─────────────────────────

type NodeId = string

interface GraphNode {
  id: NodeId
  x: number
  y: number
  type: 'scene' | 'decision'
  label: string
  anchor: 'right' | 'left' | 'below' | 'above'
}

interface GraphEdge {
  from: NodeId
  to: NodeId
  trigger?: string  // emotion label shown on decision→branch edges
}

// Canvas: 252px wide (280px sidebar − 14px padding × 2)
// Horizontal centres: left=60, mid=126, right=196; branch2: 32,88,164,220; endings: 20,64,126,188,232
const NODES: GraphNode[] = [
  // ── Phase 1 linear ────────────────────────────────────────────────
  { id: 'opening',        x: 126, y: 20,  type: 'scene',    label: 'The Letter',     anchor: 'right' },
  { id: 'foyer',          x: 126, y: 52,  type: 'scene',    label: 'Grand Foyer',    anchor: 'right' },
  { id: 'sound_upstairs', x: 126, y: 84,  type: 'scene',    label: 'Upstairs',       anchor: 'right' },
  // ── Decision 1 ────────────────────────────────────────────────────
  { id: 'decision_1',     x: 126, y: 116, type: 'decision', label: 'BRANCH',         anchor: 'above' },
  // ── Branch 1 ──────────────────────────────────────────────────────
  { id: 'upstairs_door',  x: 58,  y: 154, type: 'scene',    label: 'Upstairs Door',  anchor: 'left' },
  { id: 'study_reveal',   x: 58,  y: 192, type: 'scene',    label: 'The Study',      anchor: 'left' },
  { id: 'figure_appears', x: 126, y: 154, type: 'scene',    label: 'Stranger',       anchor: 'right' },
  { id: 'hidden_room',    x: 126, y: 192, type: 'scene',    label: 'Hid. Room',      anchor: 'right' },
  { id: 'foyer_detail',   x: 196, y: 170, type: 'scene',    label: 'Clue',           anchor: 'right' },
  // ── Decision 2 ────────────────────────────────────────────────────
  { id: 'decision_2',     x: 126, y: 228, type: 'decision', label: 'BRANCH',         anchor: 'above' },
  // ── Branch 2 ──────────────────────────────────────────────────────
  { id: 'conspiracy_deep',    x: 30,  y: 264, type: 'scene', label: 'Conspiracy', anchor: 'below' },
  { id: 'twist_reveal',       x: 88,  y: 264, type: 'scene', label: 'Mirror',     anchor: 'below' },
  { id: 'dark_humor_beat',    x: 162, y: 264, type: 'scene', label: 'Dark Humor', anchor: 'below' },
  { id: 'narrator_explains',  x: 222, y: 264, type: 'scene', label: 'Backstory',  anchor: 'below' },
  // ── Decision 3 ────────────────────────────────────────────────────
  { id: 'decision_3',     x: 126, y: 302, type: 'decision', label: 'ENDING',         anchor: 'above' },
  // ── Endings ───────────────────────────────────────────────────────
  { id: 'ending_solve',        x: 20,  y: 345, type: 'scene', label: 'Solved',     anchor: 'below' },
  { id: 'ending_bittersweet',  x: 64,  y: 345, type: 'scene', label: 'Bitter',     anchor: 'below' },
  { id: 'ending_twist',        x: 126, y: 345, type: 'scene', label: 'Twist',      anchor: 'below' },
  { id: 'ending_humorous',     x: 188, y: 345, type: 'scene', label: 'Cat Wins',   anchor: 'below' },
  { id: 'ending_supernatural', x: 232, y: 345, type: 'scene', label: 'Haunted',    anchor: 'below' },
]

const EDGES: GraphEdge[] = [
  // Phase 1 linear
  { from: 'opening',        to: 'foyer' },
  { from: 'foyer',          to: 'sound_upstairs' },
  { from: 'sound_upstairs', to: 'decision_1' },
  // Decision 1 → branches (with emotion triggers)
  { from: 'decision_1', to: 'upstairs_door',  trigger: 'engaged' },
  { from: 'decision_1', to: 'figure_appears', trigger: 'bored'   },
  { from: 'decision_1', to: 'foyer_detail',   trigger: 'confused' },
  // Branch 1 paths
  { from: 'upstairs_door',  to: 'study_reveal' },
  { from: 'figure_appears', to: 'hidden_room' },
  { from: 'foyer_detail',   to: 'upstairs_door' },
  // Converge to decision_2
  { from: 'study_reveal', to: 'decision_2' },
  { from: 'hidden_room',  to: 'decision_2' },
  // Decision 2 → branches
  { from: 'decision_2', to: 'conspiracy_deep',   trigger: 'engaged' },
  { from: 'decision_2', to: 'twist_reveal',       trigger: 'bored'   },
  { from: 'decision_2', to: 'dark_humor_beat',    trigger: 'amused'  },
  { from: 'decision_2', to: 'narrator_explains',  trigger: 'confused' },
  // Converge to decision_3
  { from: 'conspiracy_deep',   to: 'decision_3' },
  { from: 'twist_reveal',      to: 'decision_3' },
  { from: 'dark_humor_beat',   to: 'decision_3' },
  { from: 'narrator_explains', to: 'decision_3' },
  // Decision 3 → endings
  { from: 'decision_3', to: 'ending_solve',        trigger: 'engaged'  },
  { from: 'decision_3', to: 'ending_bittersweet',  trigger: 'tense'    },
  { from: 'decision_3', to: 'ending_twist',        trigger: 'surprised' },
  { from: 'decision_3', to: 'ending_humorous',     trigger: 'amused'   },
  { from: 'decision_3', to: 'ending_supernatural', trigger: 'confused' },
]

// Which scenes are the first scene for each decision's branch paths
const DECISION_OUTPUTS: Record<string, string[]> = {
  decision_1: ['upstairs_door', 'figure_appears', 'foyer_detail'],
  decision_2: ['conspiracy_deep', 'twist_reveal', 'dark_humor_beat', 'narrator_explains'],
  decision_3: ['ending_solve', 'ending_bittersweet', 'ending_twist', 'ending_humorous', 'ending_supernatural'],
}

const EMOTION_COLORS: Record<string, string> = {
  engaged: '#2ecc71', bored: '#7f8c8d', confused: '#e67e22',
  amused: '#f1c40f', tense: '#e74c3c', surprised: '#9b59b6', neutral: '#95a5a6',
}

// ── Component ─────────────────────────────────────────────────────────────────

interface StoryMapProps {
  scenesPlayed: string[]
  currentEmotion: string | null
}

export const StoryMap: FC<StoryMapProps> = ({ scenesPlayed, currentEmotion }) => {
  const visited = new Set(scenesPlayed)
  const currentScene = scenesPlayed[scenesPlayed.length - 1] ?? null

  // Decision nodes are "visited" when any of their output scenes appear in the path
  function isNodeVisited(id: NodeId): boolean {
    if (id.startsWith('decision_')) {
      return (DECISION_OUTPUTS[id] ?? []).some(o => visited.has(o))
    }
    return visited.has(id)
  }

  // Edge is active if both endpoints are visited
  function isEdgeActive(fromId: NodeId, toId: NodeId): boolean {
    return isNodeVisited(fromId) && isNodeVisited(toId)
  }

  const nodeMap = new Map(NODES.map(n => [n.id, n]))
  const R = 5      // scene circle radius
  const D = 7      // decision diamond half-size

  return (
    <svg
      viewBox="0 0 252 372"
      width="100%"
      style={{ display: 'block', overflow: 'visible' }}
    >
      {/* ── Edges (drawn first, behind nodes) ── */}
      {EDGES.map((edge, i) => {
        const from = nodeMap.get(edge.from)!
        const to   = nodeMap.get(edge.to)!
        const active = isEdgeActive(edge.from, edge.to)

        // Midpoint for trigger label
        const mx = (from.x + to.x) / 2
        const my = (from.y + to.y) / 2

        return (
          <g key={i}>
            <line
              x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={active ? '#c9a84c' : '#1e1e2e'}
              strokeWidth={active ? 1.5 : 1}
              strokeOpacity={active ? 1 : 0.6}
            />
            {edge.trigger && active && (
              <text
                x={mx + 3} y={my}
                fontSize={5.5}
                fill={EMOTION_COLORS[edge.trigger] ?? '#6e5928'}
                fontFamily="'IBM Plex Mono', monospace"
                opacity={0.85}
              >
                {edge.trigger}
              </text>
            )}
          </g>
        )
      })}

      {/* ── Nodes ── */}
      {NODES.map(node => {
        const vis = isNodeVisited(node.id)
        const cur = node.id === currentScene
        const isDec = node.type === 'decision'

        const fillColor  = cur ? '#c0392b22' : vis ? '#c9a84c18' : '#13131f'
        const ringColor  = cur ? '#c0392b'   : vis ? '#c9a84c'   : '#2a2a3d'
        const labelColor = cur ? '#c0392b'   : vis ? '#c9a84c'   : '#3a3930'

        // Label coords
        let lx = node.x, ly = node.y, textAnchor = 'middle'
        if (node.anchor === 'right') { lx = node.x + R + 5; ly = node.y + 3.5; textAnchor = 'start' }
        else if (node.anchor === 'left') { lx = node.x - R - 5; ly = node.y + 3.5; textAnchor = 'end' }
        else if (node.anchor === 'below') { ly = node.y + R + 11 }
        else if (node.anchor === 'above') { ly = node.y - D - 5 }

        return (
          <g key={node.id}>
            {/* Pulse ring on current scene */}
            {cur && !isDec && (
              <circle cx={node.x} cy={node.y} r={R + 3} fill="none" stroke="#c0392b" strokeWidth={1} opacity={0.4}>
                <animate attributeName="r" values={`${R + 2};${R + 8};${R + 2}`} dur="2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
              </circle>
            )}

            {isDec ? (
              // Diamond for decision nodes
              <polygon
                points={`${node.x},${node.y - D} ${node.x + D},${node.y} ${node.x},${node.y + D} ${node.x - D},${node.y}`}
                fill={fillColor}
                stroke={ringColor}
                strokeWidth={vis ? 1.5 : 1}
              />
            ) : (
              // Circle for scene nodes
              <circle
                cx={node.x} cy={node.y} r={R}
                fill={fillColor}
                stroke={ringColor}
                strokeWidth={vis ? 1.5 : 1}
              />
            )}

            {/* Label */}
            <text
              x={lx} y={ly}
              fontSize={node.anchor === 'above' ? 7 : node.anchor === 'below' ? 6.5 : 7.5}
              fill={labelColor}
              textAnchor={textAnchor as 'start' | 'middle' | 'end'}
              fontFamily="'IBM Plex Mono', monospace"
              letterSpacing={node.anchor === 'above' ? '0.1em' : undefined}
            >
              {node.label}
            </text>
          </g>
        )
      })}

      {/* ── Current emotion indicator ── */}
      {currentEmotion && (
        <g>
          <text x={126} y={368} fontSize={7} textAnchor="middle"
            fill={EMOTION_COLORS[currentEmotion] ?? '#6e5928'}
            fontFamily="'IBM Plex Mono', monospace"
            opacity={0.8}
          >
            ● {currentEmotion}
          </text>
        </g>
      )}
    </svg>
  )
}
