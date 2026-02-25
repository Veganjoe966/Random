"use client";

export default function StudentsPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Students</h1>
          <p className="text-muted-foreground">
            Manage and monitor student memorization progress.
          </p>
        </div>
        <button className="rounded-md bg-primary px-4 py-2 text-primary-foreground text-sm font-medium">
          Add Student
        </button>
      </div>

      {/* Student table placeholder */}
      <div className="rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-3 text-left text-sm font-medium">Name</th>
              <th className="p-3 text-left text-sm font-medium">Teacher</th>
              <th className="p-3 text-left text-sm font-medium">Progress</th>
              <th className="p-3 text-left text-sm font-medium">Retention</th>
              <th className="p-3 text-left text-sm font-medium">Streak</th>
              <th className="p-3 text-left text-sm font-medium">Last Active</th>
              <th className="p-3 text-left text-sm font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="p-3 text-sm text-muted-foreground" colSpan={7}>
                Student list will be populated from API.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
