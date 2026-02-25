/**
 * TypeScript type definitions matching backend Pydantic schemas.
 */

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "super_admin" | "masjid_admin" | "teacher" | "student" | "parent";
  tenant_id: string | null;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  email: string;
  subscription_tier: string;
  subscription_status: string;
  max_students: number;
  max_teachers: number;
  timezone: string;
}

export interface Recitation {
  id: string;
  student_id: string;
  surah_number: number;
  ayah_start: number;
  ayah_end: number;
  recitation_type: "new_lesson" | "revision" | "test";
  status: "uploaded" | "processing" | "completed" | "failed" | "reviewed";
  audio_duration_seconds: number | null;
  overall_accuracy_score: number | null;
  overall_tajweed_score: number | null;
  word_error_rate: number | null;
  total_words: number | null;
  correct_words: number | null;
  error_count: number | null;
  teacher_reviewed: boolean;
  teacher_override_score: number | null;
  teacher_notes: string | null;
  created_at: string;
}

export interface AyahScore {
  id: string;
  surah_number: number;
  ayah_number: number;
  accuracy_score: number;
  tajweed_score: number;
  combined_score: number;
  total_words: number;
  correct_words: number;
  missing_words: number;
  added_words: number;
  substituted_words: number;
  teacher_override_score: number | null;
}

export interface WordAnalysis {
  id: string;
  surah_number: number;
  ayah_number: number;
  word_position: number;
  reference_word: string;
  recited_word: string | null;
  status: "correct" | "substituted" | "missing" | "added";
  start_time: number | null;
  end_time: number | null;
  duration: number | null;
  tajweed_score: number | null;
}

export interface StudentProfile {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  current_surah: number;
  current_ayah: number;
  total_ayahs_memorized: number;
  total_juz_completed: number;
  average_retention_score: number;
  average_accuracy_score: number;
  streak_days: number;
}

export interface ScheduleItem {
  surah_number: number;
  ayah_start: number;
  ayah_end: number;
  predicted_retention: number;
  priority: "critical" | "high" | "medium" | "low";
  reason: string;
  estimated_seconds: number;
  mastery_level: string;
}

export interface RevisionSchedule {
  schedule_date: string;
  items: ScheduleItem[];
  total_items: number;
  total_ayahs: number;
  estimated_minutes: number;
  critical_count: number;
  high_count: number;
}
