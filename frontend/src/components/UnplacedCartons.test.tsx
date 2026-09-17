import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { RunWizard } from './RunWizard'
import { useToastStore } from './Toast'
import { useWizardStore } from '../hooks/useRunWizard'
import { packingListApi, containerApi, runApi } from '../services/api'

const renderWithRouter = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {ui}
    </BrowserRouter>
  )
}

describe('Unplaced Cartons Result State (Section 6.3 - FE-13 to FE-16)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useToastStore.getState().toasts = []
      useWizardStore.getState().reset()
    })
    packingListApi.list = vi.fn().mockResolvedValue([
      { id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0, created_at: '', updated_at: '' }
    ])
  })

  it('FE-13: Zero unplaced shows success state', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0,
      rows: [{ item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, description: 'Test Item', qty_pcs: 10, qty_cartons: 10 }],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])
    runApi.createQuick = vi.fn().mockResolvedValue({
      run_id: 'test-run-1',
      status: 'completed',
      container: { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' },
      metrics: { placed_count: 10, unplaced_count: 0, total_cartons: 10, fill_rate: 0.85, used_weight_kg: 10000, max_weight_kg: 28000, weight_utilization: 35.7, cog_x: 601.6, cog_y: 117.6, cog_z: 135.0, cog_deviation_xy: 0, cog_deviation_z: 0 },
      placed_boxes: [{ box_id: 'BOX-1', item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, customer_sequence: 1, x: 0, y: 0, z: 0, length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 1000, this_way_up: true, stacking_group: 1, max_load_bearing_kg: 1000, permitted_postures: [1], inflated_length: 102, inflated_width: 52, inflated_height: 40, posture: 1, actual_length: 100, actual_width: 50, actual_height: 40 }],
      unplaced_cartons: [],
      layers: [],
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    })

    renderWithRouter(<RunWizard />)

    const plSelect = screen.getByRole('combobox', { name: /packing list/i })
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /test pl/i })).toBeInTheDocument()
    })
    fireEvent.change(plSelect, { target: { value: '1' } })

    await waitFor(() => {
      const containerSelect = screen.getByRole('combobox', { name: /container/i })
      fireEvent.change(containerSelect, { target: { value: '1' } })
    })

    const runButton = screen.getByRole('button', { name: /execute loading plan/i })
    fireEvent.click(runButton)

    await waitFor(() => {
      expect(screen.getByText(/loading plan result/i)).toBeInTheDocument()
    })

    const statTiles = screen.getAllByText(/cartons placed|fill rate|weight utilization/i)
    expect(statTiles.length).toBeGreaterThan(0)
  })

  it('FE-14: Unplaced no_space shows grouped guidance', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'FCL', customer_count: 0,
      rows: [{ item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, description: 'Test Item', qty_pcs: 10, qty_cartons: 10 }],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])
    runApi.createQuick = vi.fn().mockResolvedValue({
      run_id: 'test-run-2',
      status: 'completed',
      container: { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' },
      metrics: { placed_count: 8, unplaced_count: 2, total_cartons: 10, fill_rate: 0.75, used_weight_kg: 8000, max_weight_kg: 28000, weight_utilization: 28.6, cog_x: 601.6, cog_y: 117.6, cog_z: 135.0, cog_deviation_xy: 0, cog_deviation_z: 0 },
      placed_boxes: [],
      unplaced_cartons: [
        { box_id: 'UNPLACED-1', item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, customer_sequence: 1, reason: 'no_space', length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 1000 },
        { box_id: 'UNPLACED-2', item_id: 'ITEM-1', po_no: 'PO-1', customer_code: null, customer_sequence: 2, reason: 'no_space', length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 1000 },
      ],
      layers: [],
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    })

    renderWithRouter(<RunWizard />)

    const plSelect = screen.getByRole('combobox', { name: /packing list/i })
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /test pl/i })).toBeInTheDocument()
    })
    fireEvent.change(plSelect, { target: { value: '1' } })

    await waitFor(() => {
      const containerSelect = screen.getByRole('combobox', { name: /container/i })
      fireEvent.change(containerSelect, { target: { value: '1' } })
    })

    const runButton = screen.getByRole('button', { name: /execute loading plan/i })
    fireEvent.click(runButton)

    await waitFor(() => {
      expect(screen.getByText(/loading plan result/i)).toBeInTheDocument()
    })

    expect(screen.getAllByText(/no space/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/container.*size|split.*shipment/i)).toBeInTheDocument()
    expect(screen.queryByText(/delivery order/i)).not.toBeInTheDocument()
  })

  it('FE-15: Unplaced lifo_blocked shows grouped guidance', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'LCL', customer_count: 2,
      rows: [
        { item_id: 'ITEM-1', po_no: 'PO-1', customer_code: 'CUST-A', description: 'Test Item', qty_pcs: 10, qty_cartons: 10 },
        { item_id: 'ITEM-2', po_no: 'PO-2', customer_code: 'CUST-B', description: 'Test Item', qty_pcs: 10, qty_cartons: 10 },
      ],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])
    runApi.createQuick = vi.fn().mockResolvedValue({
      run_id: 'test-run-3',
      status: 'completed',
      container: { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' },
      metrics: { placed_count: 8, unplaced_count: 2, total_cartons: 10, fill_rate: 0.75, used_weight_kg: 8000, max_weight_kg: 28000, weight_utilization: 28.6, cog_x: 601.6, cog_y: 117.6, cog_z: 135.0, cog_deviation_xy: 0, cog_deviation_z: 0 },
      placed_boxes: [],
      unplaced_cartons: [
        { box_id: 'UNPLACED-1', item_id: 'ITEM-1', po_no: 'PO-1', customer_code: 'CUST-A', customer_sequence: 1, reason: 'lifo_blocked', length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 1000 },
        { box_id: 'UNPLACED-2', item_id: 'ITEM-2', po_no: 'PO-2', customer_code: 'CUST-B', customer_sequence: 2, reason: 'lifo_blocked', length_cm: 80, width_cm: 60, height_cm: 50, weight_kg: 800 },
      ],
      layers: [],
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    })

    renderWithRouter(<RunWizard />)

    const plSelect = screen.getByRole('combobox', { name: /packing list/i })
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /test pl/i })).toBeInTheDocument()
    })
    fireEvent.change(plSelect, { target: { value: '1' } })

    await waitFor(() => {
      const containerSelect = screen.getByRole('combobox', { name: /container/i })
      fireEvent.change(containerSelect, { target: { value: '1' } })
    })

    const runButton = screen.getByRole('button', { name: /execute loading plan/i })
    fireEvent.click(runButton)

    await waitFor(() => {
      expect(screen.getByText(/loading plan result/i)).toBeInTheDocument()
    })

    expect(screen.getAllByText(/lifo.blocked/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/delivery order|consolidation/i)).toBeInTheDocument()
    expect(screen.queryByText(/bigger container/i)).not.toBeInTheDocument()
  })

  it('FE-16: Both reasons shown separately with correct total', async () => {
    packingListApi.get = vi.fn().mockResolvedValue({
      id: 1, name: 'Test PL', filename: 'test.csv', total_cartons: 10, total_weight_kg: 200, total_volume_cm3: 400000, shipment_type: 'LCL', customer_count: 2,
      rows: [
        { item_id: 'ITEM-1', po_no: 'PO-1', customer_code: 'CUST-A', description: 'Test Item', qty_pcs: 10, qty_cartons: 10 },
        { item_id: 'ITEM-2', po_no: 'PO-2', customer_code: 'CUST-B', description: 'Test Item', qty_pcs: 10, qty_cartons: 10 },
      ],
      created_at: '', updated_at: ''
    })
    containerApi.list = vi.fn().mockResolvedValue([
      { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' }
    ])
    runApi.createQuick = vi.fn().mockResolvedValue({
      run_id: 'test-run-4',
      status: 'completed',
      container: { id: 1, container_type: '40HC', internal_length_cm: 1203.2, internal_width_cm: 235.2, internal_height_cm: 270.0, max_weight_kg: 28000, created_at: '', updated_at: '' },
      metrics: { placed_count: 6, unplaced_count: 4, total_cartons: 10, fill_rate: 0.65, used_weight_kg: 6000, max_weight_kg: 28000, weight_utilization: 21.4, cog_x: 601.6, cog_y: 117.6, cog_z: 135.0, cog_deviation_xy: 0, cog_deviation_z: 0 },
      placed_boxes: [],
      unplaced_cartons: [
        { box_id: 'UNPLACED-1', item_id: 'ITEM-1', po_no: 'PO-1', customer_code: 'CUST-A', customer_sequence: 1, reason: 'no_space', length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 1000 },
        { box_id: 'UNPLACED-2', item_id: 'ITEM-2', po_no: 'PO-2', customer_code: 'CUST-B', customer_sequence: 2, reason: 'no_space', length_cm: 80, width_cm: 60, height_cm: 50, weight_kg: 800 },
        { box_id: 'UNPLACED-3', item_id: 'ITEM-3', po_no: 'PO-3', customer_code: 'CUST-A', customer_sequence: 3, reason: 'lifo_blocked', length_cm: 120, width_cm: 40, height_cm: 30, weight_kg: 1200 },
        { box_id: 'UNPLACED-4', item_id: 'ITEM-4', po_no: 'PO-4', customer_code: 'CUST-B', customer_sequence: 4, reason: 'lifo_blocked', length_cm: 90, width_cm: 70, height_cm: 60, weight_kg: 900 },
      ],
      layers: [],
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    })

    renderWithRouter(<RunWizard />)

    const plSelect = screen.getByRole('combobox', { name: /packing list/i })
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /test pl/i })).toBeInTheDocument()
    })
    fireEvent.change(plSelect, { target: { value: '1' } })

    await waitFor(() => {
      const containerSelect = screen.getByRole('combobox', { name: /container/i })
      fireEvent.change(containerSelect, { target: { value: '1' } })
    })

    const runButton = screen.getByRole('button', { name: /execute loading plan/i })
    fireEvent.click(runButton)

    await waitFor(() => {
      expect(screen.getByText(/loading plan result/i)).toBeInTheDocument()
    })

    expect(screen.getAllByText(/no space/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/lifo.blocked/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/4.*unplaced|unplaced.*4/i)).toBeInTheDocument()
  })
})