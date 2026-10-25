const video = document.querySelector("#camera");
const overlay = document.querySelector("#overlay");
const capture = document.querySelector("#capture");
const startButton = document.querySelector("#startButton");
const startLabel = document.querySelector("#startLabel");
const flipButton = document.querySelector("#flipButton");
const emptyState = document.querySelector("#emptyState");
const livePill = document.querySelector("#livePill");
const connectionText = document.querySelector("#connectionText");
const sceneText = document.querySelector("#sceneText");

const state = { stream: null, running: false, facing: "environment", busy: false, lastEvent: null, generation: 0 };

function setConnection(kind, text) {
  livePill.className = `live-pill ${kind}`;
  connectionText.textContent = text;
}

async function openCamera() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera access needs Safari/Chrome over HTTPS.");
  state.stream?.getTracks().forEach((track) => track.stop());
  state.stream = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: { facingMode: { ideal: state.facing }, width: { ideal: 640 }, height: { ideal: 480 } },
  });
  const generation = ++state.generation;
  video.srcObject = state.stream;
  await video.play();
  state.running = true;
  emptyState.classList.add("hidden");
  flipButton.disabled = false;
  startLabel.textContent = "STOP CAMERA";
  setConnection("active", "LIVE");
  requestAnimationFrame(() => drawOverlay(generation));
  detectionLoop(generation);
}

function stopCamera() {
  state.generation += 1;
  state.running = false;
  state.stream?.getTracks().forEach((track) => track.stop());
  state.stream = null;
  state.lastEvent = null;
  overlay.getContext("2d").clearRect(0,0,overlay.width,overlay.height);
  emptyState.classList.remove("hidden");
  flipButton.disabled = true;
  startLabel.textContent = "START CAMERA";
  setConnection("", "READY");
  sceneText.textContent = "Camera stopped.";
  clearCheckpoints("Camera stopped");
}

async function detectFrame() {
  const generation = state.generation;
  if (!state.running || state.busy || video.readyState < 2) return;
  state.busy = true;
  const maxWidth = 640;
  const scale = Math.min(1, maxWidth / video.videoWidth);
  capture.width = Math.max(1, Math.round(video.videoWidth * scale));
  capture.height = Math.max(1, Math.round(video.videoHeight * scale));
  capture.getContext("2d").drawImage(video, 0, 0, capture.width, capture.height);
  try {
    const blob = await new Promise((resolve) => capture.toBlob(resolve, "image/jpeg", 0.9));
    const body = new FormData();
    body.append("frame", blob, "frame.jpg");
    const heightValue=document.querySelector('#objectHeight').value;
    const fovValue=document.querySelector('#cameraFov').value;
    body.append('distance_settings', JSON.stringify({
      heights_m:heightValue ? {[document.querySelector('#sizeLabel').value.trim()]:Number(heightValue)} : {},
      horizontal_fov_deg:fovValue ? Number(fovValue) : null,
      full_height_visible:document.querySelector('#fullHeight').checked && !document.querySelector('#occluded').checked
    }));
    const response = await fetch("/api/detect", { method: "POST", body, signal: AbortSignal.timeout(60000) });
    if (!response.ok) throw new Error((await response.json()).error || `Server error ${response.status}`);
    const event = await response.json();
    if (!state.running || generation !== state.generation) return;
    state.lastEvent = event;
    updateCheckpoints(event);
    setConnection("active", "LIVE");
    sceneText.textContent = state.lastEvent.seeing;
    state.lastReceived=Date.now();
  } catch (error) {
    if (!state.running || generation !== state.generation) return;
    state.lastEvent = null;
    clearCheckpoints('No fresh camera result');
    setConnection("error", "OFFLINE");
    sceneText.textContent = error.message;
  } finally {
    state.busy = false;
  }
}

function detectionLoop(generation) {
  if (!state.running || generation !== state.generation) return;
  detectFrame().finally(() => window.setTimeout(() => detectionLoop(generation), 350));
}

