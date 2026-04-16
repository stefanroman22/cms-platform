// Auto-generated types for project: marios-restaurant
// Do not edit — regenerate with: npm run cms:sync-types

export interface CMSContent {
  project_slug: "marios-restaurant";
  project_name: string;
  last_updated: string | null;
  content: {
    hero: { _type: "text_block"; _label: string; title?: string; body?: string };
    hero_image: { _type: "image"; _label: string; url?: string; alt?: string };
    about_section: { _type: "text_block"; _label: string; title?: string; body?: string };
    floor_plan: { _type: "floor_plan"; _label: string; url?: string; alt?: string };
    gallery: { _type: "gallery"; _label: string; items?: string[] };
    menu_pdf: { _type: "file_download"; _label: string; url?: string; filename?: string };
    contact_video: { _type: "video"; _label: string; url?: string; poster?: string };
  };
}
