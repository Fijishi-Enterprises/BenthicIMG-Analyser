Annotation related design notes
===============================


Point columns and rows start from 0, not 1
------------------------------------------
Up until early 2020, point column values ranged from 1 to the image width in pixels, and point rows ranged from 1 to the image height. This decision was either made arbitrarily, or made with a concern of being more intuitive to less-technical users.

However, there were some bounds checks, calculations, etc. across the site which mistakenly assumed the ranges were 0 to width-1 and 0 to height-1, or passed the point locations into 0-indexed coordinate systems (Pillow images, Javascript positioning, etc.) without first converting to 0-indexing. From this, and the fact that spacer was already assuming 0-indexing instead of 1-indexing, we realized it would make life easier to change everything in CoralNet to assume 0-indexing.