function drawOverlay(generation) {
  if (!state.running || generation !== state.generation) return;
  const rect = overlay.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  overlay.width = Math.round(rect.width * dpr);
  overlay.height = Math.round(rect.height * dpr);
  const ctx = overlay.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);
  drawGrid(ctx, rect.width, rect.height, 6, 4);
  if (state.lastEvent && Date.now()-(state.lastReceived || Date.now())>10000) {state.lastEvent=null;clearCheckpoints('Waiting for fresh inference');}
  if (state.lastEvent) drawDetections(ctx, rect.width, rect.height, state.lastEvent);
  requestAnimationFrame(() => drawOverlay(generation));
}

function drawGrid(ctx, width, height, columns, rows) {
  ctx.strokeStyle = "rgba(37, 186, 243, .55)";
  ctx.fillStyle = "rgba(117, 222, 255, .9)";
  ctx.lineWidth = 1;
  ctx.font = "700 12px system-ui";
  for (let column = 1; column < columns; column++) {
    const x = column * width / columns; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
  }
  for (let row = 1; row < rows; row++) {
    const y = row * height / rows; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
  }
  for (let row = 0; row < rows; row++) for (let column = 0; column < columns; column++) {
    ctx.fillText(`${String.fromCharCode(65 + column)}${row + 1}`, column * width / columns + 7, row * height / rows + 17);
  }
}

function drawDetections(ctx, displayWidth, displayHeight, event) {
  const sourceWidth = event.frame.width_px;
  const sourceHeight = event.frame.height_px;
  const sourceRatio = sourceWidth / sourceHeight;
  const displayRatio = displayWidth / displayHeight;
  let scale, offsetX = 0, offsetY = 0;
  if (sourceRatio > displayRatio) { scale = displayWidth / sourceWidth; offsetY = (displayHeight - sourceHeight * scale) / 2; }
  else { scale = displayHeight / sourceHeight; offsetX = (displayWidth - sourceWidth * scale) / 2; }
  ctx.lineWidth = 3;
  ctx.font = "800 13px system-ui";
  for (const marker of event.checkpoints?.distance?.markers || []) {
    ctx.strokeStyle = '#5fffc8'; ctx.beginPath();
    marker.corners.forEach(([x,y],i) => i ? ctx.lineTo(x*scale+offsetX,y*scale+offsetY) : ctx.moveTo(x*scale+offsetX,y*scale+offsetY));
    ctx.closePath(); ctx.stroke();
  }
  for (const item of event.objects) {
    const [x1, y1, x2, y2] = item.box;
    const x = x1 * scale + offsetX, y = y1 * scale + offsetY, w = (x2 - x1) * scale, h = (y2 - y1) * scale;
    const label = `${item.name.toUpperCase()} · ${item.distance_m == null ? "range unavailable" : "~"+item.distance_m.toFixed(2)+" m "+(item.distance_kind === "optical_depth" ? "depth" : "range")}`;
    ctx.strokeStyle = "#ffc332"; ctx.fillStyle = "#ffc332";
    ctx.strokeRect(x, y, w, h);
    const textWidth = ctx.measureText(label).width + 16;
    ctx.fillRect(x, Math.max(0, y - 27), textWidth, 27);
    ctx.fillStyle = "#181307"; ctx.fillText(label, x + 8, Math.max(18, y - 8));
  }
}

startButton.addEventListener("click", async () => {
  if (state.running) return stopCamera();
  startButton.disabled = true;
  try { await openCamera(); }
  catch (error) { setConnection("error", "ERROR"); sceneText.textContent = error.message; }
  finally { startButton.disabled = false; }
});

flipButton.addEventListener("click", async () => {
  state.facing = state.facing === "environment" ? "user" : "environment";
  try { await openCamera(); } catch (error) { sceneText.textContent = error.message; }
});

