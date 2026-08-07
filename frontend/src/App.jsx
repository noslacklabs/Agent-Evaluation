import EvaluationDashboard from './pages/AgentEvaluator/EvaluationDashboard';
import EvaluationWizard from './pages/AgentEvaluator/EvaluationWizard';
import { usePathname } from './router';

export default function App() {
  const pathname = usePathname();
  return /^\/runs\/[^/]+$/.test(pathname) ? <EvaluationDashboard /> : <EvaluationWizard />;
}
