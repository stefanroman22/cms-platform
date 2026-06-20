/**
 * Overview preferences, persisted to localStorage behind a small store interface.
 * Framework-free (no React) so it is trivially unit-testable and so the persistence
 * layer can later move to the backend without touching any panel code — the
 * interface is the seam.
 *
 * The Overview is a fixed two-part layout: an always-on calendar plus ONE selectable
 * statistics view. We therefore persist just two scalars — the selected stat view and
 * the staff scope — rather than a per-widget on/off layout.
 *
 * Storage key is versioned + project-scoped: `booking.overview.v1.<projectKey>`.
 */

/** Default statistics view shown on first load (the KPI overview). */
export const DEFAULT_STAT_VIEW = "overview";

/** "all" staff, or a specific staff resource_id. */
export type ScopeValue = string;

/** Default staff scope: every staff member's bookings. */
export const DEFAULT_SCOPE: ScopeValue = "all";

/** Calendar granularity. Day-first by request, defaulting to the day timeline. */
export type CalendarView = "day" | "week" | "month";
export const CALENDAR_VIEWS: CalendarView[] = ["day", "week", "month"];
export const DEFAULT_CALENDAR_VIEW: CalendarView = "day";

const STORAGE_PREFIX = "booking.overview.v1.";

interface StoredPrefs {
  /** id of the selected stat view (see STAT_VIEWS in widgetRegistry). */
  statView?: string;
  /** "all" | resource_id */
  scope?: ScopeValue;
  /** day | week | month — persisted so the owner reopens to the same view. */
  calendarView?: CalendarView;
}

export interface OverviewPrefsStore {
  getStatView(): string;
  setStatView(view: string): void;
  getScope(): ScopeValue;
  setScope(scope: ScopeValue): void;
  getCalendarView(): CalendarView;
  setCalendarView(view: CalendarView): void;
}

function safeRead(key: string): StoredPrefs {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as StoredPrefs) : {};
  } catch {
    return {};
  }
}

function safeWrite(key: string, value: StoredPrefs): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage unavailable / quota — preferences are best-effort, never throw.
  }
}

export function createOverviewPrefs(projectKey: string): OverviewPrefsStore {
  const key = `${STORAGE_PREFIX}${projectKey}`;

  return {
    getStatView() {
      const { statView } = safeRead(key);
      return typeof statView === "string" && statView ? statView : DEFAULT_STAT_VIEW;
    },
    setStatView(view) {
      const current = safeRead(key);
      safeWrite(key, { ...current, statView: view });
    },
    getScope() {
      const { scope } = safeRead(key);
      return typeof scope === "string" && scope ? scope : DEFAULT_SCOPE;
    },
    setScope(scope) {
      const current = safeRead(key);
      safeWrite(key, { ...current, scope });
    },
    getCalendarView() {
      const { calendarView } = safeRead(key);
      return CALENDAR_VIEWS.includes(calendarView as CalendarView)
        ? (calendarView as CalendarView)
        : DEFAULT_CALENDAR_VIEW;
    },
    setCalendarView(view) {
      const current = safeRead(key);
      safeWrite(key, { ...current, calendarView: view });
    },
  };
}
