/**
 * Financial Intelligence's 3D layer, loaded lazily (see Scene3D.tsx) so three.js never ships with the app shell.
 *  - <SkylineScene>: the Overview hero. Every fiscal year is an ink column on a blueprint floor, height = the
 *    reported figure (one scale, zero at the floor, losses hang below it). Drag sideways to turn the turntable —
 *    it springs back when let go; tap a column to read that year.
 *  - <MarkScene>: the logo as an object for the brand page and 404. Flick it to spin, tap it and the columns jump.
 * Phones get a lower pixel ratio, no contact shadows and no parallax; every scene stops rendering off screen.
 */
import { ContactShadows, Edges, Grid } from '@react-three/drei'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type RefObject } from 'react'
import * as THREE from 'three'
import { BRAND, MARK_COLUMNS } from '../../lib/brandMark'
import { useOnScreen } from './webgl'

const INK = new THREE.Color('#2a2a34')
const BONE = new THREE.Color(BRAND.bone)
const DOWN = new THREE.Color(BRAND.down)

/** Unit box with its base on y = 0, so scale.y is the column height. */
function useColumnGeometry() {
  return useMemo(() => new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0), [])
}

type Turn = { yaw: number; vel: number; dragging: boolean; moved: number; lastX: number; px: number; py: number }

/** Pointer handling on the DOM wrapper: horizontal drags turn the scene; vertical scrolling still works (touch-action: pan-y). */
function useTurntable(onSpin?: (v: number) => void) {
  const turn = useRef<Turn>({ yaw: 0, vel: 0, dragging: false, moved: 0, lastX: 0, px: 0, py: 0 })
  const handlers = {
    onPointerDown: (e: ReactPointerEvent<HTMLDivElement>) => {
      const t = turn.current
      t.dragging = true; t.moved = 0; t.lastX = e.clientX; t.vel = 0
      e.currentTarget.setPointerCapture?.(e.pointerId)
    },
    onPointerMove: (e: ReactPointerEvent<HTMLDivElement>) => {
      const t = turn.current
      const r = e.currentTarget.getBoundingClientRect()
      t.px = ((e.clientX - r.left) / r.width) * 2 - 1
      t.py = ((e.clientY - r.top) / r.height) * 2 - 1
      if (!t.dragging) return
      const dx = e.clientX - t.lastX
      t.lastX = e.clientX
      t.moved += Math.abs(dx)
      const d = (dx / r.width) * Math.PI * 1.4
      t.yaw += d
      t.vel = d * 60
      onSpin?.(t.vel)
    },
    onPointerUp: (e: ReactPointerEvent<HTMLDivElement>) => {
      turn.current.dragging = false
      e.currentTarget.releasePointerCapture?.(e.pointerId)
    },
    onPointerLeave: () => { turn.current.px = 0; turn.current.py = 0 },
    onPointerCancel: () => { turn.current.dragging = false },
  }
  return { turn, handlers }
}

/* ───────────── Skyline ───────────── */

type ColumnProps = {
  i: number; x: number; width: number; target: number; neg: boolean; missing: boolean; selected: boolean
  calm: boolean; hovered: boolean; onPick: (i: number) => void; onHover: (i: number | null) => void; turn: RefObject<Turn>
}

function Column({ i, x, width, target, neg, missing, selected, calm, hovered, onPick, onHover, turn }: ColumnProps) {
  const geo = useColumnGeometry()
  const group = useRef<THREE.Group>(null)
  const mat = useRef<THREE.MeshStandardMaterial>(null)
  const s = useRef({ h: calm ? target : 0.001, v: 0, lift: 0, lv: 0, born: -1, sel: selected ? 1 : 0, pop: 0 })
  const wasSelected = useRef(selected)
  if (selected && !wasSelected.current) s.current.lv += 3.2 // a hop when a column becomes the selection
  wasSelected.current = selected

  useFrame(({ clock }, delta) => {
    const g = group.current
    if (!g) return
    const st = s.current
    const dt = Math.min(delta, 1 / 30)
    if (st.born < 0) st.born = clock.elapsedTime
    const started = calm || clock.elapsedTime - st.born > i * 0.07
    const goal = started ? Math.max(target, 0.02) : 0.001
    if (calm) st.h = goal
    else {
      st.v += ((goal - st.h) * 150 - st.v * 13) * dt
      st.h += st.v * dt
    }
    const liftGoal = hovered && !calm ? 0.14 : 0
    st.lv += ((liftGoal - st.lift) * 220 - st.lv * 16) * dt
    st.lift += st.lv * dt
    const h = Math.max(0.001, st.h)
    g.scale.set(width, h, width)
    g.position.set(x, (neg ? -h : 0) + (calm ? 0 : st.lift), 0)
    st.sel += ((selected ? 1 : 0) - st.sel) * Math.min(1, dt * 12)
    if (mat.current) {
      const base = neg ? DOWN : INK
      const hi = neg ? DOWN : BONE
      mat.current.color.copy(base).lerp(hi, st.sel)
      mat.current.opacity = missing ? 0.14 : 1
      mat.current.emissive.copy(neg ? DOWN : BONE).multiplyScalar(0.3 * st.sel)
    }
  })

  return (
    <group ref={group}>
      <mesh geometry={geo} castShadow
        onClick={(e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); if ((turn.current?.moved ?? 0) < 8) onPick(i) }}
        onPointerOver={(e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); onHover(i) }}
        onPointerOut={() => onHover(null)}>
        <meshStandardMaterial ref={mat} roughness={0.5} metalness={0.05} transparent={missing} polygonOffset polygonOffsetFactor={1} polygonOffsetUnits={1} />
        <Edges threshold={15} color={selected ? '#0B0B0D' : '#F3F1EC'} transparent opacity={selected ? 0.9 : 0.55} />
      </mesh>
    </group>
  )
}