window.addEventListener("pagehide", stopCamera);
const samples = [];
let trial = { clear: [0,0], occluded: [0,0] };
function clearCheckpoints(message) {
  document.querySelector('#detectionStatus').textContent=message;
  document.querySelector('#distanceStatus').textContent='No current measurement';
  document.querySelector('#distanceDetails').textContent='Waiting for a fresh frame.';
  document.querySelector('#distanceError').textContent='';
  document.querySelector('#liveRange').textContent='Distance: waiting for a fresh frame';
  document.querySelector('#depthPreview').hidden=true;
  document.querySelector('#objectDistances').replaceChildren();
  document.querySelector('#markerDetails').textContent='No current marker measurement.';
  document.querySelector('#pluginStatus').textContent='No fresh scene sent to adapter.';
  document.querySelector('#hapticStatus').textContent='Left 0 · Centre 0 · Right 0';
}
function updateCheckpoints(event) {
  const cp=event.checkpoints, d=cp.detection, ranges=cp.distance;
  const automatic=cp.object_distance.mode==='automatic_metric_depth';
  document.querySelector('#manualSettings').hidden=automatic;
  document.querySelector('#depthMode').textContent=automatic ? 'Automatic indoor depth · AI estimates, not sensor measurements. No height or ruler setup required.' : 'Manual mode: enter measured height and camera geometry.';
  const preview=document.querySelector('#depthPreview');preview.hidden=!cp.object_distance.preview;
  if(cp.object_distance.preview) preview.src=cp.object_distance.preview;
  document.querySelector('#depthTiming').textContent=automatic ? `Depth inference: ${cp.object_distance.inference_ms} ms · ${cp.object_distance.camera_geometry.replaceAll('_',' ')} · bright = near, dark = far (0–10 m)` : '';
  const selector=document.querySelector('#sizeLabel');
  const previous=selector.value;
  const available=[...new Set(event.objects.map(o=>o.model_label))].sort();
  if(previous && !available.includes(previous)) available.unshift(previous);
  selector.replaceChildren();
  for(const label of available) { const option=document.createElement('option');option.value=label;option.textContent=label;selector.append(option); }
  if(previous) selector.value=previous;
  if(!available.length) {const option=document.createElement('option');option.value='';option.textContent='No objects detected';selector.append(option);}

  document.querySelector('#detectionStatus').textContent=`${d.target}: ${d.status.replaceAll('_',' ')}${d.confidence == null ? '' : ` (${Math.round(d.confidence*100)}%)`}`;
  const mode=document.querySelector('#occluded').checked?'occluded':'clear';
  trial[mode][1]++; if(d.status==='detected') trial[mode][0]++;
  document.querySelector('#testCounts').textContent=`Visible: ${trial.clear[0]}/${trial.clear[1]} frames · Hand covering: ${trial.occluded[0]}/${trial.occluded[1]} frames. Presence test only; verify boxes visually.`;
  const marker=ranges.markers[0];
  document.querySelector('#markerDetails').textContent=marker ? `${marker.distance_m.toFixed(3)} m to marker #${marker.marker_id} · tilt ${marker.marker_tilt_deg.toFixed(1)}°` : ranges.status.replaceAll('_',' ');
  const list=document.querySelector('#objectDistances'); list.replaceChildren();
  for (const obj of event.objects) {
    const row=document.createElement('p');
    row.textContent=obj.distance_m == null ? `${obj.name}: ${obj.distance_status.replaceAll('_',' ')}` : `${obj.name}: ≈ ${obj.distance_m.toFixed(2)} m ${obj.distance_kind==='optical_depth'?'depth':'range'}${obj.horizontal_angle_deg == null ? '' : ` · bearing ${obj.horizontal_angle_deg.toFixed(1)}°`}${obj.depth_quality==='mixed_surfaces'?' · mixed surfaces: check box':''}`;
    list.append(row);
  }
  document.querySelector('#distanceStatus').textContent=`${cp.object_distance.estimated}/${event.objects.length} objects have a distance estimate`;
  document.querySelector('#distanceDetails').textContent=automatic ? 'Metres are learned estimates for visible surfaces. Without camera intrinsics this reports depth along the optical axis; with calibration or server FOV it reports angle-corrected range. Hidden surfaces cannot be measured.' : 'Measured height and full upright extent are required.';
  const matches=event.objects.filter(o=>o.model_label===document.querySelector('#sizeLabel').value.trim());
  const candidates=matches.filter(o=>o.distance_m != null);
  const m=automatic ? candidates.sort((a,b)=>a.distance_m-b.distance_m)[0] : candidates.length===1 ? candidates[0] : null;
  const reasons={needs_measured_height:'Enter the selected object’s measured height.', confirm_full_height_upright:'Confirm full height is visible and upright; turn off hand-covering mode.', needs_calibration_or_measured_fov:'Enter current ruler distance, then click Set distance from this reference.', ambiguous_same_label_instances:'Show only one object with this label to assign its measured height.', clipped_object:'Move the object fully inside the frame, including top and bottom.', box_too_small:'Move the object closer until its box is at least 20 pixels tall.', calibration_resolution_mismatch:'Camera resolution differs from the calibration file.'};
  document.querySelector('#liveRange').textContent=m ? `≈ ${m.distance_m.toFixed(2)} m ${m.distance_kind==='optical_depth'?'depth':'range'}${automatic && candidates.length>1 ? " · nearest "+m.name : ""}` : 'Distance: '+(matches.length ? (reasons[matches[0].distance_status] || matches[0].distance_status) : 'Selected object is not detected.');
  const truth=Number(document.querySelector('#groundTruth').value);
  document.querySelector('#distanceError').textContent=m && truth>0 ? `Absolute error: ${(Math.abs(m.distance_m-truth)*100).toFixed(1)} cm (${(100*Math.abs(m.distance_m-truth)/truth).toFixed(1)}%)` : 'Enter ruler distance and obtain one valid estimate for the selected label.';
  document.querySelector('#pluginStatus').textContent=`Scene adapter: ${cp.hardware.status.replaceAll('_',' ')}${cp.hardware.error ? ' — '+cp.hardware.error : ''}`;
  const [l,c,r]=event.haptics.channels;
  document.querySelector('#hapticStatus').textContent=`Left ${l} · Centre ${c} · Right ${r} — ${event.haptics.connection || 'preview_only'}`;
  samples.push({timestamp:event.timestamp,mode,detection:d,range:m || null,scene:{...event,checkpoints:{...event.checkpoints,object_distance:{...cp.object_distance,preview:undefined}}},ruler_m:truth>0?truth:null});
  if(samples.length>10000) samples.shift();
}
document.querySelector('#resetTest').onclick=()=>{trial={clear:[0,0],occluded:[0,0]};samples.length=0;document.querySelector('#testCounts').textContent='Trial reset.';};
document.querySelector('#exportTest').onclick=()=>{
  const url=URL.createObjectURL(new Blob([JSON.stringify(samples,null,2)],{type:'application/json'}));
  const a=document.createElement('a'); a.href=url; a.download='pulsepath-checkpoints.json'; a.click(); URL.revokeObjectURL(url);
};

