-- 2026-10-11 ADR-0011: the cms-files bucket must accept sanitised SVG uploads
-- (icons/illustrations) and theme font files. Additive: keeps every type that
-- was already allowed. SVGs are rewritten by services/svg_sanitize.py before
-- they reach storage; fonts are only accepted on `theme` services.
update storage.buckets
   set allowed_mime_types = array[
     'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
     'video/mp4', 'video/webm', 'application/pdf',
     'font/woff2', 'font/woff', 'font/ttf', 'font/otf'
   ]
 where id = 'cms-files';