export function SkylineScene({ values, selected, onPick, label, compact, calm }: {
  values: (number | null)[]; selected: number; onPick: (i: number) => void; label: string; compact: boolean; calm: boolean
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const visible = useOnScreen(wrap)
  const { turn, handlers } = useTurntable()
  const [hovered, setHovered] = useState<number | null>(null)
  const present = values.filter((v): v is number => v !== null)
  const maxAbs = Math.max(1e-9, ...present.map(Math.abs))
  const n = values.length
  const spacing = 1.18
  const width = 0.82
  const HEIGHT = 3.3
  const hasNeg = present.some(v => v < 0)

  return (
    <div ref={wrap} className={hovered !== null ? 'sky-canvas hover' : 'sky-canvas'} {...handlers} role="img" aria-label={label}>
      <Canvas dpr={compact ? [1, 1.4] : [1, 2]} frameloop={visible ? 'always' : 'never'} shadows={false}
        camera={{ fov: 24, position: [0, 9, 15], near: 0.1, far: 120 }}
        gl={{ antialias: true, alpha: true, powerPreference: compact ? 'low-power' : 'high-performance' }}>
        <hemisphereLight args={['#ffffff', '#1a2bb8', 0.9]} />
        <ambientLight intensity={0.25} />
        <directionalLight position={[6, 10, 4]} intensity={2.6} />
        <directionalLight position={[-7, 4, -3]} intensity={0.6} color="#9fb0ff" />
        <RigGroup turn={turn} compact={compact} calm={calm} count={n} hasNeg={hasNeg}>
          {values.map((v, i) => (
            <Column key={i} i={i} x={(i - (n - 1) / 2) * spacing} width={width}
              target={v === null ? 0.02 : (Math.abs(v) / maxAbs) * HEIGHT} neg={v !== null && v < 0} missing={v === null}
              selected={i === selected} hovered={hovered === i} calm={calm} onPick={onPick} onHover={setHovered} turn={turn} />
          ))}
          <Grid position={[0, 0.001, 0]} args={[40, 40]} cellSize={0.59} cellThickness={0.6} sectionSize={2.36} sectionThickness={1}
            cellColor="#c9d2ff" sectionColor="#f3f1ec" fadeDistance={compact ? 16 : 22} fadeStrength={1.6} infiniteGrid={false} side={THREE.DoubleSide} />
          {!compact && <ContactShadows position={[0, 0.002, 0]} opacity={0.42} scale={Math.max(10, n * 1.6)} blur={2.6} far={4.5} resolution={512} color="#05060f" frames={calm ? 1 : Infinity} />}
        </RigGroup>
      </Canvas>
    </div>
  )
}

/** Rotating root: everything inside turns with the turntable. */
function RigGroup({ turn, compact, calm, count, hasNeg, children }: {
  turn: RefObject<Turn>; compact: boolean; calm: boolean; count: number; hasNeg: boolean; children: React.ReactNode
}) {
  const g = useRef<THREE.Group>(null)
  const { camera, size } = useThree()
  const spring = useRef(0)
  useFrame(({ clock }, delta) => {
    const t = turn.current
    if (!t || !g.current) return
    const dt = Math.min(delta, 1 / 30)
    if (!t.dragging) {
      spring.current += (-t.yaw * 55 - spring.current * 6.5) * dt
      t.yaw += spring.current * dt
    } else spring.current = 0
    const idle = calm ? 0 : Math.sin(clock.elapsedTime * 0.45) * 0.07
    g.current.rotation.y = -0.36 + t.yaw + idle
    g.current.position.y = hasNeg ? 0.9 : 0
    const aspect = size.width / Math.max(1, size.height)
    const span = Math.max(4.8, count * 1.18 + 0.6)
    const dist = Math.max(11, (span / Math.min(aspect, 2.2)) * 2.15 + 5)
    const px = compact || calm ? 0 : t.px * 0.9
    const py = compact || calm ? 0 : -t.py * 0.6
    const want = new THREE.Vector3(px, dist * 0.5 + py, dist)
    if (calm) camera.position.copy(want)
    else camera.position.lerp(want, Math.min(1, dt * 4))
    camera.lookAt(0, 1.25 + (hasNeg ? 0.4 : 0), 0)
  })
  return <group ref={g}>{children}</group>
}

/* ───────────── the mark as an object ───────────── */

function MarkColumns({ calm, kick, spin }: { calm: boolean; kick: RefObject<number>; spin: RefObject<Turn> }) {
  const geo = useColumnGeometry()
  const root = useRef<THREE.Group>(null)
  const cols = useRef<(THREE.Group | null)[]>([])
  const st = useRef(MARK_COLUMNS.map(() => ({ y: 0, v: 0 })))
  const seenKick = useRef(0)
  const vel = useRef(calm ? 0 : 0.6)
  useFrame(({ clock }, delta) => {
    const dt = Math.min(delta, 1 / 30)
    const t = spin.current
    if (!root.current || !t) return
    if (kick.current !== seenKick.current) {
      seenKick.current = kick.current ?? 0
      st.current.forEach((c, i) => { c.v += 7 + i * 1.6 })
    }
    if (t.dragging) vel.current = t.vel
    else {
      // flick inertia, settling back to a slow idle spin
      const idle = calm ? 0 : 0.5
      vel.current += (idle - vel.current) * Math.min(1, dt * 1.6)
      root.current.rotation.y += vel.current * dt
    }
    if (t.dragging) { root.current.rotation.y += t.yaw; t.yaw = 0 }
    st.current.forEach((c, i) => {
      c.v += (-c.y * 160 - c.v * 9) * dt
      c.y += c.v * dt
      const g = cols.current[i]
      if (g) g.position.y = Math.max(-0.2, c.y)
    })
    root.current.position.y = calm ? 0 : Math.sin(clock.elapsedTime * 1.2) * 0.06
  })
  // centre the mark on the origin
  const cx = (MARK_COLUMNS[0].x + MARK_COLUMNS[2].x + 1) / 2
  return (
    <group ref={root}>
      {MARK_COLUMNS.map((c, i) => (
        <group key={i} ref={el => { cols.current[i] = el }}>
          <mesh geometry={geo} position={[c.x + 0.5 - cx, -1.45, c.y + 0.5 - 0.5]} scale={[1, c.h, 1]}>
            <meshStandardMaterial color={c.tone === 'cobalt' ? BRAND.cobalt : BRAND.bone} roughness={0.38} metalness={0.12} polygonOffset polygonOffsetFactor={1} polygonOffsetUnits={1} />
            <Edges threshold={15} color="#0B0B0D" />
          </mesh>
        </group>
      ))}
    </group>
  )
}

export function MarkScene({ compact, calm, className = '' }: { compact: boolean; calm: boolean; className?: string }) {
  const wrap = useRef<HTMLDivElement>(null)
  const visible = useOnScreen(wrap)
  const { turn, handlers } = useTurntable()
  const kick = useRef(0)
  return (
    <div ref={wrap} className={`mark-canvas ${className}`} {...handlers}
      onClick={() => { if ((turn.current.moved ?? 0) < 8) kick.current += 1 }}
      role="img" aria-label="The Financial Intelligence mark in 3D — flick it to spin, tap it to make the columns jump">
      <Canvas dpr={compact ? [1, 1.4] : [1, 2]} frameloop={visible ? 'always' : 'never'}
        camera={{ fov: 28, position: [7.2, 6.2, 7.2], near: 0.1, far: 60 }} gl={{ antialias: true, alpha: true }}
        onCreated={({ camera }) => camera.lookAt(0, 0, 0)}>
        <ambientLight intensity={0.8} />
        <directionalLight position={[3, 8, 5]} intensity={2} />
        <directionalLight position={[-6, 2, -4]} intensity={0.5} color="#9fb0ff" />
        <MarkColumns calm={calm} kick={kick} spin={turn} />
        {!compact && <ContactShadows position={[0, -1.5, 0]} opacity={0.45} scale={9} blur={2.4} far={3} resolution={256} color="#05060f" frames={calm ? 1 : Infinity} />}
      </Canvas>
    </div>
  )
}

