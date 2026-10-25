# PulsePath: vision, distance and hardware checkpoints

## Current default: automatic per-object metric depth

Start the web or native demo normally. Both now default to `--distance-mode automatic`. No measured object height, ruler reference or FOV is required to produce an estimate. The previous height-based method remains an explicit manual fallback.

Pipeline: one camera frame → YOLO-World object boxes + Depth Anything V2 Metric Indoor Small depth map → median valid depth in the central 50% of each box → optional camera-ray correction → scene adapter and UI. Both models use the same frame; no previous depth map is reused. The actual metric checkpoint is required: relative depth maps must never be labelled metres. We run the official safetensors model locally, at approximately 392-pixel processing resolution, with a 0–10 m fixed heatmap legend. The model predicts up to 20 m; near-saturation outputs are rejected. The first run downloads about 100 MB of depth weights to models/huggingface; camera frames are not sent to Hugging Face.

The automatic model estimates visible-surface optical depth Z. Without camera intrinsics, the UI explicitly says **depth**. With calibration or `--horizontal-fov-deg` supplied from an actual specification, undistorted normalized image coordinates x,y give X=xZ, Y=yZ and slant range R=Z√(1+x²+y²). Calibration also supplies lens correction. Guessed camera intrinsics are never silently substituted.

This model supplies learned scene-scale priors; monocular geometry alone cannot resolve absolute scale. These are approximate estimates, not guaranteed measurements. Indoor training can misestimate scale in unfamiliar rooms, outdoor scenes, reflections, screens and small objects. An inset box is not an instance segmentation mask: hands or background may dominate it. A wide 20th–80th percentile spread produces the **mixed surfaces** flag, which is a diagnostic, not calibrated confidence. Fully hidden object surfaces cannot be recovered reliably.

**Checkpoint 1:** confirm each label and box visually. **Checkpoint 2:** verify the live depth map, metres, inference latency and mixed-surface flags. Compare against independent ruler measurements at several distances; when comparing optical depth, use distance along the camera axis, not diagonal range. **Checkpoint 3:** verify scene delivery and the board watchdog. Hardware receives nullable distance_m plus distance_kind (`optical_depth` / `slant_range`), distance_status, depth_quality and method; read these before using a value. The built-in serial output still uses calibrated markers only. No movement instructions have been restored.

Validation: automatic sampling/angle/rejection tests plus real live webcam inference. A live run returned estimates for all 10 detected boxes, with one depth inference taking 132 ms. This confirms functioning inference and display, not real-world accuracy. Test actual range errors before relying on the estimates. Monocular learned depth is the feasible automatic option with the current webcam; a calibrated stereo pair or depth sensor would supply independent metric geometry, while ArUco markers supply reliable known-size references for specific objects.

