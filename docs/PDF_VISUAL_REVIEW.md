# Final PDF visual review - 21 October 2026

The dashboard evidence PDF has 7 landscape A3 pages; the implementation report has 30 A4 pages. All 37 pages were rendered with Poppler. All final contact sheets were inspected, together with representative full-size pages for dense dataset tables and model-comparison figures. The evidence screenshots were also inspected directly before inclusion.

The final layout has consistent margins, page numbers, readable headings and tables, an actual table of contents, complete chapter structure and identity fields on the cover. No clipped content, overlapping text, invalid glyphs or unnecessary blank pages were observed. Sparse overflow pages were removed, and short result tables are kept together. Screenshots are genuine application captures, with the lower selected-model evidence recaptured to show the class report and permutation chart.

`deliverables/logs/pdf_validation.json` records final file hashes, page counts, image embedding, text extraction and page-bound checks. `tmp/pdfs` contains ignored intermediate renders/contact sheets and can be regenerated with the validation tool. The PDFs are marked binary in Git so Windows checkout conversion cannot corrupt their offsets or image streams.

## Cover update - 22 October 2026

Both covers now list Bhargav Sonawane (ADT24SOCB0313, roll 9) and Chetan Bhapkar (ADT24SOCB0336, roll 11). The department, institution and faculty fields remain blank. All body pages were verified to retain identical extracted text and rendered pixels, and document navigation was preserved. The updated covers were rendered and visually inspected. See `deliverables/logs/pdf_identity_update.json` for the cover-update checks.

## Architecture, pattern-matching and faculty update - 22 October 2026

The implementation report now has a redesigned Jury 2 architecture (page 7) and corrected parallel Apriori / FP-Growth workflow (page 10), preserving the documented full-cohort experiment. Both covers include Department: School of computing and Faculty / Guide: Prof.Dr.Reena Pagare. Only the institution field remains blank. Updated covers and diagram pages were visually inspected after rendering. Page counts and navigation remain unchanged, and all other pages retain identical rendered pixels. See `deliverables/logs/pdf_architecture_update.json`.

## Institution field removal - 22 October 2026

Removed the institution field and its placeholder note from both covers. Both updated covers were rendered and visually checked; all other pages remain identical in text and rendered pixels. See `deliverables/logs/pdf_institution_removal.json`.

## Faculty typography revision - 22 October 2026

Both PDFs use embedded Times New Roman with 12 pt normal text, tables, captions and footers. Heading font sizes remain 25, 19, 12 and 10 pt as applicable. Institution fields and placeholder notes are removed. Document styling and explanatory diagrams use neutral black and gray; original analytical charts and genuine application screenshots retain their original evidence colors. The implementation report now has 35 A4 pages; the evidence document retains 7 landscape A3 pages. The table of contents and bookmarks were regenerated. All 42 pages were rendered and reviewed, with representative full-size dense pages inspected. Font, size, neutral text color, cover identity, bounds and nonempty-page checks passed. The full-cohort mining snapshot used for these reports is retained in `deliverables/report_assets/` so a later local sampled experiment cannot replace the verified findings during a formatting rebuild. See `deliverables/logs/pdf_typography_update.json`.
