# Assisted detection

Reference detection uses OpenCV 4.13's ArucoDetector with DICT_4X4_50 and subpixel
corner refinement. All returned valid markers remain available for explicit
choice. Corners are perimeter validated and normalized by the geometry module;
the resulting frame may rotate relative to the encoded marker orientation, but
side lengths are invariant. The outer black square sets physical scale.

Target suggestions use RGB-to-grayscale conversion, a 5×5 Gaussian blur,
configurable Canny edges, contours and polygon approximation. Defaults are
Canny 50/150, area ratio .005–.9 and perimeter approximation ratio .02. Candidate
area is relative to image dimensions. Convex quadrilaterals touching a margin
of max(2px, .005×short image edge) are excluded. More than 10% intersection
relative to the smaller of reference/candidate areas excludes a reference overlap.
Canny's duplicate contours are merged when intersection-over-union exceeds .85.

Ranking is sqrt(candidate area / image area) multiplied by contour-to-quad area
agreement. When a confirmed reference homography exists, this is further
multiplied by max(0,1−maximum angle deviation/90) and divided by
(1+maximum opposite-side disagreement). These are usable-area/shape heuristics,
not learned probabilities. At most 30 candidates are returned. Image-space
right angles are not required because perspective changes them. Right-angle
and opposite-side checks occur on the transformed plane.

Candidates and marker corners can be manually corrected. Selecting a suggestion
does not confirm it or measure it. Low contrast, glare or incomplete outlines
can yield no candidates; manual selection remains available. Detection success
is separate from physical measurement accuracy.
