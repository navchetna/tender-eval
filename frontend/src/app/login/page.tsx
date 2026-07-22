"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { GitBranch } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { Card } from "@/components/ui/Card";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/projects");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <Card className="w-full max-w-[380px] p-8">
        <div className="mb-6 flex items-center gap-[9px]">
          <div className="flex h-[27px] w-[27px] items-center justify-center rounded-lg bg-accent shadow-[0_2px_6px_-2px_rgba(47,93,138,.6)]">
            <GitBranch size={15} className="text-white" />
          </div>
          <div>
            <div className="text-[13.5px] leading-[1.1] font-semibold">Reconcile</div>
            <div className="text-[10.5px] text-ink-faint">tender ↔ bid</div>
          </div>
        </div>
        <h1 className="mb-1 text-[18px] font-semibold text-ink">Sign in</h1>
        <p className="mb-5 text-[13px] text-ink-soft">Use the email and password your admin gave you.</p>
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-ink-soft">Email</span>
            <input
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13.5px] text-ink outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-ink-soft">Password</span>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13.5px] text-ink outline-none focus:border-accent"
            />
          </label>
          {error && <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12.5px] text-bad-fg">{error}</div>}
          <button
            type="submit"
            disabled={submitting}
            className="btn mt-1 cursor-pointer rounded-[9px] border-none bg-accent px-4 py-2 text-[13.5px] font-medium text-white disabled:opacity-60"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </Card>
    </div>
  );
}