document.querySelector('#snapshot').onclick=()=>{
  if (!state.lastEvent) { document.querySelector('#snapshotStatus').textContent='Start the camera and wait for a fresh result first.'; return; }
  const url=URL.createObjectURL(new Blob([JSON.stringify(state.lastEvent,null,2)],{type:'application/json'}));
  const a=document.createElement('a'); a.href=url; a.download=`pulsepath-snapshot-${Date.now()}.json`; a.click(); URL.revokeObjectURL(url);
  document.querySelector('#snapshotStatus').textContent='Saved detection, geometry inputs/results, and adapter status for this frame.';
};

document.querySelector('#calibrateDistance').onclick=async()=>{
  const message=document.querySelector('#referenceStatus');
  try {
    if(!state.running || !state.lastEvent || Date.now()/1000-state.lastEvent.timestamp>3) throw new Error('Start the camera and wait for a fresh detection.');
    if(!document.querySelector('#fullHeight').checked || document.querySelector('#occluded').checked) throw new Error('Show the full upright object and confirm full visibility first.');
    const matches=state.lastEvent.objects.filter(o=>o.model_label===document.querySelector('#sizeLabel').value);
    if(matches.length!==1) throw new Error('Show exactly one object with the selected label.');
    const response=await fetch('/api/distance-reference',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      width:state.lastEvent.frame.width_px,height:state.lastEvent.frame.height_px,box:matches[0].box,
      height_m:Number(document.querySelector('#objectHeight').value),distance_m:Number(document.querySelector('#referenceDistance').value)
    })});
    const result=await response.json();if(!response.ok) throw new Error(result.error);
    document.querySelector('#cameraFov').value=result.horizontal_fov_deg.toFixed(6);
    message.textContent='Reference set. Move the same object closer or farther: the large distance readout updates live. Keep camera zoom unchanged. Verify at a second ruler distance.';
  } catch(error) {message.textContent=error.message;}
};
// A different camera invalidates a one-point reference and any manually supplied FOV.
flipButton.addEventListener('click',()=>{document.querySelector('#cameraFov').value='';document.querySelector('#referenceStatus').textContent='Camera changed: set a new reference.';});
