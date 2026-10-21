# Final PDF visual review - 21 October 2026

The dashboard evidence PDF has 7 landscape A3 pages; the implementation report has 30 A4 pages. All 37 pages were rendered with Poppler. All final contact sheets were inspected, together with representative full-size pages for dense dataset tables and model-comparison figures. The evidence screenshots were also inspected directly before inclusion.

The final layout has consistent margins, page numbers, readable headings and tables, an actual table of contents, complete chapter structure and blank identity fields. No clipped content, overlapping text, invalid glyphs or unnecessary blank pages were observed. Sparse overflow pages were removed, and short result tables are kept together. Screenshots are genuine application captures, with the lower selected-model evidence recaptured to show the class report and permutation chart.

`deliverables/logs/pdf_validation.json` records final file hashes, page counts, image embedding, text extraction and page-bound checks. `tmp/pdfs` contains ignored intermediate renders/contact sheets and can be regenerated with the validation tool. The PDFs are marked binary in Git so Windows checkout conversion cannot corrupt their offsets or image streams.
