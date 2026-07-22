"use client";

import React, { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronDown, ChevronRight, Pencil, Trash2, UserPlus, X } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { Empty } from "@/components/ui/Empty";
import { useToast } from "@/components/ToastProvider";
import { ApiError, createEmployee, deleteEmployee, getEmployees, getEvaluationsByProject, getProjectFiles, getProjects, updateEmployee } from "@/lib/api";
import type { Employee, Role } from "@/lib/types";
import { isProjectCompleted } from "@/lib/projectStage";

interface AssignedProject {
  project_id: string;
  project_code: string;
  project_name: string;
  completed: boolean;
}

interface Workload {
  assigned: number;
  completed: number;
  projects: AssignedProject[];
}

export default function EmployeesPage() {
  const { user } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const [employees, setEmployees] = useState<Employee[] | null>(null);
  const [workload, setWorkload] = useState<Record<string, Workload>>({});
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("REVIEWER");
  const [submitting, setSubmitting] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editRole, setEditRole] = useState<Role>("REVIEWER");
  const [editPassword, setEditPassword] = useState("");
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (user && user.role !== "ADMIN") {
      router.replace("/projects");
    }
  }, [user, router]);

  useEffect(() => {
    if (user?.role !== "ADMIN") return;
    getEmployees()
      .then(setEmployees)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load employees"));
  }, [user]);

  useEffect(() => {
    if (user?.role !== "ADMIN") return;
    let cancelled = false;
    (async () => {
      try {
        const projects = await getProjects();
        const counts: Record<string, Workload> = {};
        await Promise.all(
          projects
            .filter((p) => p.assigned_to)
            .map(async (p) => {
              const employeeId = p.assigned_to as string;
              const files = await getProjectFiles(p.project_id);
              const currentFiles = files.filter((f) => f.version === p.current_version);
              const [tenderEvals, bidEvals] =
                p.current_version > 0
                  ? await Promise.all([
                      getEvaluationsByProject("tender", p.project_id, p.current_version),
                      getEvaluationsByProject("bid", p.project_id, p.current_version),
                    ])
                  : [[], []];
              const completed = isProjectCompleted(currentFiles, tenderEvals, bidEvals);
              const bucket = counts[employeeId] ?? { assigned: 0, completed: 0, projects: [] };
              bucket.assigned += 1;
              if (completed) bucket.completed += 1;
              bucket.projects.push({
                project_id: p.project_id,
                project_code: p.project_code,
                project_name: p.project_name,
                completed,
              });
              counts[employeeId] = bucket;
            })
        );
        if (!cancelled) setWorkload(counts);
      } catch {
        if (!cancelled) setWorkload({});
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (user?.role !== "ADMIN") return null;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await createEmployee({ name, email, password, role });
      setEmployees((prev) => (prev ? [...prev, created] : [created]));
      setName("");
      setEmail("");
      setPassword("");
      setRole("REVIEWER");
      toast(`${created.name} added as ${created.role === "ADMIN" ? "admin" : "reviewer"}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create employee");
    } finally {
      setSubmitting(false);
    }
  };

  const startEdit = (emp: Employee) => {
    setEditingId(emp.employee_id);
    setEditName(emp.name);
    setEditEmail(emp.email);
    setEditRole(emp.role);
    setEditPassword("");
    setEditError(null);
  };

  const cancelEdit = () => setEditingId(null);

  const saveEdit = async (employeeId: string) => {
    setEditSubmitting(true);
    setEditError(null);
    try {
      const updated = await updateEmployee(employeeId, {
        name: editName,
        email: editEmail,
        role: editRole,
        ...(editPassword ? { password: editPassword } : {}),
      });
      setEmployees((prev) => prev?.map((e) => (e.employee_id === employeeId ? updated : e)) ?? prev);
      setEditingId(null);
      toast(`${updated.name} updated`);
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to update employee");
    } finally {
      setEditSubmitting(false);
    }
  };

  const onDelete = async (emp: Employee) => {
    if (!window.confirm(`Remove ${emp.name} (${emp.email})? This cannot be undone.`)) return;
    setDeletingId(emp.employee_id);
    try {
      await deleteEmployee(emp.employee_id);
      setEmployees((prev) => prev?.filter((e) => e.employee_id !== emp.employee_id) ?? prev);
      toast(`${emp.name} removed`);
    } catch (err) {
      toast(
        err instanceof ApiError
          ? err.message
          : "Failed to delete employee"
      );
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="px-[30px] py-[26px]">
      <h1 className="m-0 text-[21px] font-semibold text-ink">Employees</h1>
      <p className="mt-[5px] mb-[22px] text-[13.5px] text-ink-soft">
        Admins and reviewers who can sign in to the frontend. Only admins can add, edit, or remove employees.
      </p>

      <div className="grid grid-cols-[1fr_320px] items-start gap-4">
        <div>
          <Card className="overflow-hidden">
            {employees === null && <Empty>Loading…</Empty>}
            {employees !== null && employees.length === 0 && <Empty>No employees yet.</Empty>}
            {employees && employees.length > 0 && (
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-surface2">
                    {["Name", "Email", "Role", "Workload", ""].map((h) => (
                      <th
                        key={h}
                        className="border-b-[0.5px] border-line px-[14px] py-[9px] text-left text-[11.5px] font-semibold tracking-[0.3px] text-ink-faint uppercase"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {employees.map((emp, i) => {
                    const w = workload[emp.employee_id];
                    const hasProjects = !!w && w.assigned > 0;
                    const isExpanded = expandedId === emp.employee_id;
                    return (
                    <React.Fragment key={emp.employee_id}>
                    <tr className={i ? "border-t-[0.5px] border-line" : ""}>
                      {editingId === emp.employee_id ? (
                        <td colSpan={5} className="px-[14px] py-[10px]">
                          <div className="flex flex-wrap items-center gap-2">
                            <input
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              placeholder="Name"
                              className="rounded-[8px] border-[0.5px] border-line-strong bg-surface px-2 py-1 text-[13px] text-ink outline-none focus:border-accent"
                            />
                            <input
                              type="email"
                              value={editEmail}
                              onChange={(e) => setEditEmail(e.target.value)}
                              placeholder="Email"
                              className="rounded-[8px] border-[0.5px] border-line-strong bg-surface px-2 py-1 font-mono text-[12px] text-ink outline-none focus:border-accent"
                            />
                            <select
                              value={editRole}
                              onChange={(e) => setEditRole(e.target.value as Role)}
                              className="rounded-[8px] border-[0.5px] border-line-strong bg-surface px-2 py-1 text-[13px] text-ink outline-none focus:border-accent"
                            >
                              <option value="REVIEWER">Reviewer</option>
                              <option value="ADMIN">Admin</option>
                            </select>
                            <input
                              type="password"
                              value={editPassword}
                              onChange={(e) => setEditPassword(e.target.value)}
                              placeholder="New password (optional)"
                              className="rounded-[8px] border-[0.5px] border-line-strong bg-surface px-2 py-1 text-[13px] text-ink outline-none focus:border-accent"
                            />
                            <button
                              type="button"
                              disabled={editSubmitting}
                              onClick={() => saveEdit(emp.employee_id)}
                              className="btn cursor-pointer rounded-[8px] border-none bg-accent px-3 py-1 text-[12.5px] font-medium text-white disabled:opacity-60"
                            >
                              {editSubmitting ? "Saving…" : "Save"}
                            </button>
                            <button
                              type="button"
                              onClick={cancelEdit}
                              className="btn cursor-pointer rounded-[8px] border-[0.5px] border-line-strong bg-transparent p-[6px] text-ink-faint"
                              title="Cancel"
                            >
                              <X size={14} />
                            </button>
                          </div>
                          {editError && <div className="mt-[6px] text-[12px] text-bad-fg">{editError}</div>}
                        </td>
                      ) : (
                        <>
                          <td className="px-[14px] py-[10px] text-[13px] text-ink">{emp.name}</td>
                          <td className="px-[14px] py-[10px] font-mono text-[12px] text-ink-soft">{emp.email}</td>
                          <td className="px-[14px] py-[10px]">
                            <Pill tone={emp.role === "ADMIN" ? "info" : "none"} mono>
                              {emp.role.toLowerCase()}
                            </Pill>
                          </td>
                          <td className="px-[14px] py-[10px] text-[12.5px] text-ink-soft">
                            {!hasProjects ? (
                              <span className="text-ink-faint">No projects assigned</span>
                            ) : (
                              <button
                                type="button"
                                onClick={() => setExpandedId(isExpanded ? null : emp.employee_id)}
                                className="btn flex cursor-pointer items-center gap-1 rounded-md border-none bg-transparent p-0 text-[12.5px] text-ink-soft"
                              >
                                {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                                {w.assigned} assigned · {w.completed} completed
                              </button>
                            )}
                          </td>
                          <td className="px-[14px] py-[10px] text-right whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => startEdit(emp)}
                              className="btn cursor-pointer rounded-md border-none bg-transparent p-1 text-ink-faint"
                              title="Edit"
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              type="button"
                              disabled={deletingId === emp.employee_id}
                              onClick={() => onDelete(emp)}
                              className="btn cursor-pointer rounded-md border-none bg-transparent p-1 text-bad-fg disabled:opacity-60"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </>
                      )}
                    </tr>
                    {isExpanded && hasProjects && (
                      <tr className="border-t-[0.5px] border-line bg-surface2">
                        <td colSpan={5} className="px-[14px] py-[10px]">
                          <div className="flex flex-col gap-[6px]">
                            {w!.projects.map((p) => (
                              <Link
                                key={p.project_id}
                                href={`/projects/${p.project_id}`}
                                className="flex items-center justify-between rounded-md px-2 py-1 text-[12.5px] text-ink hover:bg-surface"
                              >
                                <span className="flex items-center gap-2">
                                  <span className="font-mono text-[11px] text-ink-faint">{p.project_code}</span>
                                  <span>{p.project_name}</span>
                                </span>
                                <Pill tone={p.completed ? "ok" : "info"}>{p.completed ? "Completed" : "In progress"}</Pill>
                              </Link>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                    </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Card>
        </div>

        <div>
          <Card className="p-4">
            <div className="mb-3 flex items-center gap-2 text-[13.5px] font-semibold text-ink">
              <UserPlus size={16} className="text-accent" />
              Add employee
            </div>
            <form onSubmit={onSubmit} className="flex flex-col gap-[10px]">
              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-ink-soft">Name</span>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-ink-soft">Email</span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-ink-soft">Initial password</span>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-ink-soft">Role</span>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as Role)}
                  className="rounded-[9px] border-[0.5px] border-line-strong bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
                >
                  <option value="REVIEWER">Reviewer</option>
                  <option value="ADMIN">Admin</option>
                </select>
              </label>
              {error && <div className="rounded-[9px] bg-bad-bg px-3 py-2 text-[12px] text-bad-fg">{error}</div>}
              <button
                type="submit"
                disabled={submitting}
                className="btn mt-1 cursor-pointer rounded-[9px] border-none bg-accent px-4 py-2 text-[13px] font-medium text-white disabled:opacity-60"
              >
                {submitting ? "Adding…" : "Add employee"}
              </button>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
}
