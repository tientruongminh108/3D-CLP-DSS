import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './components/Dashboard'
import { RunWizard } from './components/RunWizard'
import { RunHistory } from './components/RunHistory'
import { PackingListsManagement } from './components/PackingListsManagement'
import { PackingListDetail } from './components/PackingListDetail'
import { ItemMasterTable } from './components/ItemMasterTable'
import { ContainerTable } from './components/ContainerTable'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<RunWizard />} />
        <Route path="/new-run" element={<Navigate to="/" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/history" element={<RunHistory />} />
        <Route path="/data" element={<Navigate to="/data/packing-lists" replace />} />
        <Route path="/data/packing-lists" element={<PackingListsManagement />} />
        <Route path="/data/packing-lists/:id" element={<PackingListDetail />} />
        <Route path="/data/items" element={<ItemMasterTable />} />
        <Route path="/data/containers" element={<ContainerTable />} />
      </Route>
    </Routes>
  )
}

export default App