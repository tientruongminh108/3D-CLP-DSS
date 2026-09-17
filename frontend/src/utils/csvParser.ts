import type { ItemCreate, ContainerCreate, PackingListRow } from '../types/api'

export interface ParseResult<T> {
  success: boolean
  data?: T[]
  errors?: string[]
  error?: string
}

export interface CSVParserOptions {
  delimiter?: string
  skipEmptyLines?: boolean
}

/**
 * Generic CSV parser using FileReader API
 */
export function parseCSV<T>(
  file: File,
  rowMapper: (row: Record<string, string>, index: number) => T | null,
  options: CSVParserOptions = {}
): Promise<ParseResult<T>> {
  const { delimiter = ',', skipEmptyLines = true } = options

  return new Promise((resolve) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        if (!content || !content.trim()) {
          resolve({ success: false, error: 'File is empty' })
          return
        }

        const lines = content.split('\n')
        if (lines.length < 2) {
          resolve({ success: false, error: 'CSV must have at least a header row and one data row' })
          return
        }

        // Parse headers
        const headers = lines[0].split(delimiter).map(h => h.trim().replace(/^"|"$/g, ''))
        
        const data: T[] = []
        const errors: string[] = []

        for (let i = 1; i < lines.length; i++) {
          const line = lines[i].trim()
          if (skipEmptyLines && !line) continue

          const values = parseCSVLine(line, delimiter)
          
          if (values.length !== headers.length) {
            errors.push(`Row ${i + 1}: Column count mismatch (expected ${headers.length}, got ${values.length})`)
            continue
          }

          const row: Record<string, string> = {}
          headers.forEach((header, idx) => {
            row[header] = values[idx]?.replace(/^"|"$/g, '') || ''
          })

          const mapped = rowMapper(row, i)
          if (mapped) {
            data.push(mapped)
          } else {
            errors.push(`Row ${i + 1}: Invalid or missing required fields`)
          }
        }

        if (data.length === 0) {
          resolve({ 
            success: false, 
            error: 'No valid data rows found',
            errors: errors.length > 0 ? errors : undefined
          })
          return
        }

        resolve({ success: true, data, errors: errors.length > 0 ? errors : undefined })
      } catch (err) {
        resolve({ 
          success: false, 
          error: `Parse error: ${err instanceof Error ? err.message : 'Unknown error'}` 
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
 * Parse a CSV line handling quoted fields with commas
 */
function parseCSVLine(line: string, delimiter: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    const nextChar = line[i + 1]
    
    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
    } else if (char === delimiter && !inQuotes) {
      result.push(current)
      current = ''
    } else {
      current += char
    }
  }
  
  result.push(current)
  return result
}

/**
 * Normalize header names to handle variations
 */
function normalizeHeader(header: string): string {
  return header
    .toLowerCase()
    .replace(/[_\s-]+/g, '_')
    .replace(/[()]/g, '')
    .trim()
}

/**
 * Get value from row using multiple possible header names
 */
function getRowValue(row: Record<string, string>, possibleKeys: string[]): string | undefined {
  const normalizedRow: Record<string, string> = {}
  Object.entries(row).forEach(([key, value]) => {
    normalizedRow[normalizeHeader(key)] = value
  })

  for (const key of possibleKeys) {
    const normalizedKey = normalizeHeader(key)
    if (normalizedRow[normalizedKey] !== undefined && normalizedRow[normalizedKey] !== '') {
      return normalizedRow[normalizedKey]
    }
  }
  return undefined
}

/**
 * Parse number with validation
 */
function parseNumber(value: string | undefined, defaultValue = 0): number {
  if (value === undefined || value === '') return defaultValue
  const parsed = parseFloat(value)
  return isNaN(parsed) ? defaultValue : parsed
}

/**
 * Parse integer with validation
 */
function parseIntSafe(value: string | undefined, defaultValue = 0): number {
  if (value === undefined || value === '') return defaultValue
  const parsed = parseInt(value, 10)
  return isNaN(parsed) ? defaultValue : parsed
}

/**
 * Parse boolean with flexible input
 */
function parseBoolean(value: string | undefined, defaultValue = false): boolean {
  if (value === undefined || value === '') return defaultValue
  const lower = value.toLowerCase().trim()
  return lower === 'true' || lower === 'yes' || lower === '1' || lower === 'y'
}

/**
 * ============================================
 * ITEM CSV PARSER
 * Expected columns: item_id, description, length, width, height, weight, stack_group, max_load
 * ============================================
 */
export function parseItemsCSV(file: File): Promise<ParseResult<ItemCreate>> {
  return parseCSV<ItemCreate>(file, (row, _index) => {
    const itemId = getRowValue(row, ['item_id', 'item code', 'itemcode', 'sku', 'id', 'code'])
    const description = getRowValue(row, ['description', 'name', 'item_name', 'item name', 'desc'])
    const lengthCm = parseNumber(getRowValue(row, ['length', 'length_cm', 'length (cm)', 'l', 'len']))
    const widthCm = parseNumber(getRowValue(row, ['width', 'width_cm', 'width (cm)', 'w', 'wid']))
    const heightCm = parseNumber(getRowValue(row, ['height', 'height_cm', 'height (cm)', 'h', 'hei']))
    const weightKg = parseNumber(getRowValue(row, ['weight', 'weight_kg', 'weight (kg)', 'kg', 'wt']))
    const thisWayUp = parseBoolean(getRowValue(row, ['this_way_up', 'thiswayup', 'orientation', 'upright']), true)
    const stackingGroup = parseIntSafe(getRowValue(row, ['stack_group', 'stacking_group', 'stackgroup', 'group', 'stack']), 1)
    const maxLoadBearingKg = getRowValue(row, ['max_load', 'max_load_bearing_kg', 'max_load_bearing', 'maxload', 'load_bearing', 'loadbearing'])

    // Validate required fields
    if (!itemId || !description || lengthCm <= 0 || widthCm <= 0 || heightCm <= 0 || weightKg <= 0) {
      return null
    }

    return {
      item_id: String(itemId),
      description: String(description),
      length_cm: lengthCm,
      width_cm: widthCm,
      height_cm: heightCm,
      weight_kg: weightKg,
      this_way_up: thisWayUp,
      stacking_group: stackingGroup,
      max_load_bearing_kg: maxLoadBearingKg ? parseNumber(maxLoadBearingKg) : undefined,
    }
  })
}

/**
 * ============================================
 * CONTAINER CSV PARSER
 * Expected columns: container_id, name, type, internal_length, internal_width, internal_height, max_weight
 * ============================================
 */
export function parseContainersCSV(file: File): Promise<ParseResult<ContainerCreate>> {
  return parseCSV<ContainerCreate>(file, (row, _index) => {
    const containerType = getRowValue(row, ['container_type', 'container type', 'type', 'container_id', 'container id', 'name', 'id', 'code'])
    const internalLengthCm = parseNumber(getRowValue(row, ['internal_length', 'internal_length_cm', 'length', 'length_cm', 'length (cm)', 'l', 'len']))
    const internalWidthCm = parseNumber(getRowValue(row, ['internal_width', 'internal_width_cm', 'width', 'width_cm', 'width (cm)', 'w', 'wid']))
    const internalHeightCm = parseNumber(getRowValue(row, ['internal_height', 'internal_height_cm', 'height', 'height_cm', 'height (cm)', 'h', 'hei']))
    const maxWeightKg = parseNumber(getRowValue(row, ['max_weight', 'max_weight_kg', 'max weight', 'weight', 'weight (kg)', 'kg', 'capacity']))

    if (!containerType || internalLengthCm <= 0 || internalWidthCm <= 0 || internalHeightCm <= 0 || maxWeightKg <= 0) {
      return null
    }

    return {
      container_type: String(containerType),
      internal_length_cm: internalLengthCm,
      internal_width_cm: internalWidthCm,
      internal_height_cm: internalHeightCm,
      max_weight_kg: maxWeightKg,
    }
  })
}

/**
 * ============================================
 * PACKING LIST CSV PARSER
 * Expected columns: list_id, client_name, total_cartons, and item arrays
 * ============================================
 */
export function parsePackingListsCSV(file: File): Promise<ParseResult<PackingListRow>> {
  return parseCSV<PackingListRow>(file, (row, _index) => {
    const itemId = getRowValue(row, ['item_id', 'item code', 'itemcode', 'sku', 'id', 'code'])
    const poNo = getRowValue(row, ['po_no', 'po no', 'po', 'po_number', 'order_no', 'order'])
    const customerCode = getRowValue(row, ['customer_code', 'customer code', 'customer', 'client_code', 'client', 'cust'])
    const description = getRowValue(row, ['description', 'name', 'item_name', 'item name', 'desc'])
    const qtyPcs = parseIntSafe(getRowValue(row, ['qty_pcs', 'qty pcs', 'pieces', 'pcs', 'qty']), 0)
    const qtyCartons = parseIntSafe(getRowValue(row, ['qty_cartons', 'qty cartons', 'cartons', 'ctns', 'quantity']), 0)

    if (!itemId || !poNo || qtyCartons <= 0) {
      return null
    }

    return {
      item_id: String(itemId),
      po_no: String(poNo),
      customer_code: customerCode ? String(customerCode) : undefined,
      description: description ? String(description) : undefined,
      qty_pcs: qtyPcs || qtyCartons,
      qty_cartons: qtyCartons,
    }
  })
}

/**
 * Generate CSV template for items
 */
export function generateItemsCSVTemplate(): string {
  const headers = ['item_id', 'description', 'length_cm', 'width_cm', 'height_cm', 'weight_kg', 'this_way_up', 'stack_group', 'max_load_bearing_kg']
  const sampleRows = [
    ['SKU-001', 'Standard Box', '30', '20', '15', '2.5', 'true', '1', '100'],
    ['SKU-002', 'Large Carton', '40', '30', '25', '5.0', 'false', '1', '200'],
    ['SKU-003', 'Fragile Item', '25', '25', '20', '1.8', 'true', '2', '50'],
  ]
  return [headers.join(','), ...sampleRows.map(r => r.join(','))].join('\n')
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
  return [headers.join(','), ...sampleRows.map(r => r.join(','))].join('\n')
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
  return [headers.join(','), ...sampleRows.map(r => r.join(','))].join('\n')
}

/**
 * Download CSV template helper
 */
export function downloadCSVTemplate(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}