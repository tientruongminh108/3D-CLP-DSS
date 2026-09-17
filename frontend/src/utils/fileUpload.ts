import { ShipmentType } from '../types/api'
import type { PackingListPreview, PackingListPreviewRow } from '../types/api'

export interface ParsedPackingList {
  preview: PackingListPreview
  rawRows: any[]
}

export interface FileUploadResult {
  success: boolean
  data?: ParsedPackingList
  error?: string
}

/**
 * Parse CSV content into array of objects
 */
function parseCSV(csvText: string): any[] {
  const lines = csvText.trim().split('\n')
  if (lines.length < 2) return []

  const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''))
  const rows: any[] = []

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''))
    if (values.length !== headers.length) continue

    const row: any = {}
    headers.forEach((header, index) => {
      row[header] = values[index]
    })
    rows.push(row)
  }

  return rows
}

/**
 * Parse JSON content into array of objects
 */
function parseJSON(jsonText: string): any[] {
  try {
    const parsed = JSON.parse(jsonText)
    return Array.isArray(parsed) ? parsed : [parsed]
  } catch {
    return []
  }
}

/**
 * Validate and normalize a row from CSV/JSON into PackingListPreviewRow
 */
function normalizeRow(row: any, index: number): PackingListPreviewRow | null {
  // Required fields mapping - support multiple column name variations
  const getValue = (keys: string[]) => {
    for (const key of keys) {
      if (row[key] !== undefined && row[key] !== '') return row[key]
    }
    return undefined
  }

  const itemId = getValue(['Item Code', 'item_code', 'ItemCode', 'SKU', 'sku', 'ID', 'id'])
  const description = getValue(['Name', 'name', 'Description', 'description', 'Item Name', 'item_name'])
  const poNo = getValue(['PO', 'po', 'PO No', 'po_no', 'PONo', 'Order No', 'order_no'])
  const customerCode = getValue(['Customer', 'customer', 'Customer Code', 'customer_code', 'CustomerCode'])
  const qtyCartons = parseFloat(getValue(['Quantity', 'quantity', 'Qty', 'qty', 'Cartons', 'cartons', 'Qty Cartons', 'qty_cartons']) || '0')
  const lengthCm = parseFloat(getValue(['Length', 'length', 'Length (cm)', 'length_cm', 'L', 'l']) || '0')
  const widthCm = parseFloat(getValue(['Width', 'width', 'Width (cm)', 'width_cm', 'W', 'w']) || '0')
  const heightCm = parseFloat(getValue(['Height', 'height', 'Height (cm)', 'height_cm', 'H', 'h']) || '0')
  const weightKg = parseFloat(getValue(['Weight', 'weight', 'Weight (kg)', 'weight_kg', 'KG', 'kg']) || '0')
  const thisWayUp = getValue(['This Way Up', 'this_way_up', 'ThisWayUp', 'Orientation', 'orientation'])
  const stackingGroup = parseInt(getValue(['Stacking Group', 'stacking_group', 'StackGroup', 'Stack Group', 'Group', 'group']) || '1', 10)
  const maxLoadBearingKg = parseFloat(getValue(['Max Load Bearing', 'max_load_bearing_kg', 'MaxLoadBearing', 'Load Bearing']) || '0')

  // Validate required fields
  if (!itemId || !description || qtyCartons <= 0 || lengthCm <= 0 || widthCm <= 0 || heightCm <= 0 || weightKg <= 0) {
    return null
  }

  return {
    item_id: String(itemId),
    po_no: String(poNo || `PO-${index + 1}`),
    customer_code: customerCode ? String(customerCode) : undefined,
    description: String(description),
    qty_cartons: qtyCartons,
    length_cm: lengthCm,
    width_cm: widthCm,
    height_cm: heightCm,
    weight_kg: weightKg,
    this_way_up: thisWayUp ? String(thisWayUp).toLowerCase() === 'true' || String(thisWayUp).toLowerCase() === 'yes' || String(thisWayUp) === '1' : false,
    stacking_group: stackingGroup || 1,
    max_load_bearing_kg: maxLoadBearingKg > 0 ? maxLoadBearingKg : undefined,
  }
}

/**
 * Determine shipment type from rows
 */
