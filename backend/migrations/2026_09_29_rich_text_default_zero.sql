-- New projects stay on legacy content (0) until the CMS Connector / Website Builder
-- agents ship the rich-text kit with every new site (ADR-0010); then flip back to 1.
alter table projects alter column rich_text_version set default 0;
