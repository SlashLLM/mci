import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

/** Legacy route: registration is disabled; send users to username/password login. */
export default function WorkerSignupPage() {
  const nav = useNavigate();
  useEffect(() => {
    nav("/login", { replace: true });
  }, [nav]);
  return null;
}
