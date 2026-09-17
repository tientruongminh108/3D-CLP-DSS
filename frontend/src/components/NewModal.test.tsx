import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { ItemMasterTable } from './ItemMasterTable'
import { ContainerTable } from './ContainerTable'
import { useToastStore } from './Toast'
import { itemApi, containerApi } from '../services/api'

const renderWithRouter = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {ui}
    </BrowserRouter>
  )
}

describe('+ New Modal (Section 6.4 - FE-17 to FE-19)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useToastStore.getState().toasts = []
    })
  })

  describe('Item Master + New Modal', () => {
    it('FE-17: + New modal opens with same fields as standalone editor', async () => {
      itemApi.list = vi.fn().mockResolvedValue([])
      itemApi.create = vi.fn().mockResolvedValue({
        id: 1, item_id: 'NEW-ITEM', description: 'New Item', length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 20,
        this_way_up: true, stacking_group: 1, max_load_bearing_kg: null, created_at: '', updated_at: ''
      })

      renderWithRouter(<ItemMasterTable />)

      const newButton = screen.getByRole('button', { name: /new item/i })
      fireEvent.click(newButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      expect(screen.getByLabelText(/item id \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/description \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/length \(cm\) \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/width \(cm\) \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/height \(cm\) \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/weight \(kg\) \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/this way up/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/stacking group \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/max load bearing \(kg\)/i)).toBeInTheDocument()
    })

    it('FE-18: Modal stays open on validation error', async () => {
      itemApi.list = vi.fn().mockResolvedValue([])
      itemApi.create = vi.fn().mockRejectedValue({
        response: { data: { detail: 'Invalid input' } }
      })

      renderWithRouter(<ItemMasterTable />)

      const newButton = screen.getByRole('button', { name: /new item/i })
      fireEvent.click(newButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      fireEvent.change(screen.getByLabelText(/length \(cm\) \*/i), { target: { value: '-10' } })
      fireEvent.change(screen.getByLabelText(/description \*/i), { target: { value: 'Test Item' } })
      fireEvent.change(screen.getByLabelText(/width \(cm\) \*/i), { target: { value: '50' } })
      fireEvent.change(screen.getByLabelText(/height \(cm\) \*/i), { target: { value: '40' } })
      fireEvent.change(screen.getByLabelText(/weight \(kg\) \*/i), { target: { value: '20' } })
      fireEvent.change(screen.getByLabelText(/item id \*/i), { target: { value: 'TEST-ITEM' } })

      const submitButton = screen.getByRole('button', { name: /create/i })
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      expect(screen.getByText(/length must be > 0/i)).toBeInTheDocument()
    })

    it('FE-19: Modal closes and new record selected on success', async () => {
      itemApi.list = vi.fn().mockResolvedValue([])
      itemApi.create = vi.fn().mockResolvedValueOnce({
        id: 1, item_id: 'NEW-ITEM', description: 'New Item', length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 20,
        this_way_up: true, stacking_group: 1, max_load_bearing_kg: null, created_at: '', updated_at: ''
      })
      itemApi.list = vi.fn().mockResolvedValueOnce([
        { id: 1, item_id: 'NEW-ITEM', description: 'New Item', length_cm: 100, width_cm: 50, height_cm: 40, weight_kg: 20,
          this_way_up: true, stacking_group: 1, max_load_bearing_kg: null, created_at: '', updated_at: '' }
      ])

      renderWithRouter(<ItemMasterTable />)

      const newButton = screen.getByRole('button', { name: /new item/i })
      fireEvent.click(newButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      fireEvent.change(screen.getByLabelText(/item id \*/i), { target: { value: 'NEW-ITEM' } })
      fireEvent.change(screen.getByLabelText(/description \*/i), { target: { value: 'New Item' } })
      fireEvent.change(screen.getByLabelText(/length \(cm\) \*/i), { target: { value: '100' } })
      fireEvent.change(screen.getByLabelText(/width \(cm\) \*/i), { target: { value: '50' } })
      fireEvent.change(screen.getByLabelText(/height \(cm\) \*/i), { target: { value: '40' } })
      fireEvent.change(screen.getByLabelText(/weight \(kg\) \*/i), { target: { value: '20' } })

      const submitButton = screen.getByRole('button', { name: /create/i })
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })

      await waitFor(() => {
        expect(screen.getByText('NEW-ITEM')).toBeInTheDocument()
      })
    })
  })

  describe('Container + New Modal', () => {
    it('FE-17: Container + New modal has same fields as standalone editor', async () => {
      containerApi.list = vi.fn().mockResolvedValue([])
      containerApi.create = vi.fn().mockResolvedValue({
        id: 1, container_type: 'NEW-CTN', internal_length_cm: 1200, internal_width_cm: 235, internal_height_cm: 270, max_weight_kg: 28000, created_at: '', updated_at: ''
      })

      renderWithRouter(<ContainerTable />)

      const newButton = screen.getByRole('button', { name: /new container/i })
      fireEvent.click(newButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      expect(screen.getByLabelText(/container type \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/internal length \(cm\) \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/internal width \(cm\) \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/internal height \(cm\) \*/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/max weight \(kg\) \*/i)).toBeInTheDocument()
    })

    it('FE-18: Container modal stays open on validation error', async () => {
      containerApi.list = vi.fn().mockResolvedValue([])
      containerApi.create = vi.fn().mockRejectedValue({
        response: { data: { detail: 'Invalid input' } }
      })

      renderWithRouter(<ContainerTable />)

      const newButton = screen.getByRole('button', { name: /new container/i })
      fireEvent.click(newButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      fireEvent.change(screen.getByLabelText(/container type \*/i), { target: { value: 'TEST-CTN' } })
      fireEvent.change(screen.getByLabelText(/internal length \(cm\) \*/i), { target: { value: '-10' } })
      fireEvent.change(screen.getByLabelText(/internal width \(cm\) \*/i), { target: { value: '235' } })
      fireEvent.change(screen.getByLabelText(/internal height \(cm\) \*/i), { target: { value: '270' } })
      fireEvent.change(screen.getByLabelText(/max weight \(kg\) \*/i), { target: { value: '28000' } })

      const submitButton = screen.getByRole('button', { name: /create/i })
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      expect(screen.getByText(/length must be > 0/i)).toBeInTheDocument()
    })

    it('FE-19: Container modal closes and new record selected on success', async () => {
      containerApi.list = vi.fn().mockResolvedValue([])
      containerApi.create = vi.fn().mockResolvedValueOnce({
        id: 1, container_type: 'NEW-CTN', internal_length_cm: 1200, internal_width_cm: 235, internal_height_cm: 270, max_weight_kg: 28000, created_at: '', updated_at: ''
      })
      containerApi.list = vi.fn().mockResolvedValueOnce([
        { id: 1, container_type: 'NEW-CTN', internal_length_cm: 1200, internal_width_cm: 235, internal_height_cm: 270, max_weight_kg: 28000, created_at: '', updated_at: '' }
      ])

      renderWithRouter(<ContainerTable />)

      const newButton = screen.getByRole('button', { name: /new container/i })
      fireEvent.click(newButton)

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument()
      })

      fireEvent.change(screen.getByLabelText(/container type \*/i), { target: { value: 'NEW-CTN' } })
      fireEvent.change(screen.getByLabelText(/internal length \(cm\) \*/i), { target: { value: '1200' } })
      fireEvent.change(screen.getByLabelText(/internal width \(cm\) \*/i), { target: { value: '235' } })
      fireEvent.change(screen.getByLabelText(/internal height \(cm\) \*/i), { target: { value: '270' } })
      fireEvent.change(screen.getByLabelText(/max weight \(kg\) \*/i), { target: { value: '28000' } })

      const submitButton = screen.getByRole('button', { name: /create/i })
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })

      await waitFor(() => {
        expect(screen.getByText('NEW-CTN')).toBeInTheDocument()
      })
    })
  })
})