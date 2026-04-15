import type { ComponentType } from "react";

export interface EditorProps {
    initialContent: Record<string, unknown>;
    onChange: (content: Record<string, unknown>) => void;
    /** Phase 16: upload a file and receive its public URL. */
    onUpload?: (file: File) => Promise<string>;
}

// Dynamically import to keep each editor's bundle separate
export { TextBlockEditor } from "./TextBlockEditor";
export { EmailConfigEditor } from "./EmailConfigEditor";
export { ImageEditor } from "./ImageEditor";
export { FloorPlanEditor } from "./FloorPlanEditor";
export { GalleryEditor } from "./GalleryEditor";
export { VideoEditor } from "./VideoEditor";
export { FileDownloadEditor } from "./FileDownloadEditor";
export { KeyValueEditor } from "./KeyValueEditor";
export { RepeaterEditor } from "./RepeaterEditor";

import { TextBlockEditor } from "./TextBlockEditor";
import { EmailConfigEditor } from "./EmailConfigEditor";
import { ImageEditor } from "./ImageEditor";
import { FloorPlanEditor } from "./FloorPlanEditor";
import { GalleryEditor } from "./GalleryEditor";
import { VideoEditor } from "./VideoEditor";
import { FileDownloadEditor } from "./FileDownloadEditor";
import { KeyValueEditor } from "./KeyValueEditor";
import { RepeaterEditor } from "./RepeaterEditor";

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
};
