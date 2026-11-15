"use strict";
const $ = id => document.getElementById(id);
const fields = ["seller_name", "seller_address", "transaction_datetime", "total_amount"];
const terminal = new Set(["succeeded", "partial", "failed", "cancelled"]);
const stages = {queued:"Đang chờ xử lý",loading:"Đang nạp bộ xử lý",ocr:"Đang đọc chữ trên biên lai",extracting:"Đang trích xuất thông tin",succeeded:"Đã trích xuất thông tin",partial:"Đã có kết quả — hãy kiểm tra lại",failed:"Chưa xử lý được ảnh",cancelled:"Đã hủy",cancel_requested:"Đang dừng tác vụ an toàn"};
const reasons = {multiple_layout_blocks_check_entity:"Thông tin ghép từ nhiều vùng; hãy kiểm tra đúng người bán.",uncertain_layout:"Bố cục ảnh chưa rõ; hãy đối chiếu vùng chữ.",ambiguous_reading_order:"Thứ tự vùng chữ chưa chắc chắn.",time_missing:"Chưa xác định được giờ giao dịch; chỉ giữ ngày.",semantic_conflict:"Nhãn số tiền có cách hiểu khác nhau; hãy kiểm tra tổng tiền.",uncertain_relation:"Chưa chắc nhãn nào thuộc số tiền đã chọn.",model_abstained:"Chưa chọn được thông tin từ ảnh.",invalid_evidence:"Bằng chứng không hợp lệ; cần kiểm tra lại.",normalization_failed:"Chưa chuẩn hóa được giá trị.",partial_ocr:"Có vùng chữ chưa đọc được.",selected_overlapping_ocr_hypotheses:"Vùng chữ chồng nhau, có thể bị lặp.",overlapping_name_address_spans:"Tên và địa chỉ dùng chung đoạn chữ."};
let selectedFile = null, previewURL = null, generation = 0, latest = null, ready = false;
let idempotency = null, busy = false, activeField = null, dirty = false, maxBytes = 15*1024*1024;
let saving = null;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
function error(message) { $("error").hidden = !message; $("error").textContent = message || ""; }
async function api(path, options={}) {
  const response = await fetch(path,{credentials:"same-origin",...options});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const failure = new Error(typeof body.detail === "string" ? body.detail : "Yêu cầu không hợp lệ. Hãy kiểm tra giá trị và thử lại.");
    failure.status = response.status;
    throw failure;
  }
  return response.json();
}
function buttons() {
  $("submit").disabled = !selectedFile || busy || !ready;
  $("cancel").hidden = !busy || !latest;
  $("fields").disabled = !latest?.result || !!saving;
  $("save").disabled = !latest?.result || busy || !!saving;
  $("save").textContent = saving ? "Đang lưu…" : "Lưu bản sửa";
  $("confirm").disabled = !latest?.result || busy || !!saving || dirty || !latest?.review;
  $("download-ai").disabled = !latest?.result;
  $("download-reviewed").disabled = !latest?.review?.confirmed || dirty || !!saving;
}
function amountDisplay() {
  const text = $("total_amount").value.trim(), number = Number(text);
  $("amount-display").textContent = text && /^-?\d+$/.test(text) && Number.isSafeInteger(number) ? new Intl.NumberFormat("vi-VN").format(number) : "";
}
function clearResult() {
  saving = null;
  latest = null; activeField = null; dirty = false;
  $("review-form").reset(); $("timing").textContent = ""; $("runtime").textContent = "";
  $("result-status").textContent = "Chưa có kết quả"; $("result-status").className = "badge neutral";
  for (const field of fields) { $("status-"+field).textContent = ""; $("issue-"+field).textContent = ""; }
  $("amount-display").textContent = ""; draw(); buttons();
}
async function choose(file) {
  if (!file) return;
  const old = latest;
  generation++; busy = false; sessionStorage.removeItem("docucheck_job"); clearResult(); error("");
  if (old && !terminal.has(old.state)) api(`/api/jobs/${old.id}/cancel`,{method:"POST"}).catch(() => {});
  selectedFile = null; idempotency = null;
  if (previewURL) URL.revokeObjectURL(previewURL);
  $("preview").hidden = true; $("drop").hidden = false;
  if (file.size > maxBytes) { error("Ảnh vượt giới hạn dung lượng."); buttons(); return; }
  selectedFile = file; idempotency = crypto.randomUUID();
  previewURL = URL.createObjectURL(file); $("image").src = previewURL;
  $("drop").hidden = true; $("preview").hidden = false; $("image-note").textContent = file.name;
  $("stage").textContent = ready ? "Sẵn sàng trích xuất" : "Dịch vụ đang chuẩn bị";
  $("stage-description").textContent = "Nhấn Trích xuất thông tin để bắt đầu.";
  $("spinner").hidden = true; buttons();
}
function draw() {
  const image = $("image"), canvas = $("overlay"), ctx = canvas.getContext("2d");
  canvas.width = image.naturalWidth || 1; canvas.height = image.naturalHeight || 1;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  if (!latest?.result || !activeField) return;
  const evidence = latest.fields[activeField];
  for (const polygon of evidence?.polygons || []) {
    if (!polygon.length) continue;
    ctx.beginPath(); polygon.forEach(([x,y],i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y)); ctx.closePath();
    ctx.fillStyle = "rgba(19,106,97,.16)"; ctx.strokeStyle = "#136a61";
    ctx.lineWidth = Math.max(2,canvas.width/300); ctx.fill(); ctx.stroke();
  }
  const score = evidence?.ocr_confidence;
  $("confidence-note").textContent = `Vùng tô thuộc AI gốc. Độ tin cậy OCR: ${score == null ? "không có" : (score*100).toFixed(1)+"%"}. Đây không phải xác suất chọn đúng; bản sửa không tạo bằng chứng ảnh mới.`;
}
function fill(job) {
  const values = job.review?.values || job.result;
  $("seller_name").value = values.seller_name ?? ""; $("seller_address").value = values.seller_address ?? "";
  const [date,time] = (values.transaction_datetime || "").split("T");
  $("date").value = date || ""; $("time").value = time || "";
  $("total_amount").value = values.total_amount ?? ""; amountDisplay(); dirty = false;
  for (const field of fields) {
    const meta = job.fields[field], review = meta.status !== "ok";
    $("status-"+field).textContent = review ? "Cần kiểm tra" : "Đã trích xuất";
    $("status-"+field).className = "field-status"+(review?"":" good");
    $("issue-"+field).textContent = [...new Set(meta.issues.map(issue => reasons[issue] || "Thông tin chưa chắc chắn; hãy kiểm tra trên ảnh."))].join(" ");
  }
  $("result-status").textContent = job.review?.confirmed ? "Bạn đã xác nhận" : "Chờ bạn kiểm tra";
  $("result-status").className = "badge "+(job.review?.confirmed?"confirmed":"review");
  $("review-note").textContent = job.review?.confirmed ? "Bản sửa đã được bạn xác nhận. Kết quả AI gốc vẫn được giữ riêng." : "Kiểm tra ảnh, sửa nếu cần, rồi lưu bản sửa trước khi xác nhận.";
  const labels={ocr_seconds:"Đọc chữ",extraction_seconds:"Trích xuất",ocr_load_seconds:"Nạp OCR",qwen_load_seconds:"Nạp Qwen",queue_wait_seconds:"Chờ",submission_to_completion_seconds:"Tổng thời gian",worker_total_seconds:"Xử lý"};
  $("timing").textContent = Object.entries(job.timing || {}).map(([k,v]) => `${labels[k] || k}: ${Number(v).toFixed(2)} s`).join(" · ");
  $("runtime").textContent = `Chế độ trích xuất: ${job.mode} · GPU: ${job.gpu_policy} · Lần nạp: ${JSON.stringify(job.model_load_count || {})}`;
  buttons(); draw();
}
async function poll(id, view) {
  let failures = 0;
  while (view === generation) {
    try {
      const job = await api(`/api/jobs/${id}`);
      if (view !== generation) return;
      latest = job; failures = 0; busy = !terminal.has(job.state); $("spinner").hidden = !busy;
      $("stage").textContent = stages[job.state] || "Đang xử lý";
      $("stage-description").textContent = job.queue_position ? `Vị trí hàng đợi: ${job.queue_position}` : busy ? "Bạn có thể hủy tác vụ; bộ xử lý sẽ dừng an toàn." : "Kết quả có thể cần bạn kiểm tra và bổ sung.";
      buttons();
      if (!busy) {
        idempotency = null;
        if (job.result) { $("image").src = `/api/jobs/${id}/image`; $("drop").hidden=true; $("preview").hidden=false; fill(job); }
        else if (job.error) error(job.error.message);
        return;
      }
    } catch (err) {
      if (err.status === 404 || err.status === 401) {
        if (view !== generation) return;
        sessionStorage.removeItem("docucheck_job"); busy=false; clearResult();
        $("spinner").hidden=true; error("Tác vụ đã hết hạn hoặc không thuộc phiên này. Hãy chọn ảnh và gửi lại.");
        return;
      }
      failures++;
      if (failures >= 5) { error(err.message+" Tải lại trang để nối lại tác vụ."); return; }
    }
    await sleep(Math.min(8000,1500*2**failures));
  }
}
$("drop").addEventListener("click",() => $("file").click());
$("change").addEventListener("click",() => $("file").click());
$("file").addEventListener("change",e => {choose(e.target.files[0]); e.target.value="";});
$("drop").addEventListener("dragover",e => {e.preventDefault(); $("drop").classList.add("dragover");});
$("drop").addEventListener("dragleave",() => $("drop").classList.remove("dragover"));
$("drop").addEventListener("drop",e => {e.preventDefault(); $("drop").classList.remove("dragover"); choose(e.dataTransfer.files[0]);});
$("image").addEventListener("load",draw);
document.querySelectorAll("[data-field]").forEach(button => button.addEventListener("click",() => {activeField=button.dataset.field; draw();}));
$("submit").addEventListener("click",async () => {
  if (!selectedFile || busy) return;
  const view = ++generation; clearResult(); busy=true; buttons(); error("");
  $("spinner").hidden=false; $("stage").textContent="Đang tải ảnh lên";
  const body = new FormData(); body.append("file",selectedFile); idempotency ||= crypto.randomUUID();
  try {
    const response = await api("/api/jobs",{method:"POST",headers:{"Idempotency-Key":idempotency},body});
    if (view !== generation) {api(`/api/jobs/${response.job_id}/cancel`,{method:"POST"}).catch(()=>{});return;}
    latest={id:response.job_id,state:"queued"}; sessionStorage.setItem("docucheck_job",response.job_id); poll(response.job_id,view);
  } catch (err) { if(view===generation){busy=false; $("spinner").hidden=true; error(err.message); buttons();} }
});
$("cancel").addEventListener("click",async () => {try{await api(`/api/jobs/${latest.id}/cancel`,{method:"POST"});}catch(err){error(err.message);}});
$("fields").addEventListener("input",() => {dirty=true; $("result-status").textContent="Có thay đổi chưa lưu"; $("result-status").className="badge review"; amountDisplay(); buttons();});
function values() {
  const amount = $("total_amount").value.trim(), date=$("date").value, time=$("time").value;
  if (time && !date) throw new Error("Hãy chọn ngày trước khi nhập giờ.");
  if (amount && (!/^-?\d+$/.test(amount) || !Number.isSafeInteger(Number(amount)))) throw new Error("Tổng tiền cần là số nguyên, không nhập dấu phân cách.");
  return {seller_name:$("seller_name").value.trim()||null,seller_address:$("seller_address").value.trim()||null,
    transaction_datetime:date ? date+(time?"T"+time:"") : null,total_amount:amount?Number(amount):null};
}
async function save(confirmed) {
  if (saving || busy || !latest?.result) return;
  if (confirmed && (dirty || !latest.review)) return;
  const operation={view:generation,id:latest.id}; error("");
  try {
    const body=JSON.stringify({values:values(),revision:latest.revision,confirmed});
    saving=operation; buttons();
    const response=await api(`/api/jobs/${operation.id}/review`,{method:"PUT",headers:{"Content-Type":"application/json"},body});
    if(operation.view!==generation || latest?.id!==operation.id)return;
    latest.review=response.review;latest.revision=response.revision;fill(latest);
  } catch(err){if(operation.view===generation && latest?.id===operation.id)error(err.message);}
  finally {if(saving===operation){saving=null;buttons();}}
}
$("review-form").addEventListener("submit",e=>{e.preventDefault();save(false);});
$("confirm").addEventListener("click",()=>save(true));
async function download(version) {
  if (!latest?.result || (version === "reviewed" && (saving || dirty || !latest.review?.confirmed))) return;
  const view=generation, id=latest.id, revision=latest.revision;
  try {
    const response=await fetch(`/api/jobs/${id}/download?version=${version}`,{cache:"no-store"});
    if(!response.ok)throw new Error("Chưa có bản JSON phù hợp để tải.");
    const blob=await response.blob();
    if(view!==generation || latest?.id!==id || (version==="reviewed" && (dirty || saving || latest.revision!==revision)))return;
    const url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url;a.download=`receipt-${id}-${version}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(err){if(view===generation && latest?.id===id)error(err.message);}
}
$("download-ai").addEventListener("click",()=>download("ai"));
$("download-reviewed").addEventListener("click",()=>download("reviewed"));
async function health() {
  try {const response=await fetch("/health/ready");const status=await response.json();ready=!!status.ready;
    if(!busy&&!latest){$("stage").textContent=ready?"Sẵn sàng đọc biên lai":"Dịch vụ đang chuẩn bị";$("stage-description").textContent=status.message || (ready?"Chọn ảnh rồi nhấn Trích xuất thông tin.":"Đang kiểm tra model và điều kiện GPU; chưa chạy inference.");}buttons();
  }catch{ready=false;buttons();}
  setTimeout(health,5000);
}
async function init(){try{const config=await api("/api/session");maxBytes=config.max_bytes;$("limits").textContent=`JPG, PNG, WebP · tối đa ${Math.round(maxBytes/1024/1024)} MB`;
  $("retention").textContent=`Ảnh và kết quả được lưu tạm tối đa khoảng ${config.retention_hours} giờ.`;
  const id=sessionStorage.getItem("docucheck_job");if(id){latest={id,state:"queued"};busy=true;poll(id,generation);}health();
}catch(err){error(err.message);}}
init();