Sources: [official metric model](https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf), [official metric-depth code](https://github.com/DepthAnything/Depth-Anything-V2/tree/main/metric_depth).

## Run the laptop demo

Use Python 3.11 or 3.12. From the repository root:

```sh
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r pi/requirements-world.txt
python pi/web_server.py --model yolov8s-worldv2.pt --confidence 0.2
```

Open http://127.0.0.1:8765 and click Start Camera. Allow the browser camera prompt.
First startup downloads the detector and CLIP text encoder. The demo sends frames
only to the local server and does not save them. Current-frame boxes are yellow;
valid reference-marker outlines are green. Start without Arduino in preview mode.

### Checkpoint 1: recognition under a hand

The original COCO model lacks a drink-can class, and the original obstacle filter
excluded bottle/cup. The updated configuration adds drink can/tin can and handheld
objects; YOLO-World supplies open-vocabulary classes. Crops around detected people
provide a second inference pass for small handheld objects, with duplicate removal.
These changes are hypotheses to test, not an accuracy guarantee or trained model.

1. Hold a drink can fully visible. Verify the label and box cover the can, not your hand.
2. Reset the trial, collect at least 30 frames in each condition. Check the hand-covering
   box only while your hand really obscures part of the target. Test 15%, 30%, 50% coverage,
   rotations, different cans, backgrounds, and light. Keep false-positive examples too.
3. Compare detected-frame counts and download the measurements. These are presence counts,
   not precision/recall (there is no ground-truth bounding-box annotation in the live UI).
4. Fully hide/remove the can: no detections should be carried forward as if still seen.

A different custom detector can be selected with --model /path/to/best.pt. Its label
must match --target and the obstacle configuration. Closed-set COCO reports
unsupported_label for drink can rather than claiming success.

### Manual fallback: height-based distance (`--distance-mode manual`)

The browser displays each detected object with a distance or an explicit reason it is unavailable. Enter the exact model label and its actual measured height in metres. Confirm its full height is visible and it is upright, parallel to the image plane. For people, use their measured height only when head and feet are visible. Multiple objects with the same label are rejected because the size cannot be assigned unambiguously. The browser supports one measured label at a time; the native JSON configuration supports several labels.

Use calibrated intrinsics (recommended), or enter the camera's actual horizontal FOV at the current resolution/crop. No default FOV or average class dimensions are invented. FOV mode assumes square pixels, centred principal point and zero lens distortion. Calibration resolution mismatch disables estimates.

OpenCV undistorts the top/bottom/centre rays. For measured height H and normalized vertical span dy, Z=H/dy, X=x_normalized*Z, Y=y_normalized*Z. Displayed straight-line range is sqrt(X²+Y²+Z²), bearing atan2(X,Z), elevation atan2(Y,Z). This corrects viewing angle but cannot recover unknown object tilt or hidden extent. It estimates the bounding-box centre, not the nearest surface. Boxes under 20 pixels high or touching a frame edge are rejected. Hand-covering test mode disables size-based range.

Test with a ruler at 0.3, 0.5, 1.0 and 1.5 metres, then move to image edges. Enter the ruler distance for the single selected label and compare error. Save a diagnostic snapshot at failures; it contains input settings, boxes, ranges, reasons and hardware status. Download test measurements for the full trial. Synthetic tests do not establish real-world accuracy.

Native camera mode accepts `--distance-settings settings.json` with, for example, `{"heights_m":{"drink can":0.12},"horizontal_fov_deg":60,"full_height_visible":true}`. Those numbers are examples only: replace them with actual measurements. Disable full_height_visible whenever its assumptions fail.

### Optional calibrated metric reference range

A monocular image and a category label do not uniquely specify object size, pose,
or distance. The optional reference method uses a **measured flat ArUco marker** as a physical
reference. It measures distance to its centre, not the can centre or nearest surface.
Place the marker flat on a card beside the can. Do not bend it around the can.
No generic per-class dimensions are silently assumed.

1. Print a checkerboard with 9×6 INNER corners (10×7 squares), measure square side.
2. Stop the browser camera, then run (example: measured 25 mm squares):
   `python tools/calibrate_camera.py --square-m 0.025 --width 640 --height 480`
3. Capture at least 15 sharp, varied views with SPACE, including edges and tilts. C solves
   intrinsics and radial/tangential distortion; Q cancels. Reprojection RMS above 1.5 px
   is rejected. A low RMS alone does not prove correct physical scale.
4. `python tools/make_marker.py`; print docs/marker-0.png. Measure the BLACK outer square.
5. Restart server with `--calibration calibration.json --marker-side-m 0.05`
   only if the measured black square is exactly 50 mm. Use your measured value otherwise.
6. Use the SAME camera, focus/zoom, resolution and crop. Resolution mismatch disables range.
   Browser captures at up to 640 px wide, preserving aspect ratio. Check the actual frame
   dimensions; calibrate at that resolution if the camera supplies a different aspect ratio.
7. Place marker at ruler distances 0.3, 0.5, 1.0 and 1.5 m; test centre/edges and 0°, 30°, 60°
   tilt. Compare the reference marker range with distance measured from camera optical centre to marker centre. The UI ruler-error field instead compares the selected object. Download results.
   Choose acceptance tolerances for your hardware (suggested experiment: <=5 cm or 10%).

OpenCV IPPE square PnP uses four 2D/3D corner correspondences, camera intrinsics and lens
distortion. It estimates translation (X,Y,Z) and rotation. The display reports straight-line
range sqrt(X²+Y²+Z²), optical depth Z, bearing atan2(X,Z), vertical angle and marker tilt.
Small markers (<12 px edge), >75° tilt and >2 px reprojection error are rejected. Loss or
occlusion of the marker disables measurement; no stale range is reused. Planar pose can
still be noisy or ambiguous, especially far away; validate with a ruler. Arbitrary hidden
objects still need stereo/depth or another known geometry for reliable metric range.

## Checkpoint 3: your friend's hardware plug-in

All movement advice has been removed from both demos and the event API. Left/centre/right describe positions only. The browser server emits `pulsepath.scene.v1` scenes with timestamp, frame, objects and checkpoints. Each object includes model_label, box, distance_m (nullable), distance_status and horizontal_angle_deg. Valid size estimates also include optical_depth_m, position_m, measured_height_m, distance_method and assumptions. Frame object IDs are not persistent tracks.

Run `python pi/web_server.py --model yolov8s-worldv2.pt --hardware-plugin example_hardware:create` to try the supplied adapter. Your friend can copy pi/example_hardware.py, implement publish(scene) and close(), and select their module:factory without changing CV. The plugin receives a copy; errors are reported at checkpoint 3 without breaking vision. Delivery means the adapter accepted a call, not proof the board actuated. Keep publish nonblocking; use a bounded queue and drop stale frames. Implement a 500 ms watchdog on the board and turn outputs off in close(). A slow plugin can stall inference, so test with actual hardware before the demo.

The built-in serial bridge below deliberately uses only calibrated marker ranges. It does not actuate buzzers from approximate object heights. The custom scene adapter receives object estimates so your friend can explicitly choose how to map those and unavailable values to hardware. With no board/plugin selected, the demo works in preview mode.

Test in order: preview scenes, example adapter console, board handshake, individual channels, then unplug/disconnect and verify the watchdog. Save a snapshot at each failure to separate CV, geometry and transport issues.


Flash arduino/haptic_controller/haptic_controller.ino once. Default PWM pins are 3/5/6
for left/centre/right, USB serial 115200. Confirm wiring and buzzer type before connecting.
The sketch is for active buzzers or motor drivers; passive piezos need a tone driver.
Vibration motors require driver transistors/diodes and adequate external power.

Run server with `--serial-port auto` (exactly one recognised board), or an explicit device:
`--serial-port COM3` / `--serial-port /dev/cu.usbmodem...`. Auto selection requires a
PULSEPATH/1 handshake, so unrelated serial devices are not treated as haptic controllers.
On failure the server reports the error; restart after correcting/disconnecting the board.

Contract: host sends `HELLO\n`, board replies `PULSEPATH/1\n`. Then host sends
`P1,left,centre,right\n`, each an integer 0..255. Missing or invalid measurement sends
`P1,0,0,0\n`. Firmware turns outputs off after 500 ms without valid packets, and rejects
malformed/overflowing lines. Nearer reference -> stronger output; ±10° divides channels.
These are reference-position cues, NOT walking instructions. Slow inference may cause
intentional gaps due to the watchdog. Multiple markers combine by channel maximum.

## ImageNet training (not yet executed)

ImageNet is the dataset associated with Fei-Fei Li. Classification labels alone cannot
train localisation; use its matching object bounding-box XML annotations and images you
have permission to download. The public annotation archive was downloaded locally; 151 can XML files were extracted. Matching ImageNet photos are still missing, and training has not run. The official image-download/login page currently exposes broken server-side code; obtain legitimate image access when the site is working.

Create a JSON mapping from the verified ImageNet synset IDs in your downloaded annotations
to exact detector names (for example drink can). Do not guess IDs. Then:

```sh
python tools/prepare_imagenet.py --images /path/images --annotations /path/xml --mapping /path/mapping.json --output datasets/handheld
python tools/augment_occlusion.py datasets/handheld
python tools/train_detector.py --data datasets/handheld/data.yaml --epochs 50 --device cpu
```

The converter uses annotated boxes, verifies dimensions, splits by image-content hash
before augmentation, and rejects an empty train/validation split. Add separately annotated
real webcam clips with hands and keep entire recording sessions out of training for final
validation. Synthetic rectangular occlusion is an augmentation, not evidence of real-hand
robustness. Compare held-out clear/occluded recall and false positives before replacing
weights. ImageNet box coordinates describe image pixels, NOT real object dimensions.

## Verification

`python -m pip install pytest` then `python -m pytest -q`.
Tests cover off-axis/tilted PnP with distortion, invalid calibration/resolution, missing
markers, serial packets, unsupported labels, crop deduplication and HTTP image validation.
Synthetic geometry tests validate maths; they do not measure webcam or detector accuracy.

Sources: https://www.image-net.org/download-images.php ; https://www.image-net.org/download-bboxes ;
https://docs.ultralytics.com/models/yolo-world/ ; https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html

Local annotation preparation: datasets/imagenet/annotations/can contains 151 XML files for verified synset n02946921 (can, tin, tin can), with mapping in datasets/imagenet/can-mapping.json. Run the converter with that folder and the matching authorised images. Use --target "tin can" when testing the resulting single-class detector. Do not replace the multi-object navigation model with a can-only model without retraining the other classes too.

## Manual fallback troubleshooting and quick setup

The previous UI required an exact typed label, height, FOV and visibility confirmation. Missing any of these prevented a number. The current UI selects actual detected labels and displays the specific next action in the large distance panel.

1. Start camera and choose the object from **Object to measure**. Show only one instance of that label.
2. Enter its measured height in metres and its current straight-line ruler distance from the camera to its centre.
3. Show the entire upright object and check the full-height confirmation. Leave hand-covering test mode off.
4. Click **Set distance from this reference**. This computes approximate focal length without needing the webcam specification.
5. Move the same object nearer/farther. Read the large live estimate and verify it at a different ruler distance. Keep camera, crop, resolution, focus and zoom unchanged. Set a new reference after changing cameras.

One-point setup uses f²=(R*h/H)²-dx²-dy², with measured range R, measured object height H, pixel height h and pixel offsets dx/dy from image centre. It assumes square pixels, a centred principal point and negligible distortion. It does not replace full camera calibration. Reference distance must be measured independently; fitting the initial distance is not validation. Full calibration takes precedence when loaded.

Regression verification exercises the actual HTTP reference endpoint and detection-to-distance pipeline with deterministic boxes: a 12 cm object occupying 120 pixels at 0.60 m, then 60 pixels at 1.20 m. This verifies numerical wiring, not physical webcam accuracy.
