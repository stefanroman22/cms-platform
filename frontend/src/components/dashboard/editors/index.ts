import type { ComponentType } from "react";
import type { FieldFormat } from "@/components/dashboard/rich-text/ContentField";

export interface EditorProps {
  initialContent: Record<string, unknown>;
  onChange: (content: Record<string, unknown>) => void;
  /** Phase 16: upload a file and receive its public URL. */
  onUpload?: (file: File) => Promise<string>;
  /** Project has rich text enabled (rich_text_version >= 1). */
  richText?: boolean;
  /** Per-field formats from the service detail (spec section 5.7). */
  fieldFormats?: Record<string, FieldFormat>;
  /** Caller is an admin and may change field formats. */
  canEditStructure?: boolean;
}

import { TextBlockEditor } from "./TextBlockEditor";
import { EmailConfigEditor } from "./EmailConfigEditor";
import { ImageEditor } from "./ImageEditor";
import { FloorPlanEditor } from "./FloorPlanEditor";
import { GalleryEditor } from "./GalleryEditor";
import { VideoEditor } from "./VideoEditor";
import { FileDownloadEditor } from "./FileDownloadEditor";
import { KeyValueEditor } from "./KeyValueEditor";
import { RepeaterEditor } from "./RepeaterEditor";
import { ThemeEditor } from "./ThemeEditor";

export const EDITOR_MAP: Record<string, ComponentType<EditorProps>> = {
  text_block: TextBlockEditor,
  image: ImageEditor,
  gallery: GalleryEditor,
  email_config: EmailConfigEditor,
  floor_plan: FloorPlanEditor,
  video: VideoEditor,
  file_download: FileDownloadEditor,
  key_value: KeyValueEditor,
  repeater: RepeaterEditor,
  theme: ThemeEditor,
};
