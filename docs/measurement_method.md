# From pixels to physical dimensions

A pixel location tells us where something appears in a photograph, not its
size on a table. A 50 mm square reference supplies a physical ruler. In a
top-down picture its sides might span a similar number of pixels, but in an
angled photo the far side appears smaller. One pixels-per-centimetre number
cannot correct that varying scale.

A homography is a 3×3 matrix relating two views of the same plane. Four
reference corners map to (0,0), (s,0), (s,s), (0,s), where s is the ruler-measured
black-square side in millimetres. For an image point (x,y), multiply the matrix
by (x,y,1), then divide the first two values by the third. The resulting
coordinates are positions on the plane in millimetres. Near-zero divisors are
unsafe and rejected. The numerical solve first centers and scales coordinates
so that large image offsets and physical units do not distort condition checks.

Four target corners map through this same transformation. Euclidean distances
between adjacent transformed points give four side lengths. Averaging each
opposite pair gives two estimates, sorted into short and long. A different
cyclic starting corner rotates the reference frame without changing lengths.
Crossing click order is rejected; click sequentially around the perimeter.

The interface displays centimetres rounded to one decimal, while exports retain
unrounded millimetres. Extra stored digits are useful for calculations but do
not establish precision. A rectified display uses a separate pixels-per-mm
factor and a scale bar; those display pixels are not the physical plane frame.

Validation checks the selected geometry, not the truth of the capture. A
reference smaller than 100 analysis pixels of area is rejected, and a shortest
reference edge below 40 pixels triggers a warning. Transformed target angles
more than 10 degrees from 90 or opposite sides differing by more than 10%
trigger configurable heuristic warnings. The implementation documents further
numerical guards in geometry.py. Warnings are not calibrated confidence scores.

Numerical guards: corners must be distinct beyond 1e-8 pixels, adjacent edge
cross-product sine must be at least 1e-4, the normalized DLT system's smallest
singular value must exceed 1e-10 times its largest, and normalized homography
condition must not exceed 1e10. Projection denominators must exceed 1e-10 times
the sum of absolute homogeneous denominator terms. Reference and target must
remain on the same side of the projective horizon. Physical target edges at or
below 1e-9 mm are rejected. These numerical safeguards are operating choices,
not empirical accuracy guarantees.

The reference fits its own four correspondences exactly by construction. Its
reprojection residual cannot prove target accuracy. Coplanarity and rectangularity
are capture assumptions; a single photograph cannot reliably verify them.

When ruler ground truth is supplied, signed error is estimate minus actual,
absolute error removes the sign, and percentage error divides absolute error
by actual and multiplies by 100. The ruler's own resolution and reading
uncertainty contribute to ground-truth uncertainty.
