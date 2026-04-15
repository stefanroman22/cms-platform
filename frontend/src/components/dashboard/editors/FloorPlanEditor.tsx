"use client";

import type { EditorProps } from "./index";
import { ImageEditor } from "./ImageEditor";

export function FloorPlanEditor(props: EditorProps) {
    return <ImageEditor {...props} label="Floor plan" />;
}
