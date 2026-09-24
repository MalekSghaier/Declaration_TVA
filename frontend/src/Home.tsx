// Home.tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <Navigate
      to={user.company_status === "LOCKED" ? "/dashboard" : "/onboarding"}
      replace
    />
  );
}