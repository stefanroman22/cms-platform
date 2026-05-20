"use client";

import { useState } from "react";
import {
  DndContext,
  DragOverlay,
  type DragEndEvent,
  type DragStartEvent,
  PointerSensor,
  useDroppable,
  useDraggable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { Star } from "lucide-react";
import { LeadBadge } from "./LeadBadge";
import {
  LEAD_STATUS_LABEL,
  WEB_PRESENCE_BADGE_CN,
  WEB_PRESENCE_LABEL,
  type LeadStatus,
} from "@/lib/leadEnums";
import type { Lead } from "./types";

const COLUMNS: LeadStatus[] = ["not_sent", "sent", "accepted", "refused"];

interface Props {
  leads: Lead[];
  loading: boolean;
  onSelect: (lead: Lead) => void;
  onStatusChange: (leadId: string, next: LeadStatus) => Promise<void>;
}

// Shared card chrome — used by both the source draggable AND the
// DragOverlay ghost so the visual stays identical during drag.
function CardContent({ lead }: { lead: Lead }) {
  return (
    <>
      <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
        {lead.business_name}
      </div>
      <div className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400 truncate">
        {lead.city ?? "—"} · {lead.category ?? "—"}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <LeadBadge
          label={WEB_PRESENCE_LABEL[lead.web_presence]}
          className={WEB_PRESENCE_BADGE_CN[lead.web_presence]}
        />
        {lead.rating != null && (
          <span className="inline-flex items-center gap-0.5 text-xs text-zinc-600 dark:text-zinc-400">
            <Star className="h-3 w-3" />
            {lead.rating.toFixed(1)}
          </span>
        )}
      </div>
    </>
  );
}

const CARD_CN =
  "rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-3 cursor-grab active:cursor-grabbing select-none";

function KanbanCard({ lead, onSelect }: { lead: Lead; onSelect: (l: Lead) => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: lead.id });

  // No inline transform here — DragOverlay handles the visual drag. The
  // source card stays put as a faded placeholder so sibling cards don't
  // reflow under the cursor.
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onClick={() => {
        if (!isDragging) onSelect(lead);
      }}
      className={[
        CARD_CN,
        "hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors",
        isDragging ? "opacity-30" : "",
      ].join(" ")}
    >
      <CardContent lead={lead} />
    </div>
  );
}

function KanbanColumn({
  status,
  leads,
  onSelect,
}: {
  status: LeadStatus;
  leads: Lead[];
  onSelect: (l: Lead) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <div
      ref={setNodeRef}
      className={[
        "flex flex-col rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 min-h-[12rem] transition-colors",
        isOver ? "ring-2 ring-zinc-400 dark:ring-zinc-600 bg-zinc-100 dark:bg-zinc-800" : "",
      ].join(" ")}
    >
      <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        {LEAD_STATUS_LABEL[status]} ({leads.length})
      </div>
      <div className="space-y-2 flex-1">
        {leads.map((l) => (
          <KanbanCard key={l.id} lead={l} onSelect={onSelect} />
        ))}
        {leads.length === 0 && (
          <div className="text-xs text-zinc-400 dark:text-zinc-600 italic pt-2">(empty)</div>
        )}
      </div>
    </div>
  );
}

export function LeadKanban({ leads, loading, onSelect, onStatusChange }: Props) {
  // Tight activation distance + small delay-free pointer keeps the drag
  // glued to the cursor from the first pixel of movement.
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  // Track which card is being dragged so DragOverlay can render its ghost.
  const [activeId, setActiveId] = useState<string | null>(null);

  // Optimistic local override so the card snaps to the new column
  // immediately; parent's refresh() reconciles with the API.
  const [override, setOverride] = useState<Record<string, LeadStatus>>({});

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const leadId = String(event.active.id);
    const newStatus = event.over?.id as LeadStatus | undefined;
    if (!newStatus || !COLUMNS.includes(newStatus)) return;
    const lead = leads.find((l) => l.id === leadId);
    if (!lead) return;
    const current = override[leadId] ?? lead.lead_status;
    if (current === newStatus) return;

    setOverride((o) => ({ ...o, [leadId]: newStatus }));
    try {
      await onStatusChange(leadId, newStatus);
    } catch {
      setOverride((o) => Object.fromEntries(Object.entries(o).filter(([k]) => k !== leadId)));
    }
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {COLUMNS.map((s) => (
          <div key={s} className="h-48 rounded-xl bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }

  const effective = (l: Lead): LeadStatus => override[l.id] ?? l.lead_status;
  const byStatus: Record<LeadStatus, Lead[]> = {
    not_sent: [],
    sent: [],
    accepted: [],
    refused: [],
  };
  for (const l of leads) byStatus[effective(l)].push(l);

  const activeLead = activeId ? (leads.find((l) => l.id === activeId) ?? null) : null;

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActiveId(null)}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {COLUMNS.map((s) => (
          <KanbanColumn key={s} status={s} leads={byStatus[s]} onSelect={onSelect} />
        ))}
      </div>
      {/* Ghost card that follows the cursor while dragging. Glued to the
          pointer because DragOverlay is portal-rendered and positioned by
          dnd-kit itself — independent of grid/column reflow. */}
      <DragOverlay dropAnimation={null}>
        {activeLead ? (
          <div className={`${CARD_CN} shadow-2xl ring-2 ring-zinc-400 dark:ring-zinc-600`}>
            <CardContent lead={activeLead} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
