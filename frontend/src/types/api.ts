export enum Posture {
  LWH = 1,
  WLH = 2,
  HLW = 3,
  HWL = 4,
  LHW = 5,
  WHL = 6,
}

export enum ShipmentType {
  FCL = 'FCL',
  LCL = 'LCL',
}

export enum UnplacedReason {
  NO_SPACE = 'no_space',
  LIFO_BLOCKED = 'lifo_blocked',
}

export enum RunStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export interface Item {
  id: number
  item_id: string
  description: string
  length_cm: number
  width_cm: number
  height_cm: number
  weight_kg: number
  this_way_up: boolean
  created_at: string
  updated_at: string
}

export interface ItemCreate {
  item_id: string
  description: string
  length_cm: number
  width_cm: number
  height_cm: number
  weight_kg: number
  this_way_up: boolean
}

export interface ItemUpdate {
  description?: string
  length_cm?: number
  width_cm?: number
  height_cm?: number
  weight_kg?: number
  this_way_up?: boolean
}

export interface ContainerUpdate {
  container_type?: string
  internal_length_cm?: number
  internal_width_cm?: number
  internal_height_cm?: number
  max_weight_kg?: number
}

export interface Container {
  id: number
  container_type: string
  internal_length_cm: number
  internal_width_cm: number
  internal_height_cm: number
  max_weight_kg: number
  created_at: string
  updated_at: string
}

export interface ContainerCreate {
  container_type: string
  internal_length_cm: number
  internal_width_cm: number
  internal_height_cm: number
  max_weight_kg: number
}

export interface PackingListRow {
  item_id: string
  po_no: string
  customer_code?: string
  description?: string
  qty_pcs: number
  qty_cartons: number
}

export interface PackingListUpload {
  rows: PackingListRow[]
  filename?: string
}

export interface PackingListPreviewRow {
  item_id: string
  po_no: string
  customer_code?: string
  description: string
  qty_cartons: number
  length_cm: number
  width_cm: number
  height_cm: number
  weight_kg: number
  this_way_up: boolean
}

export interface PackingListPreview {
  rows: PackingListPreviewRow[]
  shipment_type: ShipmentType
  customer_count: number
  total_cartons: number
  total_weight_kg: number
  total_volume_cm3: number
}

export interface RunOptions {
  population_size?: number
  generations?: number
  tolerance_gap_cm?: number
}

export interface RunCreate {
  packing_list: PackingListUpload
  container_id: number
  options?: RunOptions
}

export interface RunCreateQuick {
  packing_list: PackingListUpload
  container_type: string
  options?: RunOptions
}

export interface Box {
  box_id: string
  item_id: string
  po_no: string
  customer_code?: string
  customer_sequence: number
  length_cm: number
  width_cm: number
  height_cm: number
  weight_kg: number
  this_way_up: boolean
  permitted_postures: Posture[]
  inflated_length: number
  inflated_width: number
  inflated_height: number
}

export interface PlacedBox extends Box {
  x: number
  y: number
  z: number
  posture: Posture
  actual_length: number
  actual_width: number
  actual_height: number
  step_index: number
  color?: string
  description?: string
}

export interface LoadMetrics {
  placed_count: number
  unplaced_count: number
  total_cartons: number
  fill_rate: number
  used_weight_kg: number
  max_weight_kg: number
  weight_utilization: number
  cog_x: number
  cog_y: number
  cog_z: number
  cog_deviation_xy: number
  cog_deviation_z: number
}

export interface UnplacedCarton {
  box_id: string
  item_id: string
  po_no: string
  customer_code?: string
  customer_sequence: number
  reason: UnplacedReason
  length_cm: number
  width_cm: number
  height_cm: number
  weight_kg: number
}

export interface RunResult {
  run_id: string
  status: RunStatus
  container: Container
  metrics: LoadMetrics
  placed_boxes: PlacedBox[]
  unplaced_cartons: UnplacedCarton[]
  layers: Layer[]
  created_at: string
  completed_at?: string
  error_message?: string
  options?: RunOptions
}

export interface Layer {
  x_min: number
  x_max: number
  boxes: LayerBox[]
}

export interface LayerBox {
  box_id: string
  item_id: string
  x: number
  y: number
  z: number
  length: number
  width: number
  height: number
  posture: Posture
  customer_sequence: number
  step_index?: number
  color?: string
}

export interface RunSummary {
  run_id: string
  container_type: string
  shipment_type: ShipmentType
  customer_count: number
  total_cartons: number
  placed_count: number
  unplaced_count: number
  fill_rate: number
  status: RunStatus
  created_at: string
  completed_at?: string
}

export interface ValidationError {
  field: string
  message: string
  row?: number
}

export interface ValidationResponse {
  valid: boolean
  errors: ValidationError[]
  preview?: PackingListPreview
}

export interface PackingListRow {
  item_id: string
  po_no: string
  customer_code?: string
  description?: string
  qty_pcs: number
  qty_cartons: number
}

export interface PackingListCreate {
  name: string
  filename?: string
  rows: PackingListRow[]
  total_cartons: number
  total_weight_kg: number
  total_volume_cm3: number
  shipment_type: ShipmentType
  customer_count: number
  preview?: PackingListPreview
}

export interface PackingListUpdate {
  name?: string
  rows?: PackingListRow[]
  total_cartons?: number
  total_weight_kg?: number
  total_volume_cm3?: number
  shipment_type?: ShipmentType
  customer_count?: number
}

export interface PackingListSummary {
  id: number
  name: string
  filename?: string
  total_cartons: number
  total_weight_kg: number
  total_volume_cm3: number
  shipment_type: ShipmentType
  customer_count: number
  created_at: string
  updated_at: string
}

export interface PackingList extends PackingListSummary {
  rows: PackingListRow[]
  preview?: PackingListPreview
}