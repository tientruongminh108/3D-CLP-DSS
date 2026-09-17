import { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'
import type { RunResult, PlacedBox, Container, LayerBox } from '../types/api'
import { UnplacedCartons } from './UnplacedCartons'

interface LoadingPlanViewerProps {
  result: RunResult
  onNewRun: () => void
}

const COLORS: Record<number, string> = {
  1: '#3b82f6',
  2: '#ef4444',
  3: '#22c55e',
  4: '#f59e0b',
  5: '#8b5cf6',
  6: '#ec4899',
  7: '#06b6d4',
  8: '#84cc16',
}

/**
 * Coordinate System Mapping (Logistics → Three.js):
 *
 * Logistics:
 *   X ∈ [0, L]  – Length along container from door to back wall
 *   Y ∈ [0, W]  – Width from left wall to right wall
 *   Z ∈ [0, H]  – Height above floor to ceiling
 *
 * Three.js:
 *   X_three  – Horizontal axis (left → right)     ← maps from logistics X
 *   Y_three  – Vertical axis (up)                  ← maps from logistics Z
 *   Z_three  – Depth axis (towards camera)          ← maps from logistics Y
 *
 * Container wireframe:
 *   - Centered at [0, H/2, 0] with dimensions [L, H, W]
 *   - Floor rests at Y_three = 0
 *
 * Box mesh:
 *   - Position: [box.x + actualL/2 - L/2,  box.z + actualH/2,  box.y + actualW/2 - W/2]
 *   - Dimensions: [actualL, actualH, actualW]
 *
 * CoG marker:
 *   - Position: [cog_x - L/2, cog_z, cog_y - W/2]
 */

function ContainerWireframe({ container }: { container: Container }) {
  const L = container.internal_length_cm
  const W = container.internal_width_cm
  const H = container.internal_height_cm

  return (
    <group>
      {/* Container wireframe box – centered at [0, H/2, 0] so floor is at Y=0 */}
      <mesh position={[0, H / 2, 0]}>
        <boxGeometry args={[L, H, W]} />
        <meshBasicMaterial color="#64748b" wireframe transparent opacity={0.3} />
      </mesh>

      {/* Door indicator panel at X = -L/2 (the door end) */}
      <mesh position={[-L / 2, H / 2, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[W, H]} />
        <meshBasicMaterial color="#3b82f6" transparent opacity={0.08} side={2} />
      </mesh>
      <Html position={[-L / 2 - 10, H + 15, 0]} center>
        <div style={{ fontSize: 11, color: '#3b82f6', fontWeight: 600, whiteSpace: 'nowrap' }}>
          🚪 DOOR
        </div>
      </Html>

      {/* Container type label */}
      <Html position={[0, H + 15, 0]} center>
        <div style={{ fontSize: 12, color: '#64748b', fontWeight: 500 }}>
          {container.container_type}
        </div>
      </Html>
    </group>
  )
}

function BoxMesh({ box, containerL, containerW, onClick, isSelected }: {
  box: PlacedBox
  containerL: number
  containerW: number
  onClick: () => void
  isSelected: boolean
}) {
  const color = COLORS[box.customer_sequence % 8 || 8] || '#94a3b8'

  // Logistics → Three.js coordinate transform
  const posX = box.x + box.actual_length / 2 - containerL / 2
  const posY = box.z + box.actual_height / 2  // logistics Z → Three.js Y (up)
  const posZ = box.y + box.actual_width / 2 - containerW / 2  // logistics Y → Three.js Z (depth)

  return (
    <mesh
      position={[posX, posY, posZ]}
      onClick={(e) => { e.stopPropagation(); onClick() }}
    >
      <boxGeometry args={[box.actual_length, box.actual_height, box.actual_width]} />
      <meshStandardMaterial
        color={isSelected ? '#f59e0b' : color}
        transparent
        opacity={isSelected ? 0.9 : 0.85}
        metalness={0.1}
        roughness={0.8}
      />
    </mesh>
  )
}

function CogMarker({ metrics, containerL, containerW }: {
  metrics: RunResult['metrics']
  containerL: number
  containerW: number
}) {
  // CoG position: logistics → Three.js
  const cogX = metrics.cog_x - containerL / 2
  const cogY = metrics.cog_z  // logistics Z → Three.js Y
  const cogZ = metrics.cog_y - containerW / 2  // logistics Y → Three.js Z

  return (
    <group position={[cogX, cogY, cogZ]}>
      {/* Sphere marker */}
      <mesh>
        <sphereGeometry args={[8, 16, 16]} />
        <meshStandardMaterial color="#ef4444" transparent opacity={0.7} emissive="#ef4444" emissiveIntensity={0.3} />
      </mesh>
      {/* Crosshair lines */}
      {[
        { start: [-15, 0, 0], end: [15, 0, 0] },
        { start: [0, -15, 0], end: [0, 15, 0] },
        { start: [0, 0, -15], end: [0, 0, 15] },
      ].map((line, i) => (
        <line key={i}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              count={2}
              array={new Float32Array([...line.start, ...line.end])}
              itemSize={3}
            />
          </bufferGeometry>
          <lineBasicMaterial color="#ef4444" linewidth={2} />
        </line>
      ))}
      <Html center distanceFactor={400}>
        <div style={{
          fontSize: 10,
          color: '#ef4444',
          fontWeight: 600,
          background: 'rgba(255,255,255,0.85)',
          padding: '1px 4px',
          borderRadius: 3,
          whiteSpace: 'nowrap',
        }}>
          CoG
        </div>
      </Html>
    </group>
  )
}

function Scene({ placedBoxes, container, metrics, selectedBoxId, onBoxClick }: {
  placedBoxes: PlacedBox[]
  container: Container
  metrics: RunResult['metrics']
  selectedBoxId: string | null
  onBoxClick: (box: PlacedBox) => void
}) {
  const L = container.internal_length_cm
  const W = container.internal_width_cm
  const H = container.internal_height_cm

  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight position={[L, H * 2, W]} intensity={1} />
      <directionalLight position={[-L, H, -W / 2]} intensity={0.5} />

      <ContainerWireframe container={container} />

      {placedBoxes.map((box) => (
        <BoxMesh
          key={box.box_id}
          box={box}
          containerL={L}
          containerW={W}
          isSelected={box.box_id === selectedBoxId}
          onClick={() => onBoxClick(box)}
        />
      ))}

      <CogMarker metrics={metrics} containerL={L} containerW={W} />

      <gridHelper args={[Math.max(L, W) * 1.2, 40, '#cbd5e1', '#e2e8f0']} />
    </>
  )
}

function OverviewTab({ result, selectedBoxId, onBoxClick }: {
  result: RunResult
  selectedBoxId: string | null
  onBoxClick: (box: PlacedBox) => void
}) {
  const L = result.container.internal_length_cm
  const W = result.container.internal_width_cm
  const H = result.container.internal_height_cm

  // Camera positioned for a nice isometric-ish view
  const camDist = Math.max(L, W, H)
  const cameraPos: [number, number, number] = [L * 0.9, H * 1.8, W * 1.8]
  const controlsTarget: [number, number, number] = [0, H / 2, 0]

  return (
    <Canvas
      camera={{ position: cameraPos, fov: 50, near: 1, far: camDist * 10 }}
      style={{ width: '100%', height: '100%' }}
      onCreated={({ gl }) => { gl.setClearColor('#f8fafc', 1) }}
    >
      <Scene
        placedBoxes={result.placed_boxes}
        container={result.container}
        metrics={result.metrics}
        selectedBoxId={selectedBoxId}
        onBoxClick={onBoxClick}
      />
      <OrbitControls target={controlsTarget} enableDamping dampingFactor={0.12} />
    </Canvas>
  )
}

function LayerWalkthroughTab({ result, selectedLayer, onLayerChange }: {
  result: RunResult
  selectedLayer: number
  onLayerChange: (layer: number) => void
}) {
  const layer = result.layers[selectedLayer]
  if (!layer) return <div className="flex items-center justify-center h-full text-muted">No layer data</div>

  const L = result.container.internal_length_cm
  const W = result.container.internal_width_cm
  const H = result.container.internal_height_cm

  const cameraPos: [number, number, number] = [L * 0.9, H * 1.8, W * 1.8]
  const controlsTarget: [number, number, number] = [0, H / 2, 0]

  return (
    <div className="h-full flex flex-col">
      <div className="layer-controls">
        <label className="text-sm text-muted">Layer {selectedLayer + 1} / {result.layers.length}</label>
        <input
          type="range"
          className="layer-slider"
          min={0}
          max={result.layers.length - 1}
          value={selectedLayer}
          onChange={(e) => onLayerChange(parseInt(e.target.value, 10))}
        />
        <span className="layer-info">
          Z: {layer.z_min.toFixed(0)} - {layer.z_max.toFixed(0)} cm • {layer.boxes.length} boxes
        </span>
      </div>
      <div className="flex-1">
        <Canvas
          camera={{ position: cameraPos, fov: 50, near: 1, far: Math.max(L, W, H) * 10 }}
          style={{ width: '100%', height: '100%' }}
          onCreated={({ gl }) => { gl.setClearColor('#f8fafc', 1) }}
        >
          <ambientLight intensity={0.8} />
          <directionalLight position={[L, H * 2, W]} intensity={1} />

          <ContainerWireframe container={result.container} />

          {layer.boxes.map((box: LayerBox) => {
            // Same logistics → Three.js transform for layer boxes
            const posX = box.x + box.length / 2 - L / 2
            const posY = box.z + box.height / 2  // logistics Z → Three.js Y
            const posZ = box.y + box.width / 2 - W / 2  // logistics Y → Three.js Z

            return (
              <mesh key={box.box_id} position={[posX, posY, posZ]}>
                <boxGeometry args={[box.length, box.height, box.width]} />
                <meshStandardMaterial
                  color={COLORS[box.customer_sequence % 8 || 8] || '#94a3b8'}
                  transparent
                  opacity={0.85}
                  metalness={0.1}
                  roughness={0.8}
                />
              </mesh>
            )
          })}

          <gridHelper args={[Math.max(L, W) * 1.2, 40, '#cbd5e1', '#e2e8f0']} />
          <OrbitControls target={controlsTarget} enableDamping dampingFactor={0.12} />
        </Canvas>
      </div>
    </div>
  )
}

export function LoadingPlanViewer({ result, onNewRun }: LoadingPlanViewerProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'layers'>('overview')
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null)
  const [selectedLayer, setSelectedLayer] = useState(0)

  const metrics = result.metrics

  const handleBoxClick = (box: PlacedBox) => {
    setSelectedBoxId(box.box_id === selectedBoxId ? null : box.box_id)
  }

  return (
    <div className="viewer">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Loading Plan</h2>
        <button className="btn btn-primary" onClick={onNewRun}>
          New Run
        </button>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Fill Rate</div>
          <div className="stat-value">{(metrics.fill_rate * 100).toFixed(1)}<span className="stat-unit">%</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Weight Used</div>
          <div className="stat-value">{metrics.used_weight_kg.toLocaleString()}<span className="stat-unit"> kg</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Weight Utilization</div>
          <div className="stat-value">{(metrics.weight_utilization * 100).toFixed(1)}<span className="stat-unit">%</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Placed</div>
          <div className="stat-value">{metrics.placed_count}<span className="stat-unit"> / {metrics.total_cartons}</span></div>
        </div>
        {metrics.unplaced_count > 0 && (
          <div className="stat-card warning">
            <div className="stat-label">Unplaced</div>
            <div className="stat-value">{metrics.unplaced_count}<span className="stat-unit"> cartons</span></div>
          </div>
        )}
      </div>

      <div className="viewer-tabs">
        <button
          className={`viewer-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`viewer-tab ${activeTab === 'layers' ? 'active' : ''}`}
          onClick={() => setActiveTab('layers')}
        >
          Layer Walkthrough
        </button>
      </div>

      <div className="viewer-content">
        {activeTab === 'overview' && (
          <OverviewTab
            result={result}
            selectedBoxId={selectedBoxId}
            onBoxClick={handleBoxClick}
          />
        )}
        {activeTab === 'layers' && (
          <LayerWalkthroughTab
            result={result}
            selectedLayer={selectedLayer}
            onLayerChange={setSelectedLayer}
          />
        )}
      </div>

      {selectedBoxId && (
        <div className="mt-4 p-4 bg-background rounded-md border">
          <h3 className="font-medium mb-2">Box Details</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {(() => {
              const box = result.placed_boxes.find(b => b.box_id === selectedBoxId)
              if (!box) return null
              return (
                <>
                  <div><span className="text-muted">ID:</span> <span className="font-mono">{box.box_id}</span></div>
                  <div><span className="text-muted">Item:</span> {box.item_id}</div>
                  <div><span className="text-muted">PO:</span> {box.po_no}</div>
                  <div><span className="text-muted">Customer:</span> {box.customer_code || '—'}</div>
                  <div><span className="text-muted">Position:</span> ({box.x.toFixed(1)}, {box.y.toFixed(1)}, {box.z.toFixed(1)})</div>
                  <div><span className="text-muted">Dims:</span> {box.actual_length}×{box.actual_width}×{box.actual_height} cm</div>
                  <div><span className="text-muted">Weight:</span> {box.weight_kg} kg</div>
                  <div><span className="text-muted">Posture:</span> {box.posture}</div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      <UnplacedCartons unplacedCartons={result.unplaced_cartons} />
    </div>
  )
}