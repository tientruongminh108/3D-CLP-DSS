import Papa from 'papaparse'
import type { PackingListRow } from '../types/api'

export interface CSVParseResult<T> {
  success: boolean
  data?: T[]
  errors?: string[]
  error?: string
}

/**
 * Parse CSV text into PackingListRow array using PapaParse
 */
export function parseCSV(text: string): Promise<PackingListRow[]> {
  return new Promise((resolve, reject) => {
    Papa.parse(text, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
      complete: (results) => {
        const rows: PackingListRow[] = (results.data as Record<string, unknown>[]).map((row) => ({
          item_id: String(row.Item_ID || row.item_id || row['Item Code'] || row['item_code'] || '').trim(),
          po_no: String(row.PO_No || row.po_no || row.PO || row.po || '').trim(),
          customer_code: row.Customer_Code || row.customer_code || row.Customer || row.customer
            ? String(row.Customer_Code || row.customer_code || row.Customer || row.customer).trim()
            : undefined,
          description: row.Description || row.description || row.Name || row.name
            ? String(row.Description || row.description || row.Name || row.name).trim()
            : undefined,
          qty_pcs: parseInt(String(row.Qty_Pcs || row.qty_pcs || row.Quantity || row.quantity || '0'), 10),
          qty_cartons: parseInt(String(row.Qty_Cartons || row.qty_cartons || row.Cartons || row.cartons || '0'), 10),
        }))
        resolve(rows)
      },
      error: (error: Error) => reject(error),
    })
  })
}

/**
 * Validate packing list rows
 */
export function validatePackingListRows(rows: PackingListRow[]): string[] {
  const errors: string[] = []
  rows.forEach((row, index) => {
    if (!row.item_id) errors.push(`Row ${index + 1}: Item_ID is required`)
    if (!row.po_no) errors.push(`Row ${index + 1}: PO_No is required`)
    if (row.qty_pcs <= 0) errors.push(`Row ${index + 1}: Qty_Pcs must be > 0`)
    if (row.qty_cartons <= 0) errors.push(`Row ${index + 1}: Qty_Cartons must be > 0`)
  })
  return errors
}

/**
 * Generate CSV template for packing lists
 */
export function generatePackingListsCSVTemplate(): string {
  const headers = ['item_id', 'po_no', 'customer_code', 'description', 'qty_pcs', 'qty_cartons']
  const sampleRows = [
    ['SKU-001', 'PO-1001', 'CUST-A', 'Standard Box', '50', '50'],
    ['SKU-002', 'PO-1001', 'CUST-A', 'Large Carton', '30', '30'],
    ['SKU-003', 'PO-1002', 'CUST-B', 'Fragile Item', '100', '100'],
  ]
  return [headers.join(','), ...sampleRows.map((r) => r.join(','))].join('\n')
}

export function generateCSVTemplate(): string {
  return generatePackingListsCSVTemplate()
}

/**
 * Generate CSV template for items
 */
export function generateItemsCSVTemplate(): string {
  const headers = ['item_id', 'description', 'length_cm', 'width_cm', 'height_cm', 'weight_kg', 'this_way_up', 'stacking_group', 'max_load_bearing_kg']
  const sampleRows = [
    ['SKU-001', 'Standard Box', '30', '20', '15', '2.5', 'true', '1', '100'],
    ['SKU-002', 'Large Carton', '40', '30', '25', '5.0', 'false', '1', '200'],
    ['SKU-003', 'Fragile Item', '25', '25', '20', '1.8', 'true', '2', '50'],
  ]
  return [headers.join(','), ...sampleRows.map((r) => r.join(','))].join('\n')
}

/**
 * Generate CSV template for containers
 */
export function generateContainersCSVTemplate(): string {
  const headers = ['container_type', 'internal_length_cm', 'internal_width_cm', 'internal_height_cm', 'max_weight_kg']
  const sampleRows = [
    ['20GP', '589.8', '235.2', '239.3', '28000'],
    ['40GP', '1203.2', '235.2', '239.3', '28000'],
    ['40HC', '1203.2', '235.2', '270.0', '28000'],
  ]
  return [headers.join(','), ...sampleRows.map((r) => r.join(','))].join('\n')
}

/**
 * Download CSV helper
 */
export function downloadCSV(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

export function downloadCSVTemplate(content: string, filename: string) {
  downloadCSV(content, filename)
}