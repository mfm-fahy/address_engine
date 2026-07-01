import { Routes, Route } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import CustomerDetail from './components/CustomerDetail'

export default function App() {
  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/customer/:id" element={<CustomerDetail />} />
      </Routes>
    </div>
  )
}