function determineShipmentType(rows: PackingListPreviewRow[]): ShipmentType {
  const customerCodes = new Set(rows.map(r => r.customer_code).filter(Boolean))
  return customerCodes.size > 1 ? ShipmentType.LCL : ShipmentType.FCL
}

/**
 * Calculate totals from rows
 */
function calculateTotals(rows: PackingListPreviewRow[]) {
  let totalCartons = 0
  let totalWeightKg = 0
  let totalVolumeCm3 = 0

  for (const row of rows) {
    totalCartons += row.qty_cartons
    totalWeightKg += row.weight_kg * row.qty_cartons
    totalVolumeCm3 += row.length_cm * row.width_cm * row.height_cm * row.qty_cartons
  }

  return { totalCartons, totalWeightKg, totalVolumeCm3 }
}

/**
 * Main function to parse uploaded file (CSV or JSON)
 */
export async function parsePackingListFile(file: File): Promise<FileUploadResult> {
  const validExtensions = ['.csv', '.json']
  const fileName = file.name.toLowerCase()
  const isValidExtension = validExtensions.some(ext => fileName.endsWith(ext))

  if (!isValidExtension) {
    return {
      success: false,
      error: 'Invalid file format. Please upload a .csv or .json file.',
    }
  }

  return new Promise((resolve) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        if (!content) {
          resolve({ success: false, error: 'File is empty' })
          return
        }

        let rawRows: any[] = []

        if (fileName.endsWith('.csv')) {
          rawRows = parseCSV(content)
        } else if (fileName.endsWith('.json')) {
          rawRows = parseJSON(content)
        }

        if (rawRows.length === 0) {
          resolve({ success: false, error: 'No valid data rows found in file' })
          return
        }

        // Normalize rows
        const previewRows: PackingListPreviewRow[] = []
        const errors: string[] = []

        rawRows.forEach((row, index) => {
          const normalized = normalizeRow(row, index)
          if (normalized) {
            previewRows.push(normalized)
          } else {
            errors.push(`Row ${index + 1}: Missing or invalid required fields`)
          }
        })

        if (previewRows.length === 0) {
          resolve({
            success: false,
            error: 'No valid items could be parsed from the file. Please check your CSV/JSON format.',
          })
          return
        }

        const shipmentType = determineShipmentType(previewRows)
        const customerCodes = new Set(previewRows.map(r => r.customer_code).filter(Boolean))
        const { totalCartons, totalWeightKg, totalVolumeCm3 } = calculateTotals(previewRows)

        const preview: PackingListPreview = {
          rows: previewRows,
          shipment_type: shipmentType,
          customer_count: customerCodes.size,
          total_cartons: totalCartons,
          total_weight_kg: totalWeightKg,
          total_volume_cm3: totalVolumeCm3,
        }

        resolve({
          success: true,
          data: {
            preview,
            rawRows: previewRows,
          },
        })
      } catch (err) {
        resolve({
          success: false,
          error: `Failed to parse file: ${err instanceof Error ? err.message : 'Unknown error'}`,
        })
      }
    }

    reader.onerror = () => {
      resolve({ success: false, error: 'Failed to read file' })
    }

    reader.readAsText(file)
  })
}

/**
 * Generate a sample CSV template for download
 */
export function generateSampleCSV(): string {
  const headers = [
    'Item Code',
    'Name',
    'PO',
    'Customer',
    'Quantity',
    'Length (cm)',
    'Width (cm)',
    'Height (cm)',
    'Weight (kg)',
    'This Way Up (true/false)',
    'Stacking Group',
    'Max Load Bearing (kg)',
  ]

  const sampleRows = [
    ['SKU-001', 'Widget A', 'PO-1001', 'CUST-01', '50', '30', '20', '15', '2.5', 'false', '1', '100'],
    ['SKU-002', 'Widget B', 'PO-1001', 'CUST-01', '30', '40', '30', '25', '5.0', 'true', '2', '200'],
    ['SKU-003', 'Gadget X', 'PO-1002', 'CUST-02', '100', '25', '25', '20', '1.8', 'false', '1', '80'],
    ['SKU-004', 'Gadget Y', 'PO-1002', 'CUST-02', '75', '35', '25', '30', '3.2', 'false', '3', '150'],
  ]

  return [headers.join(','), ...sampleRows.map(r => r.join(','))].join('\n')
}