# Feedback — Lead db28078a-cbe5-4bcd-8269-c0edbf33e37c (hairdresser Samir)

Generated: 2026-05-21
Consumed (via chat): 2026-05-22 → distilled into LEARNINGS.md + structural edits to the lead-to-design-prompt skill (ai-slop-anti-patterns.md + prompt-skeleton.xml.md).

## Iterations sent to Claude Design

### Iteration 1
Inside the Home Page hero section, there is too much text, keep it more concise and shorter. In the Diensten section, make the animation on hover over services a bit more smooth, not so fast. There should be spacing (10px approx) between button "Alle diensten" and Diensten section. Also less text in Diensten section, and button "Alle diensten" should be aligned with text exactly like in Galerij Section. In the reviews section the two reviews are not aligned in same position. Make the text "Lees alle 105 reviews op Google Maps - 4.8 / 5 - 105" centered and make sure line is aligned in middle with both parts of text. In Diensten section the spacing between service description and price is too much. You need to make it clearly that all of these three (Service Name, Service Description, Service Time + Price) are grouped together and there is a clear separation between different services. In the team section again the two team member cards are not aligned. The name of the member is positioned differently between the two, also the number 01 or 02 is drawn over the line below image — that should not be the case.

### Iteration 2
Inside review section, still the two reviews are not perfectly aligned. Make it dynamic spacing, such that even if one review has more text than the other, all parts of a review are still aligned. Basically space between elements for each review is dynamically set based on the space needed between elements for the review with most text. Also spacing between text at bottom and end of section is too much, lower it. Inside Diensten section (2nd image) the time + price part of a service is too low and too close to next service — group all info for a service closer together. Inside team section (3rd image) again apply dynamic sizing for the service that barber offers. Even if description for one barber is longer, all parts of the team member card are aligned with all other cards on same row. Apply this principle same as you do it good already for the Boek button. In the hero section of the Home page, the button "Diensten" is not visible at all. Adjust the background and text color to make it visible and fit in the website theme, but not the same exact colors as the button next to it: "Boek een afspraak". Inside the reviews section of the home page, include somehow a link to the Google Maps page of the business such that the client can see all the reviews of the business.

### Iteration 3
Add tweakable controls to index.html: can you add a tweak such that I can change the screen size, to see if the website design is fully responsive to mobile, tablet etc. I want you to adjust the responsiveness. For small phone screen (iPhone SE 375) the footer is not fully visible, especially the timetable (check 1st image). Also inside services section (both home page and Diensten) when hovering over a service, because of the effect the text changes — some words move to another row. I want to keep the animation, but text should not move on hover — it makes the app look glitchy. Button "Boek een afspraak" not fully visible on small screen phone + tablet (with max width 768px). Also, on smaller screen I see that because elements do not fit correctly, the screen is scrollable horizontally, which should never be the case, no matter the layout. The UI should fully be responsive without need for horizontal scrolling of the whole web page. Also, I want a smooth animation of the header expanding/de-expanding for smaller screens, not just appear directly on screen.

## Distilled lessons (recorded in LEARNINGS.md → ## General)

- Zero horizontal scroll at any width ≥320px.
- Every primary CTA fully visible + ≥44px tappable at 375px.
- Footers + data tables reflow/stack below `sm`.
- Dev-only responsive-preview harness in the build.
- Hover animates only transform/color/opacity/shadow — never reflow text; hover ≥200ms ease-out.
- Animated mobile nav (no instant snap).
- Sibling cards/rows equal-height with aligned internal slots regardless of text length (dynamic spacing keyed to tallest item).
- Proximity grouping for compound list items; decorative numbers never overlap dividers/images.
- Centered + middle-aligned rating/review summary lines.
- Concise hero + section copy (word ceilings).
- Secondary buttons over photographic heroes need explicit, distinct, legible contrast treatment.
- Always link rating/review blocks to the Google source.

## Structural skill edits made (permanent, all future leads)

- `ai-slop-anti-patterns.md`: new "Banned layout & responsiveness failures" section.
- `prompt-skeleton.xml.md`: hardened `<motion>` (no-reflow-on-hover rule) + deliverable #10 (mobile-first hard requirements + responsive-preview harness).
