# Real-photo evaluation protocol

No real-photo observations are bundled. manifest_example.csv contains explicit
placeholders. Keep private photos in private_photos/ and do not commit them.

Collect at least five distinct flat rectangular objects, three approximate
angles (top-down, moderate, strong tilt) and two lighting conditions: 30 photos.
Keep the camera fixed for this first experiment, record its model and laptop
hardware, reference size, ruler resolution, and actual short/long dimensions.
Retain failed images. Angles and lighting categories are approximate unless
measured. Repeated captures of one object are not independent object samples.

Use an object-separated development subset to adjust detection settings, then
freeze settings for an evaluation subset. Save confirmed/corrected coordinates
using the app's annotation download. For each row record method and whether
each detector's selected corners required correction. Detection success means
confirmed without correction, not merely returning a candidate. Record manual
fallback separately. Blank evidence stays undefined.

Run manual homography and assisted workflows on the same photos. The runner
uses saved confirmed corners for measurement and records automatic-stage timing
for assisted rows; annotation settings must match the frozen processing setup.
The naive global-scale baseline is optional and unsuitable for tilted photos.

The runner retains per-row failures and excludes them only from error aggregates.
Short and long sides are reported separately with signed, absolute and percentage
errors, mean/median absolute error, worst error and success counts. Detection,
assisted completion and manual fallback rates have explicit denominators.
Latency excludes upload, rendering and human work: after one warm-up per method it times
geometry and, for assisted rows, reference detection and target suggestion.
Report median, 95th percentile, sample count, image resolution and hardware.
Latency aggregates cover successful processing rows; failures remain in their
own report. Batch latency reruns algorithms on the saved confirmed corners,
while detector success/correction evidence comes from your observed workflow.
It is never inferred simply from a candidate count. Optional reference_attempted
and target_attempted columns can exclude an unattempted detector from its
denominator; assisted rows otherwise assume both were attempted. Boolean columns
accept true/false, yes/no or 1/0. Blank evidence makes the corresponding rate
undefined and records its unknown count. Assisted completion means a successful
measurement without manual fallback; fallback rate is reported independently.

Summary.json separates methods and splits, flags objects appearing in both
development/evaluation, and reports whether evaluation processing settings match.
Resolve mixed settings or split overlap before publishing a comparison.

Figures group dimension error by angle and lighting. Failure reports list reasons
and paths; sharing representative images requires the owner's approval. Do not
copy private images into a public report automatically. Results for a tiny set
are a demonstration, not a general accuracy claim. Compare actual supported
top-down/moderate results against the provisional median percentage error <=5%
and median processing <1 second at 2000px; report misses truthfully.
