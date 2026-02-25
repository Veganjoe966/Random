"use client";

import { useEffect, useState } from "react";

interface DashboardStats {
  total_students: number;
  total_teachers: number;
  total_recitations: number;
  recitations_this_month: number;
  average_accuracy: number;
  average_retention: number;
  active_students_7d: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-2">Masjid Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        AI-assisted memorization insights. Teachers have final authority over all assessments.
      </p>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Active Students"
          value={stats?.active_students_7d ?? "—"}
          subtitle="Last 7 days"
        />
        <StatCard
          title="Recitations This Month"
          value={stats?.recitations_this_month ?? "—"}
          subtitle="Processing complete"
        />
        <StatCard
          title="Avg. Accuracy"
          value={stats ? `${(stats.average_accuracy * 100).toFixed(1)}%` : "—"}
          subtitle="Across all students"
        />
        <StatCard
          title="Avg. Retention"
          value={stats ? `${(stats.average_retention * 100).toFixed(1)}%` : "—"}
          subtitle="Predicted recall"
        />
      </div>

      {/* Placeholder sections for full implementation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-lg border p-6">
          <h2 className="text-xl font-semibold mb-4">Recent Recitations</h2>
          <p className="text-muted-foreground">
            Pending teacher review queue will appear here.
          </p>
        </div>
        <div className="rounded-lg border p-6">
          <h2 className="text-xl font-semibold mb-4">Students Needing Attention</h2>
          <p className="text-muted-foreground">
            Students with declining retention scores.
          </p>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string | number;
  subtitle: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
    </div>
  );
}
