import { Navigate, Outlet } from "react-router-dom";
import { useAuth, type User } from "./AuthContext";

interface Props {
  status: User["company_status"];
  redirectTo: string;
}

// Laisse passer seulement si la societe a le statut demande, sinon redirige.
export default function RequireStatus({ status, redirectTo }: Props) {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.company_status !== status) return <Navigate to={redirectTo} replace />;

  return <Outlet />;
}