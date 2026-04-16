/**
 * cms.config.ts — CMS integration config
 *
 * Place this file in the root of every client website repo.
 * It is the ONLY CMS-aware file in the project.
 *
 * Steps:
 *  1. Copy this file to cms.config.ts
 *  2. Fill in projectSlug (must match the slug in the CMS dashboard)
 *  3. List every service key and its type (must match what the admin configured)
 *  4. Run `npm run cms:sync-types` to generate TypeScript types
 */

export const cmsConfig = {
    /** The URL slug of this project in the CMS — e.g. "marios-restaurant" */
    projectSlug: "your-project-slug",

    /** Base URL of the CMS content API — no trailing slash */
    endpoint: "https://cms.romantechnologies.com/content",

    /**
     * Map of service keys to service types.
     * Keys must exactly match what the admin configured in the dashboard.
     * Types must be one of the built-in service types.
     */
    services: {
        // example — replace with real services for this project:
        hero:           "text_block",
        hero_image:     "image",
        about_section:  "text_block",
        floor_plan:     "floor_plan",
        gallery:        "gallery",
        menu_pdf:       "file_download",
        contact_video:  "video",
        contact_form:   "email_config",   // email_config is excluded from public content
        // repeater example — list of structured items:
        experience:     "repeater",       // items: [{ company, role, period, bullets[] }]
        projects_list:  "repeater",       // items: [{ name, description, tags[], url, repo }]
    },
} as const;

export type ServiceKey = keyof typeof cmsConfig.services;
export type ServiceType = (typeof cmsConfig.services)[ServiceKey];
