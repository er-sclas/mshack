/**
 * Main App Component
 *
 * Sets up routing and layout for the Chepauk Traffic Portal.
 */

import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Scenarios from './pages/Scenarios';
import Runs from './pages/Runs';
import RunDetail from './pages/RunDetail';
import Compare from './pages/Compare';
import Chat from './pages/Chat';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/scenarios" element={<Scenarios />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/runs/:runId" element={<RunDetail />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/chat" element={<Chat />} />
      </Routes>
    </Layout>
  );
}
