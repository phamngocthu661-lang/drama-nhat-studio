/* ==============================================================================
   DRAMA NHẬT STUDIO — FRONTEND APPLICATION LOGIC (V2.0 - BATCH & CUSTOM OUTPUT)
   ============================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentMode = "single"; // "single" hoặc "batch"
  let selectedResolution = "1920x1080";
  let selectedFps = 24;
  let batchQueue = []; // [{ id, name, script_text, count, duration }]
  let currentResults = [];
  let socket = null;

  // DOM Elements
  const tabSingle = document.getElementById("tab-single");
  const tabBatch = document.getElementById("tab-batch");
  const tabAdas = document.getElementById("tab-adas");
  const singleScriptSection = document.getElementById("single-script-section");
  const batchScriptSection = document.getElementById("batch-script-section");
  const adasScriptSection = document.getElementById("adas-script-section");
  const projectNameGroup = document.getElementById("project-name-group");
  const projectNameInput = document.getElementById("script-title") || document.getElementById("project-name");
  const legacyProjectNameInput = document.getElementById("project-name");
  const channelNameInput = document.getElementById("channel-name");
  const scriptTextInput = document.getElementById("script-input") || document.getElementById("script-text");
  const legacyScriptTextInput = document.getElementById("script-text");
  const scriptStats = document.getElementById("script-stats");
  const charCountEl = document.getElementById("char-count");
  const estDurationEl = document.getElementById("est-duration");
  const estScenesEl = document.getElementById("est-scenes");
  const btnLoadSample = document.getElementById("btn-load-sample");
  const btnClearScript = document.getElementById("btn-clear-script");
  const outputDirInput = document.getElementById("output-dir");

  // Single file browse
  const singleFileInput = document.getElementById("single-file-input");
  const btnBrowseSingle = document.getElementById("btn-browse-single");

  // Batch elements
  const batchFilesInput = document.getElementById("batch-files-input");
  const btnBrowseBatch = document.getElementById("btn-browse-batch");
  const batchQueueContainer = document.getElementById("batch-queue-container");
  const queueCount = document.getElementById("queue-count");
  const queueList = document.getElementById("queue-list");
  const btnClearQueue = document.getElementById("btn-clear-queue");

  // Stock & Settings
  const stockSelect = document.getElementById("stock-select");
  const availableStockCount = document.getElementById("available-stock-count");
  const autoDeleteStock = document.getElementById("auto-delete-stock");
  const targetStockHoursInput = document.getElementById("target-stock-hours");
  const btnAutoReplenishMain = document.getElementById("btn-auto-replenish-main");
  const btnAutoReplenishModal = document.getElementById("btn-auto-replenish-modal");
  const mainReplenishMsg = document.getElementById("main-replenish-msg");
  const autoEnsureStock = document.getElementById("auto-ensure-stock");
  const cloudNoteLinkMain = document.getElementById("cloud-note-link-main");
  const cloudNoteLinkModal = document.getElementById("cloud-note-link-modal");
  const cloudNoteUrlText = document.getElementById("cloud-note-url-text");
  const cloudNoteCountMain = document.getElementById("cloud-note-count-main");
  const cloudNoteCountModal = document.getElementById("cloud-note-count-modal");
  const btnSyncCloudMain = document.getElementById("btn-sync-cloud-main");
  const btnSyncCloudModal = document.getElementById("btn-sync-cloud-modal");
  const cloudSyncMsg = document.getElementById("cloud-sync-msg");
  const bgmVolSlider = document.getElementById("bgm-vol");
  const bgmVolVal = document.getElementById("bgm-vol-val");

  // Preview Elements
  const previewContainer = document.getElementById("preview-container");
  const previewResTag = document.getElementById("preview-res-tag");
  const previewSubText = document.getElementById("preview-sub-text");
  const previewWatermarkText = document.getElementById("preview-watermark-text");

  // Control & Progress Elements
  const btnProduce = document.getElementById("btn-produce");
  const btnProduceLabel = document.getElementById("btn-produce-label");
  const progressSection = document.getElementById("progress-section");
  const progressMsg = document.getElementById("progress-msg");
  const progressPct = document.getElementById("progress-pct");
  const progressBar = document.getElementById("progress-bar");
  const progressStageName = document.getElementById("progress-stage-name");
  const progressTime = document.getElementById("progress-time");
  const deliverablesBox = document.getElementById("deliverables-box");
  const deliverablesTitle = document.getElementById("deliverables-title");

  // Deliverables Buttons
  const btnWatchVideo = document.getElementById("btn-watch-video");
  const btnOpenDir = document.getElementById("btn-open-dir");
  const btnCopySrt = document.getElementById("btn-copy-srt");
  const btnCopyChapters = document.getElementById("btn-copy-chapters");

  // Stock Modal Elements
  const btnOpenStockModal = document.getElementById("btn-open-stock-modal");
  const stockModal = document.getElementById("stock-modal");
  const btnCloseStockModal = document.getElementById("btn-close-stock-modal") || document.getElementById("btn-close-modal");
  const stockTableBody = document.getElementById("stock-table-body");
  const modalTotalStocks = document.getElementById("modal-total-stocks");
  const btnCleanupUsedStocks = document.getElementById("btn-cleanup-used-stocks");
  const btnRescanStocks = document.getElementById("btn-rescan-stocks");
  const ytUrlInput = document.getElementById("yt-url");
  const btnYtDownload = document.getElementById("btn-yt-download");
  const ytDownloadMsg = document.getElementById("yt-download-msg");

  // Folder Pickers & Stock Dir
  const btnBrowseOutputDir = document.getElementById("btn-browse-output-dir");
  const btnBrowseStockDir = document.getElementById("btn-browse-stock-dir");
  const btnModalBrowseStockDir = document.getElementById("btn-modal-browse-stock-dir");
  const btnApplyModalStockDir = document.getElementById("btn-apply-modal-stock-dir");
  const currentStookPath = document.getElementById("current-stook-path");
  const modalStookDirInput = document.getElementById("modal-stook-dir-input");

  // License Elements
  const btnOpenLicenseModal = document.getElementById("btn-open-license-modal");
  const licenseBadgeText = document.getElementById("license-badge-text");
  const licenseModal = document.getElementById("license-modal");
  const btnCloseLicenseModal = document.getElementById("btn-close-license-modal");
  const licenseHwidText = document.getElementById("license-hwid-text");
  const btnCopyHwid = document.getElementById("btn-copy-hwid");
  const licModalStatus = document.getElementById("lic-modal-status");
  const licModalPlan = document.getElementById("lic-modal-plan");
  const licModalExpiry = document.getElementById("lic-modal-expiry");
  const licenseKeyInput = document.getElementById("license-key-input");
  const btnActivateLicense = document.getElementById("btn-activate-license");
  const licenseModalMsg = document.getElementById("license-modal-msg");
  let isLicenseValid = false;

  // Init App
  initApp();

  async function initApp() {
    setupLicenseSystem();
    setupModeTabs();
    setupSingleFileLoader();
    setupBatchUploader();
    setupFolderPickers();
    setupResolutionSelectors();
    setupFpsSelectors();
    setupLivePreviewListeners();
    setupStockModal();
    setupProductionTrigger();
    setupChatGPTAndADASSystem();
    setupTelemetryPolling();
    await checkLicenseStatus();
    await loadConfig();
    await loadStocks();
    connectWebSocket();
  }

  // 1. Setup 4-Tab Studio Navigation & Mode Tabs
  function switchStudioTab(targetTabId) {
    if (!targetTabId) return;
    const actualPaneId = targetTabId === "tab-voice-stock" ? "tab-render" : targetTabId;
    if (targetTabId !== "tab-voice-stock") {
      window.scrollTo({ top: 0, behavior: "instant" });
    }
    document.querySelectorAll(".tab-pane").forEach((pane) => {
      if (pane.id === actualPaneId) {
        pane.style.display = "flex";
        pane.classList.remove("hidden");
        pane.classList.add("active");
      } else {
        pane.style.display = "none";
        pane.classList.add("hidden");
        pane.classList.remove("active");
      }
    });

    if (targetTabId === "tab-voice-stock") {
      const stockSec = document.getElementById("card-stock-section");
      if (stockSec) {
        setTimeout(() => stockSec.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
      }
    }

    document.querySelectorAll(".main-tab-btn").forEach((btn) => {
      const btnTarget = btn.dataset.tabTarget || btn.dataset.target;
      if (btnTarget === targetTabId) {
        btn.classList.add("active", "bg-surface-container", "text-primary-container", "border-b-2", "border-primary-container", "font-bold", "shadow-sm");
        btn.classList.remove("text-on-surface-variant", "border-transparent", "font-medium", "font-semibold");
      } else {
        btn.classList.remove("active", "bg-surface-container", "text-primary-container", "border-b-2", "border-primary-container", "font-bold", "shadow-sm");
        btn.classList.add("text-on-surface-variant", "border-transparent", "font-semibold");
      }
    });

    document.querySelectorAll(".quick-tab-jump").forEach((pill) => {
      const pillTarget = pill.dataset.tabTarget || pill.dataset.target || pill.dataset.jump;
      const dot = pill.querySelector(".sub-dot");
      if (pillTarget === targetTabId) {
        pill.className = "quick-tab-jump px-3 py-1.5 rounded-lg bg-primary-container/10 border border-primary-container/40 text-primary-container font-headline font-bold text-xs flex items-center gap-2 shadow-[0_0_12px_rgba(0,230,118,0.12)] transition-all";
        if (dot) dot.classList.remove("hidden");
      } else {
        pill.className = "quick-tab-jump px-3 py-1.5 rounded-lg bg-surface-container-low/60 hover:bg-surface-container border border-outline-variant/20 text-on-surface-variant hover:text-on-surface font-headline font-medium text-xs flex items-center gap-2 transition-all";
        if (dot) dot.classList.add("hidden");
      }
    });

    if (actualPaneId === "tab-render") {
      if (batchQueue.length > 0 && (!scriptTextInput || !scriptTextInput.value.trim())) {
        currentMode = "batch";
        updateBatchButtonLabel();
      } else {
        currentMode = "single";
        if (btnProduceLabel) {
          btnProduceLabel.innerText = "BẮT ĐẦU SẢN XUẤT 1-CLICK";
        }
      }
    }
  }

  function setupModeTabs() {
    document.querySelectorAll(".main-tab-btn, .quick-tab-jump").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.dataset.tabTarget || btn.dataset.target || btn.dataset.jump;
        if (target) switchStudioTab(target);
      });
    });

    const btnHeaderTerminal = document.getElementById("btn-header-terminal");
    if (btnHeaderTerminal) {
      btnHeaderTerminal.addEventListener("click", () => {
        switchStudioTab("tab-diagnostics");
        const cmdInput = document.getElementById("terminal-quick-input");
        if (cmdInput) setTimeout(() => cmdInput.focus(), 100);
      });
    }

    if (tabSingle) {
      tabSingle.addEventListener("click", () => {
        currentMode = "single";
        tabSingle.className = "mode-tab active px-3 py-1.5 rounded-md bg-primary-container/15 text-primary-container border border-primary-container/40 text-[11px] font-headline font-bold flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(0,230,118,0.15)]";
        if (tabBatch) {
          tabBatch.className = "mode-tab px-3 py-1.5 rounded-md text-on-surface-variant text-[11px] font-headline font-semibold hover:text-on-surface hover:bg-surface-container-low/50 flex items-center gap-1.5 transition-all border border-transparent";
        }
        if (tabAdas) tabAdas.classList.remove("active");
        if (singleScriptSection) {
          singleScriptSection.style.display = "flex";
          singleScriptSection.classList.remove("hidden");
        }
        if (batchScriptSection) {
          batchScriptSection.style.display = "none";
          batchScriptSection.classList.add("hidden");
        }
        if (projectNameGroup) projectNameGroup.style.display = "block";
        if (btnProduceLabel) btnProduceLabel.innerText = "XUẤT VIDEO HOÀN CHỈNH (FFMPEG NVENC GPU)";
      });
    }

    if (tabBatch) {
      tabBatch.addEventListener("click", () => {
        currentMode = "batch";
        tabBatch.className = "mode-tab active px-3 py-1.5 rounded-md bg-primary-container/15 text-primary-container border border-primary-container/40 text-[11px] font-headline font-bold flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(0,230,118,0.15)]";
        if (tabSingle) {
          tabSingle.className = "mode-tab px-3 py-1.5 rounded-md text-on-surface-variant text-[11px] font-headline font-semibold hover:text-on-surface hover:bg-surface-container-low/50 flex items-center gap-1.5 transition-all border border-transparent";
        }
        if (tabAdas) tabAdas.classList.remove("active");
        if (singleScriptSection) {
          singleScriptSection.style.display = "none";
          singleScriptSection.classList.add("hidden");
        }
        if (batchScriptSection) {
          batchScriptSection.style.display = "block";
          batchScriptSection.classList.remove("hidden");
        }
        if (projectNameGroup) projectNameGroup.style.display = "none";
        updateBatchButtonLabel();
      });
    }

    const btnToggleAdas = document.getElementById("btn-toggle-adas-body");
    if (btnToggleAdas && adasScriptSection) {
      btnToggleAdas.addEventListener("click", () => {
        const isHidden = adasScriptSection.style.display === "none";
        adasScriptSection.style.display = isHidden ? "block" : "none";
        btnToggleAdas.innerText = isHidden ? "🔽 Thu gọn / Mở rộng" : "▶️ Mở rộng Trạm AI";
      });
    }
  }

  function updateBatchButtonLabel() {
    if (!btnProduceLabel) return;
    if (currentMode === "batch") {
      btnProduceLabel.innerText = batchQueue.length > 0
        ? `CHẠY HÀNG LOẠT (${batchQueue.length} KỊCH BẢN - FFMPEG NVENC GPU)`
        : "XUẤT VIDEO HOÀN CHỈNH (FFMPEG NVENC GPU)";
    } else {
      btnProduceLabel.innerText = "XUẤT VIDEO HOÀN CHỈNH (FFMPEG NVENC GPU)";
    }
  }

  // 2. Single File Loader & Sample/Clear Buttons
  function setupSingleFileLoader() {
    if (btnBrowseSingle && singleFileInput) {
      btnBrowseSingle.addEventListener("click", () => singleFileInput.click());
      singleFileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
          currentMode = "single";
          if (scriptTextInput) {
            scriptTextInput.value = event.target.result;
            scriptTextInput.dispatchEvent(new Event("input"));
          }
          if (legacyScriptTextInput && legacyScriptTextInput !== scriptTextInput) {
            legacyScriptTextInput.value = event.target.result;
          }
          const baseName = file.name.replace(/\.[^/.]+$/, "");
          if (projectNameInput) projectNameInput.value = baseName;
          if (legacyProjectNameInput && legacyProjectNameInput !== projectNameInput) {
            legacyProjectNameInput.value = baseName;
          }
          updateBatchButtonLabel();
        };
        reader.readAsText(file, "utf-8");
      });
    }

    if (btnLoadSample && scriptTextInput) {
      btnLoadSample.addEventListener("click", () => {
        currentMode = "single";
        const sampleScript = [
          "定年退職の日、夫は「お前とは別に暮らす」と冷たく言い放った。",
          "三十年間、家族のために尽くしてきた私に突きつけられたのは、一枚の離婚届だった。",
          "だが、私が静かに差し出した三十年前の家計ノートを開いた瞬間、夫の顔から血の気が引いていった。",
          "そこには、夫が忘れていたある重大な秘密と、毎月振り込まれ続けていた謎の口座記録が残されていたのだ。"
        ].join("\n");
        scriptTextInput.value = sampleScript;
        if (projectNameInput && !projectNameInput.value.trim()) {
          projectNameInput.value = "K1_DRAMA_SAMPLE";
        }
        scriptTextInput.dispatchEvent(new Event("input"));
        updateBatchButtonLabel();
      });
    }

    if (btnClearScript && scriptTextInput) {
      btnClearScript.addEventListener("click", () => {
        scriptTextInput.value = "";
        scriptTextInput.dispatchEvent(new Event("input"));
      });
    }
  }

  // 3. Batch Uploader & Queue Management
  function setupBatchUploader() {
    if (btnBrowseBatch && batchFilesInput) {
      btnBrowseBatch.addEventListener("click", () => batchFilesInput.click());
      batchFilesInput.addEventListener("change", async (e) => {
        const files = Array.from(e.target.files);
        if (files.length === 0) return;

        for (const file of files) {
          const text = await readFileAsText(file);
          const name = file.name.replace(/\.[^/.]+$/, "");
          const sentences = text.split("\n").filter(l => l.trim().length > 0);

          batchQueue.push({
            id: `job_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
            name: name,
            script_text: text,
            sentences_count: sentences.length
          });
        }

        currentMode = "batch";
        renderBatchQueue();
        updateBatchButtonLabel();
        batchFilesInput.value = "";
      });
    }

    if (btnClearQueue) {
      btnClearQueue.addEventListener("click", () => {
        batchQueue = [];
        currentMode = "single";
        renderBatchQueue();
        updateBatchButtonLabel();
      });
    }
  }

  function readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsText(file, "utf-8");
    });
  }

  function renderBatchQueue() {
    if (!batchQueueContainer || !queueCount || !queueList) return;
    if (batchQueue.length === 0) {
      batchQueueContainer.style.display = "none";
      return;
    }

    batchQueueContainer.style.display = "block";
    queueCount.innerText = batchQueue.length;
    queueList.innerHTML = "";

    batchQueue.forEach((job, idx) => {
      const item = document.createElement("div");
      item.className = "queue-item";
      item.innerHTML = `
        <div>
          <span style="color: var(--accent-green); font-weight: 700; margin-right: 6px;">#${idx+1}</span>
          <span class="queue-item-name">${job.name}</span>
          <span class="queue-item-meta">(${job.sentences_count} câu)</span>
        </div>
        <button type="button" class="queue-item-del" data-idx="${idx}">&times;</button>
      `;
      queueList.appendChild(item);
    });

    // Sự kiện xóa từng item
    document.querySelectorAll(".queue-item-del").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.idx);
        batchQueue.splice(idx, 1);
        if (batchQueue.length === 0) currentMode = "single";
        renderBatchQueue();
        updateBatchButtonLabel();
      });
    });
  }

  // 3b. Setup Folder Pickers (Thư mục lưu thành phẩm & Kho Stock)
  function setupFolderPickers() {
    // 1. Nút chọn thư mục lưu thành phẩm
    if (btnBrowseOutputDir) {
      btnBrowseOutputDir.addEventListener("click", async () => {
        btnBrowseOutputDir.disabled = true;
        const originalText = btnBrowseOutputDir.innerText;
        btnBrowseOutputDir.innerText = "⏳ Đang mở hộp thoại...";
        try {
          const res = await fetch("/api/browse-directory", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "Chọn Thư Mục Lưu Video Thành Phẩm" })
          });
          const data = await res.json();
          if (data && data.path) {
            outputDirInput.value = data.path;
          }
        } catch (e) {
          console.error("Lỗi khi chọn thư mục lưu:", e);
          alert("Không thể mở hộp thoại chọn thư mục: " + e.message);
        } finally {
          btnBrowseOutputDir.disabled = false;
          btnBrowseOutputDir.innerText = originalText;
        }
      });
    }

    // 2. Nút chọn kho stock ngoài màn hình chính
    if (btnBrowseStockDir) {
      btnBrowseStockDir.addEventListener("click", async () => {
        await pickAndChangeStockDir(btnBrowseStockDir, "📂 Chọn Kho Stock");
      });
    }

    // 3. Nút chọn kho stock trong Modal
    if (btnModalBrowseStockDir) {
      btnModalBrowseStockDir.addEventListener("click", async () => {
        await pickAndChangeStockDir(btnModalBrowseStockDir, "📂 Duyệt Thư Mục...");
      });
    }

    // 4. Nút Áp Dụng đường dẫn kho stock gõ tay/dán trong Modal
    if (btnApplyModalStockDir && modalStookDirInput) {
      btnApplyModalStockDir.addEventListener("click", async () => {
        const customPath = modalStookDirInput.value.trim();
        if (!customPath) {
          alert("Vui lòng nhập hoặc dán đường dẫn thư mục Kho Stock!");
          return;
        }
        await applyNewStockDirectory(customPath);
      });

      modalStookDirInput.addEventListener("keydown", async (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          const customPath = modalStookDirInput.value.trim();
          if (customPath) {
            await applyNewStockDirectory(customPath);
          }
        }
      });
    }
  }

  async function pickAndChangeStockDir(btnElement, originalText) {
    if (btnElement) {
      btnElement.disabled = true;
      btnElement.innerText = "⏳ Đang mở...";
    }
    try {
      const res = await fetch("/api/browse-directory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Chọn Thư Mục Chứa Video Stock Nền" })
      });
      const data = await res.json();
      if (data && data.path) {
        await applyNewStockDirectory(data.path);
      }
    } catch (e) {
      console.error("Lỗi chọn kho stock:", e);
      alert("Lỗi khi mở chọn kho stock: " + e.message);
    } finally {
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.innerText = originalText;
      }
    }
  }

  async function applyNewStockDirectory(newPath) {
    try {
      const res = await fetch("/api/stocks/set-directory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory: newPath })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        await loadStocks();
        alert(`✅ Đã chuyển sang kho Stock mới thành công!\n📁 Đường dẫn: ${newPath}\n📊 Tổng cộng: ${data.data.total} video (${data.data.available_count} khả dụng)`);
      } else {
        alert("❌ Lỗi chuyển kho stock: " + (data.detail || "Thư mục không tồn tại hoặc không hợp lệ"));
      }
    } catch (e) {
      alert("❌ Lỗi kết nối khi cập nhật kho stock: " + e.message);
    }
  }

  // 4. Load Config từ Backend
  async function loadConfig() {
    try {
      const res = await fetch("/api/config");
      const data = await res.json();
      if (data.gpu_name) {
        const gpuEl = document.getElementById("gpu-name");
        if (gpuEl) gpuEl.innerText = data.gpu_name;
      }
      if (data.default_output_dir && outputDirInput && !outputDirInput.value) {
        outputDirInput.value = data.default_output_dir;
      }
    } catch (e) {
      console.warn("Không thể tải config:", e);
    }
  }

  // 5. Resolution & FPS
  function setupResolutionSelectors() {
    const btns = document.querySelectorAll("#resolution-grid .select-btn, #resolution-grid .res-card");
    btns.forEach(btn => {
      btn.addEventListener("click", () => {
        btns.forEach(b => {
          b.classList.remove("active", "border-2", "border-primary-container", "bg-primary-container/10", "shadow-[0_0_15px_rgba(0,230,118,0.12)]");
          b.classList.add("border", "border-outline-variant/25", "bg-surface-container");
          const dot = b.querySelector(".res-dot");
          if (dot) dot.className = "res-dot w-2 h-2 rounded-full bg-outline-variant/40";
        });
        btn.classList.add("active", "border-2", "border-primary-container", "bg-primary-container/10", "shadow-[0_0_15px_rgba(0,230,118,0.12)]");
        btn.classList.remove("border", "border-outline-variant/25", "bg-surface-container");
        const activeDot = btn.querySelector(".res-dot");
        if (activeDot) activeDot.className = "res-dot w-2 h-2 rounded-full bg-primary-container shadow-[0_0_6px_#00e676]";
        selectedResolution = btn.dataset.res;
        updatePreviewDimensions();
      });
    });
  }

  function setupFpsSelectors() {
    const pills = document.querySelectorAll("#fps-pills .pill-btn, #fps-pills .pill");
    pills.forEach(pill => {
      pill.addEventListener("click", () => {
        pills.forEach(p => {
          p.classList.remove("active", "border-2", "border-secondary-container", "bg-secondary-container/10", "shadow-[0_0_15px_rgba(0,210,255,0.12)]");
          p.classList.add("border", "border-outline-variant/25", "bg-surface-container");
        });
        pill.classList.add("active", "border-2", "border-secondary-container", "bg-secondary-container/10", "shadow-[0_0_15px_rgba(0,210,255,0.12)]");
        pill.classList.remove("border", "border-outline-variant/25", "bg-surface-container");
        selectedFps = parseInt(pill.dataset.fps);
        updatePreviewDimensions();
      });
    });
  }

  function updatePreviewDimensions() {
    if (previewResTag) {
      previewResTag.innerText = `${selectedResolution} @ ${selectedFps}FPS`;
    }
    const specRes = document.getElementById("spec-res");
    if (specRes) specRes.innerText = selectedResolution;
    const specFps = document.getElementById("spec-fps");
    if (specFps) specFps.innerText = `${selectedFps} FPS`;

    const resPill = document.getElementById("preview-spec-res-pill");
    if (resPill) {
      const labelMap = {
        "1920x1080": "1920x1080 (Full HD)",
        "1280x720": "1280x720 (HD)",
        "2560x1440": "2560x1440 (2K QHD)",
        "3840x2160": "3840x2160 (4K UHD)",
        "1080x1920": "1080x1920 (Shorts 9:16)"
      };
      resPill.innerText = labelMap[selectedResolution] || selectedResolution;
    }
    const fpsPill = document.getElementById("preview-spec-fps-pill");
    if (fpsPill) {
      fpsPill.innerText = `${selectedFps} FPS`;
    }
    const masterTag = document.getElementById("preview-master-tag");
    if (masterTag) {
      masterTag.innerText = selectedResolution === "1080x1920" ? "SHORTS 9:16 • MASTER" : "16:9 • MASTER";
    }

    if (previewContainer) {
      if (selectedResolution === "1080x1920") {
        previewContainer.style.aspectRatio = "9 / 16";
        previewContainer.style.maxHeight = "480px";
        previewContainer.style.margin = "0 auto";
      } else {
        previewContainer.style.aspectRatio = "16 / 9";
        previewContainer.style.maxHeight = "none";
      }
    }
  }

  // 6. Live Preview & 5-Layer Timeline Playback Controller
  let previewSentencesList = [
    "定年退職の日、夫は「お前とは別に暮らす」と冷たく言い放った。",
    "三十年間、家族のために尽くしてきた私に突きつけられたのは、一枚の離婚届だった。",
    "だが、私が静かに差し出した三十年前の家計ノートを開いた瞬間、夫の顔から血の気が引いていった。",
    "そこには、夫が忘れていたある重大な秘密と、毎月振り込まれ続けていた謎の口座記録が残されていたのだ。"
  ];
  let previewCurrentIdx = 0;
  let previewTotalEstSec = 1390;
  let previewPlayInterval = null;

  function formatSecToTimecode(sec, includeFrames = false) {
    const s = Math.max(0, Math.floor(sec || 0));
    const hh = String(Math.floor(s / 3600)).padStart(2, "0");
    const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const ss = String(s % 60).padStart(2, "0");
    if (includeFrames) {
      const ff = String((s * 7) % (selectedFps || 24)).padStart(2, "0");
      return `${hh}:${mm}:${ss}:${ff}`;
    }
    return `${hh}:${mm}:${ss}`;
  }

  function renderPreviewTimelinePosition(idx) {
    const total = Math.max(1, previewSentencesList.length);
    previewCurrentIdx = Math.max(0, Math.min(total - 1, idx));
    const curSentence = previewSentencesList[previewCurrentIdx] || "";
    if (previewSubText && curSentence) {
      previewSubText.innerText = curSentence;
    }
    const pct = total > 1 ? Math.round(((previewCurrentIdx + 1) / total) * 100) : 18;
    const curSec = Math.round((pct / 100) * previewTotalEstSec);

    const scrubFill = document.getElementById("preview-scrub-fill");
    const scrubThumb = document.getElementById("preview-scrub-thumb");
    const recTimer = document.getElementById("preview-rec-timer");
    const timeCur = document.getElementById("preview-time-cur");
    const timeTotal = document.getElementById("preview-time-total");
    const sceneBadge = document.getElementById("preview-scene-badge");
    const segCounter = document.getElementById("preview-segment-counter");

    if (scrubFill) scrubFill.style.width = `${pct}%`;
    if (scrubThumb) scrubThumb.style.left = `${pct}%`;
    if (recTimer) recTimer.innerText = formatSecToTimecode(curSec, true);
    if (timeCur) timeCur.innerText = formatSecToTimecode(curSec, false);
    if (timeTotal) timeTotal.innerText = formatSecToTimecode(previewTotalEstSec, false);
    if (sceneBadge) {
      sceneBadge.innerText = `SCENE #${String(previewCurrentIdx + 1).padStart(3, "0")} / ${String(total).padStart(3, "0")}`;
    }
    if (segCounter) {
      segCounter.innerText = `Câu #${previewCurrentIdx + 1} / ${total}`;
    }
  }

  function setupLivePreviewListeners() {
    if (channelNameInput && previewWatermarkText) {
      previewWatermarkText.innerText = channelNameInput.value.trim() || ".";
      channelNameInput.addEventListener("input", () => {
        previewWatermarkText.innerText = channelNameInput.value.trim() || ".";
      });
    }

    // 5-Layer Visibility Toggles
    document.querySelectorAll(".preview-layer-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const rawLayer = btn.dataset.layer || "1";
        const layerId = rawLayer.startsWith("preview-layer-") ? rawLayer : `preview-layer-${rawLayer}`;
        const layerEl = document.getElementById(layerId);
        if (!layerEl) return;
        const isHidden = layerEl.style.opacity === "0";
        layerEl.style.opacity = isHidden ? "" : "0";
        btn.style.opacity = isHidden ? "1" : "0.4";
      });
    });

    // Timeline Prev / Next / Play / Scrub / Fullscreen
    const btnPrevScene = document.getElementById("btn-preview-prev-scene");
    const btnNextScene = document.getElementById("btn-preview-next-scene");
    const btnPlayToggle = document.getElementById("btn-preview-play-toggle");
    const playIcon = document.getElementById("preview-play-icon");
    const scrubBar = document.getElementById("preview-scrub-bar");
    const btnFullscreen = document.getElementById("btn-preview-fullscreen");

    if (btnPrevScene) {
      btnPrevScene.addEventListener("click", () => {
        renderPreviewTimelinePosition(previewCurrentIdx - 1);
      });
    }
    if (btnNextScene) {
      btnNextScene.addEventListener("click", () => {
        renderPreviewTimelinePosition(previewCurrentIdx + 1);
      });
    }
    if (btnPlayToggle) {
      btnPlayToggle.addEventListener("click", () => {
        if (previewPlayInterval) {
          clearInterval(previewPlayInterval);
          previewPlayInterval = null;
          if (playIcon) playIcon.innerText = "play_arrow";
        } else {
          if (playIcon) playIcon.innerText = "pause";
          previewPlayInterval = setInterval(() => {
            const nextIdx = (previewCurrentIdx + 1) % Math.max(1, previewSentencesList.length);
            renderPreviewTimelinePosition(nextIdx);
          }, 2200);
        }
      });
    }
    if (scrubBar) {
      scrubBar.addEventListener("click", (e) => {
        const rect = scrubBar.getBoundingClientRect();
        if (!rect.width) return;
        const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const targetIdx = Math.floor(ratio * Math.max(1, previewSentencesList.length - 1));
        renderPreviewTimelinePosition(targetIdx);
      });
    }
    if (btnFullscreen && previewContainer) {
      btnFullscreen.addEventListener("click", () => {
        if (!document.fullscreenElement) {
          previewContainer.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
      });
    }

    if (scriptTextInput) {
      let debounceTimer = null;
      scriptTextInput.addEventListener("input", () => {
        const rawText = scriptTextInput.value;
        const text = rawText.trim();
        if (text) currentMode = "single";
        if (legacyScriptTextInput && legacyScriptTextInput !== scriptTextInput) {
          legacyScriptTextInput.value = rawText;
        }
        if (charCountEl) {
          charCountEl.innerText = `${text.length.toLocaleString()}`;
        }

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          if (!text) {
            if (scriptStats) scriptStats.innerText = "0 câu | ~00:00";
            if (estDurationEl) estDurationEl.innerText = "~00:00";
            if (estScenesEl) estScenesEl.innerText = "0";
            return;
          }

          try {
            const res = await fetch("/api/preview-script", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ script_text: text })
            });
            const data = await res.json();
            if (scriptStats) {
              scriptStats.innerText = `${data.sentence_count} câu | ~${data.estimated_formatted}`;
            }
            if (estDurationEl) {
              estDurationEl.innerText = `~${data.estimated_formatted}`;
            }
            if (estScenesEl) {
              estScenesEl.innerText = `${data.sentence_count}`;
            }
            if (data.estimated_seconds) {
              previewTotalEstSec = data.estimated_seconds;
            }
            if (data.sample_sentences && data.sample_sentences.length > 0 && previewSubText) {
              previewSubText.innerHTML = data.sample_sentences.slice(0, 2).join("<br>");
            }
          } catch (e) {
            console.error(e);
          }
        }, 300);
      });
    }

    // Bidirectional BGM Volume Sliders (Tab 2 #bgm-vol-render <-> Tab 3 #bgm-vol)
    const bgmVolRender = document.getElementById("bgm-vol-render");
    const bgmVolLabelRender = document.getElementById("bgm-vol-label-render");
    const bgmVolLabelTab3 = document.getElementById("bgm-vol-label");

    function syncBgmVolumeUI(rawVal) {
      const num = parseFloat(rawVal);
      const pct = num <= 1.0 ? Math.round(num * 100) : Math.round(num);
      const floatVal = (pct / 100).toFixed(2);
      if (bgmVolSlider) {
        const max1 = parseFloat(bgmVolSlider.max || "1");
        bgmVolSlider.value = max1 <= 1.0 ? floatVal : String(pct);
      }
      if (bgmVolRender) {
        const max2 = parseFloat(bgmVolRender.max || "1");
        bgmVolRender.value = max2 <= 1.0 ? floatVal : String(pct);
      }
      if (bgmVolVal) bgmVolVal.innerText = `${pct}%`;
      if (bgmVolLabelTab3) bgmVolLabelTab3.innerText = `${pct}%`;
      if (bgmVolLabelRender) bgmVolLabelRender.innerText = `${pct}%`;
    }

    if (bgmVolSlider) {
      bgmVolSlider.addEventListener("input", () => syncBgmVolumeUI(bgmVolSlider.value));
    }
    if (bgmVolRender) {
      bgmVolRender.addEventListener("input", () => syncBgmVolumeUI(bgmVolRender.value));
    }
  }

  // 7. Quản lý kho Stock
  async function loadStocks() {
    try {
      const res = await fetch("/api/stocks");
      const data = await res.json();

      const availFiles = data.available_count || 0;
      const availUses = data.available_uses_count !== undefined ? data.available_uses_count : availFiles;
      const rawHours = data.available_raw_hours !== undefined ? data.available_raw_hours : 0;
      const targetHrs = data.target_stock_hours || (targetStockHoursInput ? parseFloat(targetStockHoursInput.value) || 30 : 30);
      if (targetStockHoursInput && data.target_stock_hours) {
        targetStockHoursInput.value = data.target_stock_hours;
        updateReplenishButtonLabels(data.target_stock_hours);
      }
      if (availableStockCount) {
        availableStockCount.innerText = `${availFiles} file (${rawHours}h gốc • ${availUses} lượt xuất)`;
      }
      if (modalTotalStocks) {
        modalTotalStocks.innerText = data.deleted_count && data.deleted_count > 0
          ? `${data.total || 0} file — ${rawHours}h gốc • ${availUses} lượt khả dụng`
          : `${data.total || 0} file (${rawHours}h gốc • ${availUses} lượt khả dụng)`;
      }

      // Cập nhật hiển thị đường dẫn kho stock hiện tại
      if (data.current_stook_dir) {
        if (currentStookPath) currentStookPath.innerText = data.current_stook_dir;
        if (modalStookDirInput) modalStookDirInput.value = data.current_stook_dir;
      }

      // Cập nhật thông tin Note Online chống trùng đa máy
      if (data.used_links_count !== undefined) {
        if (cloudNoteCountMain) cloudNoteCountMain.innerText = `${data.used_links_count} links`;
        if (cloudNoteCountModal) cloudNoteCountModal.innerText = data.used_links_count;
      }
      if (data.cloud_note_url) {
        if (cloudNoteLinkMain) {
          cloudNoteLinkMain.href = data.cloud_note_url;
          cloudNoteLinkMain.innerText = data.cloud_note_url.replace(/^https?:\/\//, "");
        }
        if (cloudNoteLinkModal) cloudNoteLinkModal.href = data.cloud_note_url;
        if (cloudNoteUrlText) cloudNoteUrlText.innerText = data.cloud_note_url;
      }

      stockSelect.innerHTML = `<option value="auto_unique">🛡️ Tự động chọn Stock 720p chưa dùng (Dùng xong xóa ngay giải phóng bộ nhớ)</option>`;
      if (data.items && data.items.length > 0) {
        data.items.forEach(item => {
          const maxUses = item.max_uses || 1;
          const usedCount = item.usage_count || 0;
          const isFullyUsed = usedCount >= maxUses || item.status === "used";
          const opt = document.createElement("option");
          opt.value = item.id;
          if (isFullyUsed) {
            opt.disabled = true;
            opt.innerText = `⛔ [ĐÃ DÙNG] ${item.name} (${item.duration_formatted}) — Đã khóa`;
            opt.style.color = "#ff6666";
            opt.style.background = "#2a1515";
          } else {
            opt.innerText = `🟢 [Mới 100% • Dùng xong tự xóa] ${item.name} (${item.duration_formatted})`;
          }
          stockSelect.appendChild(opt);
        });

        renderStockTable(data.items);
        renderInlineStockRolls(data.items);
      } else {
        stockSelect.innerHTML = `<option value="auto_unique">⚠️ Kho này chưa có video (.mp4) nào</option>`;
        renderStockTable([]);
        renderInlineStockRolls([]);
      }
    } catch (e) {
      console.warn("Lỗi tải kho stock:", e);
    }
  }

  function renderInlineStockRolls(items) {
    const inlineList = document.getElementById("inline-stock-rolls-list");
    if (!inlineList) return;
    if (!items || items.length === 0) {
      inlineList.innerHTML = `<div class="p-3 rounded-lg bg-surface-container-lowest/80 border border-outline-variant/20 text-center text-xs text-on-surface-variant">Kho STOOK hiện đang trống. Bấm <strong>Tải Sẵn Đủ 30 Tiếng Stock</strong> bên trên để tự động nạp video 720p mới!</div>`;
      return;
    }
    inlineList.innerHTML = items.slice(0, 25).map((item) => {
      const maxUses = item.max_uses || 1;
      const usedCount = item.usage_count || 0;
      const isFullyUsed = usedCount >= maxUses || item.status === "used";
      if (!isFullyUsed) {
        return `
          <div class="inline-stock-item flex items-center justify-between p-2 rounded-lg bg-surface-container-lowest/80 border border-outline-variant/20 hover:border-secondary-container/40 transition-colors cursor-pointer" data-stock-id="${item.id}">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-8 h-6 rounded bg-secondary-container/20 border border-secondary-container/40 flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-secondary-container text-[14px]">movie</span>
              </div>
              <span class="font-mono text-xs text-on-surface truncate">${item.name}</span>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <span class="text-[10px] font-mono text-on-surface-variant">720p • ${item.duration_formatted || "30:00"}</span>
              <span class="px-1.5 py-0.5 rounded bg-primary-container/15 text-primary-container font-mono text-[9px] font-bold">Khả dụng</span>
            </div>
          </div>
        `;
      } else {
        return `
          <div class="flex items-center justify-between p-2 rounded-lg bg-surface-container-lowest/40 border border-outline-variant/10 opacity-60">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-8 h-6 rounded bg-surface-container-high border border-outline-variant/30 flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-on-surface-variant text-[14px]">lock</span>
              </div>
              <span class="font-mono text-xs text-on-surface-variant line-through truncate">${item.name}</span>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <span class="text-[10px] font-mono text-on-surface-variant">Đã dùng (${item.size_mb || 0}MB)</span>
              <span class="px-1.5 py-0.5 rounded bg-error-container/30 text-error font-mono text-[9px] font-bold">Chờ xóa</span>
            </div>
          </div>
        `;
      }
    }).join("");

    inlineList.querySelectorAll(".inline-stock-item").forEach((el) => {
      el.addEventListener("click", () => {
        const sid = el.dataset.stockId;
        if (stockSelect && sid) {
          stockSelect.value = sid;
        }
      });
    });
  }

  function renderStockTable(items) {
    if (!stockTableBody) return;
    if (!items || items.length === 0) {
      stockTableBody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-on-surface-variant">Kho STOOK chưa có video nào. Dán link YouTube bên trên hoặc bấm Tự Động Bù Stock để tải!</td></tr>`;
      return;
    }

    stockTableBody.innerHTML = "";
    items.forEach(item => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-surface-container/60 transition-colors";
      const maxUses = item.max_uses || 1;
      const usedCount = item.usage_count || 0;
      const isFullyUsed = usedCount >= maxUses || item.status === "used";

      let statusBadge = "";
      let actionBtn = "";
      if (!isFullyUsed) {
        statusBadge = `<span class="px-2 py-0.5 rounded bg-primary-container/15 text-primary-container border border-primary-container/30 text-[10px] font-bold">🟢 Mới 100% (Khả dụng)</span>`;
        actionBtn = `<span class="text-primary-container text-[11px] font-bold">🗑️ Dùng xong tự xóa</span>`;
      } else {
        statusBadge = `<span class="px-2 py-0.5 rounded bg-error/15 text-error border border-error/30 text-[10px] font-bold">🔒 Đã dùng - ĐÃ KHÓA</span>`;
        actionBtn = `<span class="text-error text-[11px] font-bold">🔒 Cấm dùng lại</span>`;
      }

      const projects = item.used_in_projects && item.used_in_projects.length > 0
        ? item.used_in_projects.join(", ")
        : "—";

      tr.innerHTML = `
        <td class="px-4 py-2.5 font-mono text-on-surface font-semibold">${item.name}</td>
        <td class="px-3 py-2.5 font-mono text-secondary-container">${item.duration_formatted}</td>
        <td class="px-3 py-2.5 font-mono text-on-surface-variant">${item.size_mb} MB</td>
        <td class="px-3 py-2.5">${statusBadge}</td>
        <td class="px-3 py-2.5 font-mono text-on-surface-variant text-[11px]">${projects}</td>
        <td class="px-4 py-2.5 text-right">${actionBtn}</td>
      `;
      stockTableBody.appendChild(tr);
    });
  }

  function updateReplenishButtonLabels(hrs) {
    const h = hrs || (targetStockHoursInput ? parseFloat(targetStockHoursInput.value) || 30 : 30);
    if (btnAutoReplenishMain && !btnAutoReplenishMain.disabled) {
      btnAutoReplenishMain.innerText = `⚡ Tải Sẵn Đủ ${h} Tiếng Stock (720p) Ngay`;
    }
    if (btnAutoReplenishModal && !btnAutoReplenishModal.disabled) {
      btnAutoReplenishModal.innerText = `⚡ Tự Động Tìm & Bù Đủ ${h} Tiếng Stock 720p (Không Cần Dán Link)`;
    }
  }

  function setupStockModal() {
    if (targetStockHoursInput) {
      targetStockHoursInput.addEventListener("input", () => {
        updateReplenishButtonLabels(parseFloat(targetStockHoursInput.value) || 30);
      });
    }

    async function runAutoReplenishStock() {
      const targetHrs = targetStockHoursInput ? (parseFloat(targetStockHoursInput.value) || 30) : 30;
      if (btnAutoReplenishMain) {
        btnAutoReplenishMain.disabled = true;
        btnAutoReplenishMain.innerText = `⏳ Đang kiểm tra & tải bù đủ ${targetHrs}h (720p)...`;
      }
      if (btnAutoReplenishModal) {
        btnAutoReplenishModal.disabled = true;
        btnAutoReplenishModal.innerText = `⏳ Đang tìm & tải bù đủ ${targetHrs}h (720p)...`;
      }
      if (mainReplenishMsg) {
        mainReplenishMsg.style.display = "block";
        mainReplenishMsg.style.color = "var(--accent-cyan)";
        mainReplenishMsg.innerText = `⏳ Đang kiểm tra kho Stock (Mục tiêu: ${targetHrs} tiếng). Nếu thiếu hệ thống sẽ tự động tìm video 720p mới trên YouTube và cắt thành các part 30 phút...`;
      }
      if (ytDownloadMsg) {
        ytDownloadMsg.style.color = "var(--accent-cyan)";
        ytDownloadMsg.innerText = `⏳ Đang tự động tìm video 720p mới trên YouTube và tải bù cho đủ ${targetHrs} tiếng...`;
      }

      try {
        const res = await fetch("/api/stocks/auto-replenish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_hours: targetHrs, slice_minutes: 30 })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          const msg = data.message || `✅ Đã đảm bảo kho có đủ ${data.current_hours}h / ${targetHrs}h!`;
          if (mainReplenishMsg) {
            mainReplenishMsg.style.color = "var(--accent-green)";
            mainReplenishMsg.innerText = msg;
          }
          if (ytDownloadMsg) {
            ytDownloadMsg.style.color = "var(--accent-green)";
            ytDownloadMsg.innerText = msg;
          }
          await loadStocks();
        } else {
          const errMsg = `❌ Lỗi tải bù tự động: ${data.error || "Không thể tải thêm video"}`;
          if (mainReplenishMsg) {
            mainReplenishMsg.style.color = "var(--accent-red)";
            mainReplenishMsg.innerText = errMsg;
          }
          if (ytDownloadMsg) {
            ytDownloadMsg.style.color = "var(--accent-red)";
            ytDownloadMsg.innerText = errMsg;
          }
        }
      } catch (e) {
        const errMsg = `❌ Lỗi kết nối: ${e.message}`;
        if (mainReplenishMsg) {
          mainReplenishMsg.style.color = "var(--accent-red)";
          mainReplenishMsg.innerText = errMsg;
        }
        if (ytDownloadMsg) {
          ytDownloadMsg.style.color = "var(--accent-red)";
          ytDownloadMsg.innerText = errMsg;
        }
      } finally {
        if (btnAutoReplenishMain) btnAutoReplenishMain.disabled = false;
        if (btnAutoReplenishModal) btnAutoReplenishModal.disabled = false;
        updateReplenishButtonLabels(targetHrs);
      }
    }

    if (btnAutoReplenishMain) {
      btnAutoReplenishMain.addEventListener("click", runAutoReplenishStock);
    }
    if (btnAutoReplenishModal) {
      btnAutoReplenishModal.addEventListener("click", runAutoReplenishStock);
    }

    async function runSyncCloudNote() {
      if (btnSyncCloudMain) {
        btnSyncCloudMain.disabled = true;
        btnSyncCloudMain.innerText = "⏳ Đang đồng bộ Note...";
      }
      if (btnSyncCloudModal) {
        btnSyncCloudModal.disabled = true;
        btnSyncCloudModal.innerText = "⏳ Đang đồng bộ Note...";
      }
      if (cloudSyncMsg) {
        cloudSyncMsg.style.color = "var(--accent-cyan)";
        cloudSyncMsg.innerText = "⏳ Đang đọc & dán danh sách link YouTube đã tải lên File Note Online chung...";
      }
      if (mainReplenishMsg) {
        mainReplenishMsg.style.display = "block";
        mainReplenishMsg.style.color = "var(--accent-cyan)";
        mainReplenishMsg.innerText = "⏳ Đang đồng bộ danh sách link YouTube với File Note Online chung...";
      }

      try {
        const res = await fetch("/api/stocks/sync-cloud-note", { method: "POST" });
        const data = await res.json();
        if (res.ok && data.success) {
          const noteUrl = data.cloud_note_url || "https://rentry.co/nhat-drama-stock-9f8a7b6c";
          const totalIds = data.total_synced_ids !== undefined ? data.total_synced_ids : 0;
          const pulledNew = data.new_from_cloud !== undefined ? data.new_from_cloud : 0;
          const msg = `✅ Đã đồng bộ File Note Online (${noteUrl})! Tổng số link đã khóa trên toàn hệ thống: ${totalIds} link (Nhận mới từ máy khác: +${pulledNew} | Đẩy lên Note: ${data.pushed_to_cloud ? "Thành công" : "Đã khớp"}).`;
          if (cloudSyncMsg) {
            cloudSyncMsg.style.color = "var(--accent-green)";
            cloudSyncMsg.innerText = msg;
          }
          if (mainReplenishMsg) {
            mainReplenishMsg.style.color = "var(--accent-green)";
            mainReplenishMsg.innerText = msg;
          }
          await loadStocks();
        } else {
          const errMsg = `⚠️ Không thể đồng bộ Note Online lúc này: ${data.error || "Mất kết nối mạng (Đang dùng bộ nhớ chống trùng cục bộ)"}`;
          if (cloudSyncMsg) {
            cloudSyncMsg.style.color = "var(--accent-gold)";
            cloudSyncMsg.innerText = errMsg;
          }
          if (mainReplenishMsg) {
            mainReplenishMsg.style.color = "var(--accent-gold)";
            mainReplenishMsg.innerText = errMsg;
          }
        }
      } catch (e) {
        const errMsg = `❌ Lỗi kết nối khi đồng bộ Note Online: ${e.message}`;
        if (cloudSyncMsg) {
          cloudSyncMsg.style.color = "var(--accent-red)";
          cloudSyncMsg.innerText = errMsg;
        }
      } finally {
        if (btnSyncCloudMain) {
          btnSyncCloudMain.disabled = false;
          btnSyncCloudMain.innerText = "☁️ Đồng Bộ Note Ngay";
        }
        if (btnSyncCloudModal) {
          btnSyncCloudModal.disabled = false;
          btnSyncCloudModal.innerText = "☁️ Đồng Bộ Note Ngay";
        }
      }
    }

    if (btnSyncCloudMain) {
      btnSyncCloudMain.addEventListener("click", runSyncCloudNote);
    }
    if (btnSyncCloudModal) {
      btnSyncCloudModal.addEventListener("click", runSyncCloudNote);
    }

    if (btnOpenStockModal && stockModal) {
      btnOpenStockModal.addEventListener("click", () => {
        stockModal.style.display = "flex";
        stockModal.classList.remove("hidden");
        loadStocks();
      });
    }

    if (btnCloseStockModal && stockModal) {
      btnCloseStockModal.addEventListener("click", () => {
        stockModal.style.display = "none";
        stockModal.classList.add("hidden");
      });
    }

    window.addEventListener("click", (e) => {
      if (e.target === stockModal && stockModal) {
        stockModal.style.display = "none";
        stockModal.classList.add("hidden");
      }
    });

    if (btnRescanStocks) {
      btnRescanStocks.addEventListener("click", async () => {
        btnRescanStocks.innerText = "Đang quét...";
        await fetch("/api/stocks/scan", { method: "POST" });
        await loadStocks();
        btnRescanStocks.innerText = "🔄 Quét Thêm Video Mới";
      });
    }

    if (btnCleanupUsedStocks) {
      btnCleanupUsedStocks.addEventListener("click", async () => {
        if (!confirm("Bạn có chắc chắn muốn xóa tất cả các file video stock ĐÃ DÙNG khỏi ổ cứng để giải phóng dung lượng đĩa?\n\n(Lưu ý: Hệ thống vẫn lưu vĩnh viễn lịch sử để bảo đảm TUYỆT ĐỐI KHÔNG BAO GIỜ bị dùng lại).")) {
          return;
        }
        btnCleanupUsedStocks.disabled = true;
        btnCleanupUsedStocks.innerText = "Đang dọn dẹp...";
        try {
          const res = await fetch("/api/stocks/cleanup-used", { method: "POST" });
          const data = await res.json();
          alert(data.message || `Đã dọn dẹp ${data.deleted_count} file stock đã dùng!`);
          await loadStocks();
        } catch (e) {
          alert("Lỗi dọn dẹp: " + e.message);
        } finally {
          btnCleanupUsedStocks.disabled = false;
          btnCleanupUsedStocks.innerText = "🗑️ Xóa File Stock Đã Dùng";
        }
      });
    }

    btnYtDownload.addEventListener("click", async () => {
      const url = ytUrlInput.value.trim();
      if (!url) {
        alert("Vui lòng dán link YouTube!");
        return;
      }
      await triggerYtDownload(url, false);
    });

    async function triggerYtDownload(url, forceDownload) {
      btnYtDownload.disabled = true;
      btnYtDownload.innerText = "Đang tải & cắt part...";
      ytDownloadMsg.style.color = "var(--accent-cyan)";
      ytDownloadMsg.innerText = "⏳ Đang kiểm tra và tải video, sau đó tự động cắt thành các part 30 phút... Vui lòng chờ.";

      try {
        const res = await fetch("/api/stocks/download-youtube", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: url, slice_minutes: 30, force: forceDownload })
        });
        const data = await res.json();
        if (data.success) {
          ytDownloadMsg.style.color = "var(--accent-green)";
          ytDownloadMsg.innerText = `✅ Tải & Cắt thành công ${data.parts_count} part 30 phút vào kho STOOK!`;
          ytUrlInput.value = "";
          await loadStocks();
        } else if (data.already_exists) {
          ytDownloadMsg.style.color = "var(--accent-cyan)";
          ytDownloadMsg.innerHTML = `🛡️ <strong>ĐÃ TỒN TẠI TRONG KHO:</strong><br>${data.error}<br><button type="button" id="btn-force-yt-download" class="btn-tool-link" style="margin-top:6px;">⚠️ Vẫn tải lại (Ghi đè)</button>`;
          const btnForce = document.getElementById("btn-force-yt-download");
          if (btnForce) {
            btnForce.addEventListener("click", () => triggerYtDownload(url, true));
          }
        } else {
          ytDownloadMsg.style.color = "var(--accent-red)";
          ytDownloadMsg.innerText = `❌ Lỗi: ${data.error || "Không thể tải video"}`;
        }
      } catch (e) {
        ytDownloadMsg.style.color = "var(--accent-red)";
        ytDownloadMsg.innerText = `❌ Lỗi kết nối: ${e.message}`;
      } finally {
        btnYtDownload.disabled = false;
        btnYtDownload.innerText = "Tải & Cắt Part 30p";
      }
    }
  }

  // 8. Bắt đầu sản xuất
  function setupProductionTrigger() {
    btnProduce.addEventListener("click", async () => {
      await checkLicenseStatus();
      if (!isLicenseValid) {
        if (licenseModal) licenseModal.style.display = "flex";
        return;
      }

      const outputDir = outputDirInput.value.trim() || null;
      const channel = channelNameInput.value.trim() || ".";
      const rawBgm = bgmVolSlider ? parseFloat(bgmVolSlider.value) : 8;
      const bgmVol = isNaN(rawBgm) ? 0.08 : (rawBgm <= 1.0 ? rawBgm : rawBgm / 100.0);

      // KIỂM TRA QUY ĐỊNH NGHIÊM NGẶT: TUYỆT ĐỐI KHÔNG DÙNG LẠI STOCK ĐÃ DÙNG
      if (stockSelect && stockSelect.value && stockSelect.value !== "auto_unique") {
        const selOpt = stockSelect.options[stockSelect.selectedIndex];
        if (selOpt && selOpt.disabled) {
          alert("❌ Video stock này đã qua sử dụng! Theo quy định nghiêm ngặt, tuyệt đối không được dùng lại stock đã dùng.\nVui lòng chọn video khả dụng khác hoặc chọn 'Tự động chọn Stock chưa dùng (Chống trùng 100%)'.");
          return;
        }
      }

      let endpoint = "/api/start";
      let payload = {};
      const shouldDeleteUsedStocks = autoDeleteStock ? autoDeleteStock.checked : true;
      const shouldAutoEnsureStock = autoEnsureStock ? autoEnsureStock.checked : true;
      const targetStockHours = targetStockHoursInput ? (parseFloat(targetStockHoursInput.value) || 30.0) : 30.0;

      if (currentMode === "adas") {
        const runAllBtn = document.getElementById("btn-adas-run-all");
        if (runAllBtn) runAllBtn.click();
        return;
      }

      if (currentMode === "single") {
        const script = scriptTextInput ? scriptTextInput.value.trim() : "";
        if (!script) {
          // Chế độ mặc định (Đã ẩn Kịch Bản Đơn thủ công): Lấy trực tiếp dự án từ Kho ADAS để xuất Video MP4
          const targetSel = document.getElementById("render-adas-target-select");
          const chosenTarget = targetSel ? targetSel.value : "ALL_READY";
          if (chosenTarget && chosenTarget !== "ALL_READY") {
            await triggerRenderOnly([chosenTarget], false);
            return;
          }
          const res = await fetch("/api/adas/ideas");
          if (res.ok) {
            const data = await res.json();
            const readyIds = (data.ideas || [])
              .filter((it) => (!!it.has_script && (it.pure_char_count || 0) >= 35000) && (!it.has_video_mp4 || it.status !== "COMPLETED_VIDEO"))
              .map((it) => it.ma_id);
            if (readyIds.length > 0) {
              await triggerRenderOnly(readyIds, true);
              return;
            }
            alert("Hiện chưa có dự án nào trong Kho ADAS đang chờ xuất MP4 (Hoặc toàn bộ đã xuất xong MP4).\n\nBạn có thể chọn 1 mã cụ thể ở mục 'Nguồn Kịch Bản Xuất Video (Từ Kho ADAS)' bên trái để xuất lại!");
            return;
          }
          return;
        }

        endpoint = "/api/start";
        payload = {
          script_text: script,
          project_name: projectNameInput ? (projectNameInput.value.trim() || null) : null,
          output_dir: outputDir,
          channel_name: channel,
          resolution: selectedResolution,
          fps: selectedFps,
          stock_selection: (stockSelect && stockSelect.value) ? stockSelect.value : "auto_unique",
          bgm_volume: bgmVol,
          delete_used_stocks: shouldDeleteUsedStocks,
          auto_ensure_stock_hours: shouldAutoEnsureStock,
          target_stock_hours: targetStockHours,
          voice_config: getCurrentVoiceConfigFromUI()
        };
      } else {
        // BATCH MODE
        if (batchQueue.length === 0) {
          alert("Hàng đợi kịch bản đang trống! Vui lòng bấm 'Chọn Nhiều File Kịch Bản (.txt)' trước.");
          return;
        }

        endpoint = "/api/start-batch";
        payload = {
          jobs: batchQueue.map(j => ({ name: j.name, script_text: j.script_text })),
          output_dir: outputDir,
          channel_name: channel,
          resolution: selectedResolution,
          fps: selectedFps,
          stock_selection: (stockSelect && stockSelect.value) ? stockSelect.value : "auto_unique",
          bgm_volume: bgmVol,
          delete_used_stocks: shouldDeleteUsedStocks,
          auto_ensure_stock_hours: shouldAutoEnsureStock,
          target_stock_hours: targetStockHours,
          voice_config: getCurrentVoiceConfigFromUI()
        };
      }

      btnProduce.disabled = true;
      btnProduce.style.opacity = "0.6";
      progressSection.style.display = "block";
      deliverablesBox.style.display = "none";
      progressBar.style.width = "2%";
      progressPct.innerText = "2%";
      progressMsg.innerText = "Đang bắt đầu tiến trình...";

      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Không thể khởi động");
        }
      } catch (e) {
        alert("Lỗi: " + e.message);
        btnProduce.disabled = false;
        btnProduce.style.opacity = "1";
        progressSection.style.display = "none";
      }
    });

    // Deliverables Buttons
    btnWatchVideo.addEventListener("click", async () => {
      const target = currentResults.length > 0 ? currentResults[0] : null;
      if (target && target.final_video) {
        await openSystemVideo(target.final_video);
      }
    });

    btnOpenDir.addEventListener("click", async () => {
      const target = currentResults.length > 0 ? currentResults[0] : null;
      const targetPath = (target && target.project_dir) ? target.project_dir : outputDirInput.value.trim();
      if (targetPath) {
        await openSystemFolder(targetPath);
      }
    });

    btnCopySrt.addEventListener("click", () => {
      const target = currentResults.length > 0 ? currentResults[0] : null;
      if (target && target.subtitles_srt) {
        navigator.clipboard.writeText(target.subtitles_srt);
        alert("Đã sao chép đường dẫn file SRT: " + target.subtitles_srt);
      }
    });

    btnCopyChapters.addEventListener("click", () => {
      const target = currentResults.length > 0 ? currentResults[0] : null;
      if (target && target.timestamps_txt) {
        navigator.clipboard.writeText(target.timestamps_txt);
        alert("Đã sao chép đường dẫn file Chapters: " + target.timestamps_txt);
      }
    });
  }

  // 9. WebSocket Tiến Trình Thời Gian Thực
  function connectWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${location.host}/ws`;

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("[WebSocket] Kết nối thời gian thực thành công!");
    };

    socket.onmessage = (event) => {
      try {
        const state = JSON.parse(event.data);
        handleStateUpdate(state);
      } catch (e) {
        console.error("Lỗi parse WebSocket message:", e);
      }
    };

    socket.onclose = () => {
      setTimeout(connectWebSocket, 3000);
    };

    // Đồng bộ ngay khi kết nối và lặp lại mỗi 2.5 giây
    const syncStatusNow = async () => {
      try {
        const res = await fetch("/api/status");
        if (res.ok) {
          const state = await res.json();
          handleStateUpdate(state);
        }
      } catch (e) {
        // Bỏ qua lỗi tạm thời
      }
    };
    syncStatusNow();
    setInterval(syncStatusNow, 2500);
  }

  let latestVideoPipelineState = null;
  let lastSavedIdeasCache = [];
  let lastAdasIdeasLoadTs = 0;
  let lastAdasStepKey = "";

  function handleStateUpdate(state) {
    if (!state) return;

    if (state.type === "sys_log" && state.entry) {
      pushLogEntryToConsole(state.entry);
      return;
    }

    if (state.type === "adas_update" && state.adas_state) {
      updateADASLiveUI(state.adas_state);
      const now = Date.now();
      const stepKey = `${state.adas_state.status || ""}|${state.adas_state.current_ma_id || ""}|${state.adas_state.current_step || ""}`;
      if (stepKey !== lastAdasStepKey || (now - lastAdasIdeasLoadTs >= 4000)) {
        lastAdasStepKey = stepKey;
        lastAdasIdeasLoadTs = now;
        const listEl = document.getElementById("adas-ideas-list");
        // Không ghi đè DOM khi người dùng đang rê chuột vào danh sách dự án để bấm nút Mở Folder / Xem / Render
        if (!listEl || !listEl.matches(":hover")) {
          loadSavedIdeas();
        }
      }
      return;
    }

    const prevStatus = latestVideoPipelineState ? latestVideoPipelineState.status : null;
    const prevPct = latestVideoPipelineState ? Math.round(latestVideoPipelineState.progress || 0) : -1;
    latestVideoPipelineState = state;
    if (state.hardware_load) {
      const g = Math.round(state.hardware_load.gpu_percent || 0);
      const c = Math.round(state.hardware_load.cpu_percent || 0);
      const balEl = document.getElementById("gpu-balancer-badge");
      if (balEl) {
        balEl.innerText = `⚡ Tự cân đối 90%: GPU ${g}% • CPU ${c}%`;
      }
      const gpuPctEl = document.getElementById("gauge-gpu-pct");
      const gpuBarEl = document.getElementById("gauge-gpu-bar");
      const cpuPctEl = document.getElementById("gauge-cpu-pct");
      const cpuBarEl = document.getElementById("gauge-cpu-bar");
      if (gpuPctEl) gpuPctEl.innerText = `${g}%`;
      if (gpuBarEl) gpuBarEl.style.width = `${Math.max(4, Math.min(100, g))}%`;
      if (cpuPctEl) cpuPctEl.innerText = `${c}%`;
      if (cpuBarEl) cpuBarEl.style.width = `${Math.max(4, Math.min(100, c))}%`;
    }
    const curPct = Math.round(state.progress || 0);
    if (lastSavedIdeasCache.length > 0 && (prevStatus !== state.status || prevPct !== curPct)) {
      renderSavedIdeasList(lastSavedIdeasCache);
    }

    if (state.status === "running") {
      progressSection.style.display = "block";
      deliverablesBox.style.display = "none";
      btnProduce.disabled = true;
      btnProduce.style.opacity = "0.6";

      const pct = Math.max(2, Math.min(100, state.progress || 0));
      progressBar.style.width = `${pct}%`;
      progressPct.innerText = `${pct.toFixed(0)}%`;
      progressMsg.innerText = state.message || "Đang xử lý...";

      const totalJobs = state.batch_total || 1;
      const activeJobs = Array.isArray(state.active_jobs) ? state.active_jobs : [];
      const doneJobsCount = typeof state.completed_count === "number" ? state.completed_count : ((state.results || []).length);
      const pendingJobsCount = typeof state.pending_count === "number" ? state.pending_count : Math.max(0, totalJobs - doneJobsCount - activeJobs.length);

      progressStageName.innerText = `📊 Tiến độ lô: Đang chạy ${activeJobs.length} video song song • Đã xong: ${doneJobsCount}/${totalJobs} video • Chờ: ${pendingJobsCount} video`;

      const sec = state.elapsed_seconds || 0;
      const m = Math.floor(sec / 60);
      const s = sec % 60;
      progressTime.innerText = `Thời gian tổng: ${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

      renderActiveVideoJobBoxes(activeJobs);
    } else if (state.status === "completed") {
      progressBar.style.width = "100%";
      progressPct.innerText = "100%";
      progressMsg.innerText = state.message || "Sản xuất hoàn tất!";
      btnProduce.disabled = false;
      btnProduce.style.opacity = "1";
      renderActiveVideoJobBoxes([]);

      currentResults = state.results || [];
      deliverablesBox.style.display = "block";
      deliverablesTitle.innerText = currentResults.length > 1
        ? `🎉 HOÀN TẤT THÀNH CÔNG HÀNG ĐỢI ${currentResults.length} VIDEO!`
        : `🎉 SẢN XUẤT HOÀN TẤT THÀNH CÔNG!`;

      loadStocks();
    } else if (state.status === "error") {
      progressMsg.innerText = state.message || "Có lỗi xảy ra";
      progressMsg.style.color = "var(--accent-red)";
      btnProduce.disabled = false;
      btnProduce.style.opacity = "1";
      renderActiveVideoJobBoxes([]);
    }
  }

  function renderActiveVideoJobBoxes(activeJobs) {
    const listContainer = document.getElementById("multi-video-jobs-list");
    if (!listContainer) return;

    if (!Array.isArray(activeJobs) || activeJobs.length === 0) {
      listContainer.classList.add("hidden");
      listContainer.classList.remove("flex");
      listContainer.innerHTML = "";
      return;
    }

    listContainer.classList.remove("hidden");
    listContainer.classList.add("flex");

    const activeIdsSet = new Set(activeJobs.map((j) => String(j.project_name || "")));
    listContainer.querySelectorAll("[data-video-job-id]").forEach((rowEl) => {
      if (!activeIdsSet.has(rowEl.getAttribute("data-video-job-id") || "")) {
        rowEl.remove();
      }
    });

    activeJobs.forEach((job) => {
      const projId = String(job.project_name || "VIDEO");
      const stageLbl = String(job.stage_label || "Đang xử lý");
      const detailTxt = String(job.detail || "Đang xử lý...");
      const jobPct = Math.max(1, Math.min(100, Number(job.progress || 0)));
      const elap = Math.max(0, Number(job.elapsed_seconds || 0));
      const mm = String(Math.floor(elap / 60)).padStart(2, "0");
      const ss = String(elap % 60).padStart(2, "0");

      let rowEl = listContainer.querySelector(`[data-video-job-id="${projId}"]`);
      if (!rowEl) {
        rowEl = document.createElement("div");
        rowEl.setAttribute("data-video-job-id", projId);
        rowEl.className = "video-job-row p-2.5 rounded-md bg-surface-container border border-surface-container-highest flex flex-col gap-1.5 shadow-sm";
        rowEl.innerHTML = `
          <div class="flex items-center justify-between gap-2 text-xs font-mono">
            <div class="flex items-center gap-1.5 min-w-0 flex-1">
              <span class="px-1.5 py-0.5 rounded bg-primary-container/20 text-primary-container font-bold border border-primary-container/40 shrink-0">#${projId}</span>
              <span class="vjob-stage-badge px-1.5 py-0.5 rounded bg-secondary-container/20 text-secondary border border-secondary/30 text-[10.5px] font-semibold shrink-0"></span>
              <span class="vjob-detail-text text-on-surface text-[11px] truncate flex-1"></span>
            </div>
            <div class="flex items-center gap-2.5 shrink-0">
              <span class="vjob-time-text text-[10.5px] text-on-surface-variant"></span>
              <span class="vjob-pct-text font-bold text-primary-container min-w-[40px] text-right"></span>
            </div>
          </div>
          <div class="w-full h-1.5 bg-surface-container-lowest rounded overflow-hidden">
            <div class="vjob-bar-fill h-full bg-gradient-to-r from-secondary to-primary-container rounded transition-all duration-300" style="width: 1%;"></div>
          </div>
        `;
        listContainer.appendChild(rowEl);
      }

      const stageBadgeEl = rowEl.querySelector(".vjob-stage-badge");
      const detailEl = rowEl.querySelector(".vjob-detail-text");
      const timeEl = rowEl.querySelector(".vjob-time-text");
      const pctEl = rowEl.querySelector(".vjob-pct-text");
      const barEl = rowEl.querySelector(".vjob-bar-fill");

      if (stageBadgeEl && stageBadgeEl.innerText !== stageLbl) stageBadgeEl.innerText = stageLbl;
      if (detailEl && detailEl.innerText !== detailTxt) {
        detailEl.innerText = detailTxt;
        detailEl.title = `[#${projId}] ${stageLbl} — ${detailTxt}`;
      }
      if (timeEl) timeEl.innerText = `⏱ ${mm}:${ss}`;
      if (pctEl) pctEl.innerText = `${jobPct.toFixed(1)}%`;
      if (barEl) barEl.style.width = `${jobPct}%`;
    });
  }

  // 10. Hệ thống Khóa & Kích hoạt Bản Quyền (License Gate)
  function setupLicenseSystem() {
    if (btnOpenLicenseModal) {
      btnOpenLicenseModal.addEventListener("click", async () => {
        await checkLicenseStatus();
        if (licenseModal) licenseModal.style.display = "flex";
      });
    }

    if (btnCloseLicenseModal) {
      btnCloseLicenseModal.addEventListener("click", () => {
        if (isLicenseValid && licenseModal) {
          licenseModal.style.display = "none";
        }
      });
    }

    if (btnCopyHwid) {
      btnCopyHwid.addEventListener("click", () => {
        const hwid = licenseHwidText ? licenseHwidText.innerText.trim() : "";
        if (hwid) {
          navigator.clipboard.writeText(hwid);
          const orig = btnCopyHwid.innerText;
          btnCopyHwid.innerText = "✅ Đã Copy!";
          setTimeout(() => { btnCopyHwid.innerText = orig; }, 2000);
        }
      });
    }

    if (btnActivateLicense) {
      btnActivateLicense.addEventListener("click", async () => {
        const keyStr = licenseKeyInput ? licenseKeyInput.value.trim() : "";
        if (!keyStr) {
          if (licenseModalMsg) {
            licenseModalMsg.style.color = "var(--accent-red)";
            licenseModalMsg.innerText = "⚠️ Vui lòng dán mã Key bản quyền vào ô bên trên!";
          }
          return;
        }

        btnActivateLicense.disabled = true;
        btnActivateLicense.innerText = "⏳ ĐANG KIỂM TRA & KÍCH HOẠT...";
        if (licenseModalMsg) {
          licenseModalMsg.style.color = "var(--accent-cyan)";
          licenseModalMsg.innerText = "Đang xác thực chữ ký số và thời hạn Key...";
        }

        try {
          const res = await fetch("/api/license/activate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ license_key: keyStr })
          });
          const data = await res.json();
          if (res.ok && data.valid) {
            if (licenseModalMsg) {
              licenseModalMsg.style.color = "var(--accent-green)";
              licenseModalMsg.innerText = data.message || "✅ Kích hoạt bản quyền thành công!";
            }
            await checkLicenseStatus();
            setTimeout(() => {
              if (licenseModal) licenseModal.style.display = "none";
            }, 1000);
          } else {
            if (licenseModalMsg) {
              licenseModalMsg.style.color = "var(--accent-red)";
              licenseModalMsg.innerText = data.detail || data.message || "❌ Mã Key không hợp lệ hoặc đã hết hạn!";
            }
          }
        } catch (e) {
          if (licenseModalMsg) {
            licenseModalMsg.style.color = "var(--accent-red)";
            licenseModalMsg.innerText = "❌ Lỗi kết nối khi kích hoạt: " + e.message;
          }
        } finally {
          btnActivateLicense.disabled = false;
          btnActivateLicense.innerText = "🔓 KÍCH HOẠT / GIA HẠN BẢN QUYỀN NGAY";
        }
      });
    }
  }

  async function checkLicenseStatus() {
    try {
      const res = await fetch("/api/license/status");
      const data = await res.json();
      isLicenseValid = !!data.valid;

      if (licenseHwidText && data.hwid) {
        licenseHwidText.innerText = data.hwid;
      }

      if (data.valid) {
        if (licenseBadgeText) {
          licenseBadgeText.innerText = `Bản Quyền: Còn ${data.days_remaining} ngày (${data.expiry_formatted})`;
        }
        if (btnOpenLicenseModal) {
          btnOpenLicenseModal.style.borderColor = "rgba(0, 230, 118, 0.5)";
          btnOpenLicenseModal.style.background = "rgba(0, 230, 118, 0.12)";
          btnOpenLicenseModal.style.color = "var(--accent-green)";
        }
        if (licModalStatus) {
          licModalStatus.style.color = "var(--accent-green)";
          licModalStatus.innerText = `✅ Đang hoạt động (Còn ${data.days_remaining} ngày)`;
        }
        if (licModalPlan) licModalPlan.innerText = `${data.plan_label || ""} — ${data.mode_label || ""}`;
        if (licModalExpiry) licModalExpiry.innerText = data.expiry_formatted || "--/--/----";
        if (licenseKeyInput && data.license_key && !licenseKeyInput.value) {
          licenseKeyInput.value = data.license_key;
        }
        if (btnCloseLicenseModal) btnCloseLicenseModal.style.display = "block";
      } else {
        if (licenseBadgeText) {
          licenseBadgeText.innerText = data.status === "expired" ? "⛔ KEY ĐÃ HẾT HẠN" : "🔒 CHƯA KÍCH HOẠT KEY";
        }
        if (btnOpenLicenseModal) {
          btnOpenLicenseModal.style.borderColor = "rgba(255, 75, 75, 0.6)";
          btnOpenLicenseModal.style.background = "rgba(255, 75, 75, 0.15)";
          btnOpenLicenseModal.style.color = "#ff6b6b";
        }
        if (licModalStatus) {
          licModalStatus.style.color = "var(--accent-red)";
          licModalStatus.innerText = data.message || "Chưa kích hoạt hoặc đã hết hạn";
        }
        if (licModalPlan) licModalPlan.innerText = data.plan_label || "Chưa kích hoạt";
        if (licModalExpiry) licModalExpiry.innerText = data.expiry_formatted || "--/--/----";
        if (btnCloseLicenseModal) btnCloseLicenseModal.style.display = "none";
        if (licenseModal) licenseModal.style.display = "flex";
      }
    } catch (e) {
      console.warn("Không thể kiểm tra trạng thái bản quyền:", e);
    }
  }

  // ============================================================================
  // 11. HỆ THỐNG 3 TÀI KHOẢN CHATGPT WEB & DÂY CHUYỀN ADAS (STEP 2 -> STEP 6)
  // ============================================================================
  let currentProjectDetailData = null;

  async function openSystemFolder(targetPath) {
    if (!targetPath) return;
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.open_folder) {
        const res = await window.pywebview.api.open_folder(targetPath);
        if (res && res.success) return;
      }
    } catch (e) {
      console.warn("pywebview open_folder fallback:", e);
    }
    await fetch("/api/open-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: targetPath })
    });
  }

  async function openSystemVideo(targetPath) {
    if (!targetPath) return;
    try {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.open_video) {
        const res = await window.pywebview.api.open_video(targetPath);
        if (res && res.success) return;
      }
    } catch (e) {
      console.warn("pywebview open_video fallback:", e);
    }
    await fetch("/api/open-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: targetPath })
    });
  }

  let activeGpuServerMode = "voicevox_gpu";

  function getCurrentVoiceConfigFromUI() {
    const mainSel = document.getElementById("voice-preset-select");
    const adasSel = document.getElementById("adas-voice-select");
    const speedRange = document.getElementById("voice-speed-range");
    const pitchRange = document.getElementById("voice-pitch-range");
    const intoRange = document.getElementById("voice-intonation-range");
    const pauseRange = document.getElementById("voice-pause-range");

    const selectedId = (mainSel && mainSel.value) || (adasSel && adasSel.value) || "Drama";
    const presetObj = (voicePresetsCache || []).find((p) => p.id === selectedId) || null;
    const isOmni = activeGpuServerMode === "omnivoice_gpu" || (presetObj && presetObj.engine === "omnivoice");

    const activePerfMode = localStorage.getItem("studio_perf_mode") || "full_100";
    return {
      active_gpu_server: isOmni ? "omnivoice_gpu" : "voicevox_gpu",
      engine_mode: isOmni ? "omnivoice" : "voicevox",
      selected_preset_id: selectedId,
      speaker_id: presetObj ? presetObj.speaker_id : 13,
      speedScale: speedRange ? parseFloat(speedRange.value) : 0.97,
      pitchScale: pitchRange ? parseFloat(pitchRange.value) : -0.02,
      intonationScale: intoRange ? parseFloat(intoRange.value) : 0.95,
      pauseLengthScale: pauseRange ? parseFloat(pauseRange.value) : 1.12,
      volumeScale: presetObj ? (presetObj.volumeScale || 1.05) : 1.05,
      ref_wav: presetObj ? (presetObj.ref_wav || "Drama.wav") : "Drama.wav",
      performance_mode: activePerfMode
    };
  }

  function getCurrentVideoSettings() {
    const rawBgm = bgmVolSlider ? parseFloat(bgmVolSlider.value) : 8;
    const bgmVol = isNaN(rawBgm) ? 0.08 : (rawBgm <= 1.0 ? rawBgm : rawBgm / 100.0);
    const activePerfMode = localStorage.getItem("studio_perf_mode") || "full_100";
    return {
      output_dir: outputDirInput ? outputDirInput.value.trim() : "",
      channel_name: (channelNameInput ? channelNameInput.value.trim() : "") || ".",
      resolution: selectedResolution,
      fps: selectedFps,
      stock_selection: (stockSelect && stockSelect.value) ? stockSelect.value : "auto_unique",
      bgm_volume: bgmVol,
      delete_used_stocks: autoDeleteStock ? autoDeleteStock.checked : true,
      auto_ensure_stock_hours: autoEnsureStock ? autoEnsureStock.checked : true,
      target_stock_hours: targetStockHoursInput ? parseFloat(targetStockHoursInput.value) || 30.0 : 30.0,
      performance_mode: activePerfMode,
      voice_config: getCurrentVoiceConfigFromUI()
    };
  }

  function updateADASLiveUI(st) {
    if (!st) return;
    const stepEl = document.getElementById("adas-current-step-text");
    const pctEl = document.getElementById("adas-progress-pct");
    const barEl = document.getElementById("adas-progress-bar");
    const msgEl = document.getElementById("adas-status-msg");
    const stopBtn = document.getElementById("btn-adas-stop");
    const threadEl = document.getElementById("adas-thread-status");

    const pct = Math.max(0, Math.min(100, Math.round(st.progress || 0)));
    if (stepEl) {
      stepEl.innerText = `🤖 Trạng thái Agent: ${st.current_step || "Sẵn sàng"}${st.current_ma_id ? " [" + st.current_ma_id + "]" : ""}`;
    }
    if (pctEl) {
      pctEl.innerText = `${pct}%`;
    }
    if (barEl) {
      barEl.style.width = `${pct}%`;
    }
    if (msgEl) {
      msgEl.innerText = st.message || "";
      msgEl.style.color = st.status === "error" ? "var(--accent-red)" : st.status === "completed" ? "var(--accent-green)" : "var(--text-primary)";
    }
    if (stopBtn) {
      if (st.status === "running") {
        stopBtn.style.display = "inline-flex";
        stopBtn.classList.remove("hidden");
      } else {
        stopBtn.style.display = "none";
        stopBtn.classList.add("hidden");
      }
    }
    if (threadEl) {
      threadEl.innerText = st.status === "running"
        ? `● LUỒNG ĐANG CHẠY (${st.current_ma_id || "ADAS"})`
        : "● LUỒNG ĐANG SẴN SÀNG";
    }
  }

  async function refreshChatGPTAccountsBar(force = false) {
    try {
      const res = await fetch(`/api/chatgpt/status?force=${force ? "true" : "false"}`);
      if (!res.ok) return;
      const data = await res.json();
      const accs = data.accounts || {};
      let openOrLoggedCount = 0;

      ["acc_1", "acc_2", "acc_3"].forEach((aid, idx) => {
        const btn = document.getElementById(`btn-chatgpt-acc-${idx + 1}`);
        if (!btn) return;
        const info = accs[aid] || {};
        if (info.browser_open) openOrLoggedCount += 1;
        const port = 9222 + idx;
        const activeJobs = (info.active_projects || []).length;

        if (!info.browser_open) {
          btn.innerHTML = `<span class="w-2 h-2 rounded-full bg-on-surface-variant/60"></span>Acc #${idx + 1} (Cổng ${port}) — Chưa mở`;
        } else if (info.logged_in) {
          const busyTag = activeJobs > 0 ? ` • 🔥 Đang chạy ${activeJobs}` : "";
          btn.innerHTML = `<span class="w-2 h-2 rounded-full bg-primary-container animate-pulse"></span>Acc #${idx + 1} (Cổng ${port})${busyTag}`;
        } else {
          btn.innerHTML = `<span class="w-2 h-2 rounded-full bg-tertiary"></span>Acc #${idx + 1} (Cổng ${port}) — Cần Login`;
        }
      });

      const cdpBadge = document.getElementById("adas-cdp-linked-badge");
      if (cdpBadge) {
        cdpBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-primary-container animate-ping"></span>CDP LINKED (${openOrLoggedCount}/3 ACC)`;
      }

      const visBtn = document.getElementById("btn-chatgpt-toggle-vis");
      if (visBtn) {
        const isHidden = !!data.chrome_hidden;
        visBtn.dataset.visible = isHidden ? "false" : "true";
        visBtn.innerHTML = isHidden
          ? `<span class="material-symbols-outlined text-[15px]">visibility</span>Hiện Lại Cửa Sổ Chrome`
          : `<span class="material-symbols-outlined text-[15px]">visibility_off</span>Ẩn Ngầm Chrome (-3200)`;
      }
    } catch (e) {
      // Bỏ qua lỗi tạm thời
    }
  }

  async function loadSavedIdeas() {
    try {
      const res = await fetch("/api/adas/ideas");
      if (!res.ok) return;
      const data = await res.json();
      if (data.state) updateADASLiveUI(data.state);
      renderSavedIdeasList(data.ideas || []);
    } catch (e) {
      console.warn("Lỗi tải danh sách ý tưởng ADAS:", e);
    }
  }

  let currentAdasFilter = "all";
  let adasVisibleLimit = 25;

  function renderSavedIdeasList(ideas) {
    lastSavedIdeasCache = ideas || [];
    const countEl = document.getElementById("adas-ideas-count");
    const listEl = document.getElementById("adas-ideas-list");
    if (countEl) countEl.innerText = ideas.length;
    if (!listEl) return;

    const classifyDone = (it) => {
      const pureCount = it.pure_char_count || 0;
      const doneParts = typeof it.completed_parts_count === "number"
        ? it.completed_parts_count
        : (pureCount >= 35000 ? 3 : pureCount >= 24000 ? 2 : pureCount >= 9500 ? 1 : 0);
      return !!it.has_script && pureCount >= 35000 && doneParts >= 3;
    };

    const isVideoTrulyCompleted = (it) => !!it.has_video_mp4 && it.status === "COMPLETED_VIDEO";

    const doneIdeas = ideas.filter((it) => classifyDone(it));
    const pendingIdeas = ideas.filter((it) => !classifyDone(it));
    const renderedIdeas = ideas.filter((it) => isVideoTrulyCompleted(it));
    const readyUnrendered = doneIdeas.filter((it) => !isVideoTrulyCompleted(it));
    const videoErrorCount = readyUnrendered.filter((it) => it.status === "ERROR_VIDEO").length;
    const mp4DoneCount = renderedIdeas.length;

    const renderSummaryEl = document.getElementById("render-adas-ready-summary");
    if (renderSummaryEl) {
      const errNote = videoErrorCount > 0 ? ` (Gồm ${videoErrorCount} video lỗi/ngắt cần chạy lại)` : "";
      renderSummaryEl.innerText = `✅ Chờ xuất MP4: ${readyUnrendered.length} mã${errNote} • Đã có MP4: ${mp4DoneCount} mã`;
    }
    const renderTargetSel = document.getElementById("render-adas-target-select");
    if (renderTargetSel) {
      const prevVal = renderTargetSel.value || "ALL_READY";
      const opts = [
        `<option value="ALL_READY">🎬 Xuất Tất Cả Kịch Bản Chưa Có MP4 & Video Lỗi/Ngắt (${readyUnrendered.length} mã sẵn sàng)</option>`,
        ...doneIdeas.map((it) => {
          const mid = it.ma_id || "IDEA";
          const t = String(it.locked_title || it.draft_title_ja || it.summary_vi || "").slice(0, 42);
          const mp4Tag = isVideoTrulyCompleted(it)
            ? " [Đã có MP4]"
            : (it.status === "ERROR_VIDEO" ? " [⚠️ Lỗi/Ngắt - Chờ Render lại]" : " [Chờ Render]");
          return `<option value="${mid}">#${mid}${mp4Tag} — ${t}...</option>`;
        })
      ];
      renderTargetSel.innerHTML = opts.join("");
      if ([...renderTargetSel.options].some((o) => o.value === prevVal)) {
        renderTargetSel.value = prevVal;
      }
    }

    const btnAll = document.getElementById("btn-adas-filter-all");
    const btnPending = document.getElementById("btn-adas-filter-pending");
    const btnDone = document.getElementById("btn-adas-filter-done");
    const btnUnrendered = document.getElementById("btn-adas-filter-unrendered");
    const btnRendered = document.getElementById("btn-adas-filter-rendered");
    if (btnAll) btnAll.innerText = `Tất cả (${ideas.length})`;
    if (btnPending) btnPending.innerText = `⏳ Chưa xong (${pendingIdeas.length})`;
    if (btnDone) btnDone.innerText = `✅ Đã xong KB (${doneIdeas.length})`;
    if (btnUnrendered) btnUnrendered.innerText = `📦 Chưa Render (${readyUnrendered.length})`;
    if (btnRendered) btnRendered.innerText = `🎬 Đã Render (${renderedIdeas.length})`;

    document.querySelectorAll(".adas-filter-btn").forEach((b) => {
      const f = b.dataset.adasFilter || "all";
      if (f === currentAdasFilter) {
        b.className = "adas-filter-btn px-2 py-0.5 rounded text-[10.5px] font-mono font-bold bg-primary-container text-on-primary-container transition-all";
      } else {
        b.className = "adas-filter-btn px-2 py-0.5 rounded text-[10.5px] font-mono font-semibold text-on-surface-variant hover:bg-surface-container-high transition-all";
      }
      if (!b.dataset.boundClick) {
        b.dataset.boundClick = "1";
        b.addEventListener("click", () => {
          currentAdasFilter = b.dataset.adasFilter || "all";
          adasVisibleLimit = 25;
          renderSavedIdeasList(lastSavedIdeasCache);
        });
      }
    });

    const filteredIdeas = currentAdasFilter === "rendered"
      ? renderedIdeas
      : (currentAdasFilter === "unrendered"
        ? readyUnrendered
        : (currentAdasFilter === "done"
          ? doneIdeas
          : (currentAdasFilter === "pending" ? pendingIdeas : ideas)));

    if (filteredIdeas.length === 0) {
      const emptyMsg = currentAdasFilter === "pending"
        ? "✅ Tuyệt vời! Không còn tiêu đề nào chưa xong kịch bản."
        : (currentAdasFilter === "done"
          ? "⏳ Chưa có tiêu đề nào hoàn thành kịch bản."
          : (currentAdasFilter === "unrendered"
            ? "✅ Tất cả các kịch bản đã viết xong đều đã được Render Video MP4 (hoặc chưa có kịch bản nào hoàn tất)."
            : (currentAdasFilter === "rendered"
              ? "🎬 Chưa có kịch bản nào đã Render xong Video MP4."
              : "Chưa có tiêu đề nào được lưu. Hãy dán Tiêu đề Nhật nháp ở cột bên trái rồi bấm Lưu Kho Dự Án!")));
      listEl.innerHTML = `<div class="p-4 rounded-lg bg-surface-container-lowest/60 border border-dashed border-outline-variant/30 text-center text-xs text-on-surface-variant">${emptyMsg}</div>`;
      return;
    }

    const visibleItems = filteredIdeas.slice(0, adasVisibleLimit);
    const remainingCount = Math.max(0, filteredIdeas.length - visibleItems.length);

    const rowsHtml = visibleItems.map((it) => {
      const maId = it.ma_id || "IDEA";
      const lockedTitle = it.locked_title || "";
      const draftTitle = it.draft_title_ja || it.summary_vi || "(Chưa có tiêu đề Nhật)";
      const fullTitle = lockedTitle || draftTitle;
      const pureCount = it.pure_char_count || 0;
      const doneParts = typeof it.completed_parts_count === "number"
        ? it.completed_parts_count
        : (pureCount >= 35000 ? 3 : pureCount >= 24000 ? 2 : pureCount >= 9500 ? 1 : 0);
      const hasScript = !!it.has_script && pureCount >= 35000 && doneParts >= 3;
      const isPartialScript = !hasScript && (it.status === "PARTIAL_SCRIPT" || (pureCount >= 2500 && pureCount < 35000) || (doneParts > 0 && doneParts < 3));
      const hasMp4 = isVideoTrulyCompleted(it);
      const activeProjectsList = (latestVideoPipelineState && latestVideoPipelineState.current_project)
        ? String(latestVideoPipelineState.current_project).split(",").map((s) => s.trim()).filter(Boolean)
        : [];
      const isVideoRenderingNow =
        latestVideoPipelineState &&
        latestVideoPipelineState.status === "running" &&
        activeProjectsList.includes(maId);
      const isVideoError = it.status === "ERROR_VIDEO" && !hasMp4;
      const isError = (it.status === "ERROR" || it.status === "ERROR_VIDEO") && !hasScript && !isPartialScript;
      const isRunning = (it.status === "RUNNING" || (it.status === "VIDEO_RENDERING" && isVideoRenderingNow) || isVideoRenderingNow) && !hasMp4;
      const hasThumb = !!it.has_thumbnail;
      const hasSeo = !!it.has_seo;

      let statusPill = `<span class="px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant text-[10px] font-mono shrink-0">⏳ Chưa xong</span>`;
      if (hasMp4) {
        statusPill = `<span class="px-1.5 py-0.5 rounded bg-primary-container/20 text-primary-container border border-primary-container/40 text-[10px] font-mono font-bold shrink-0">🎬 Đã có MP4</span>`;
      } else if (isRunning) {
        statusPill = `<span class="px-1.5 py-0.5 rounded bg-secondary-container/20 text-secondary-container border border-secondary-container/40 text-[10px] font-mono font-bold animate-pulse shrink-0">🔄 Đang chạy</span>`;
      } else if (isVideoError && hasScript) {
        const kChars = (pureCount / 1000).toFixed(1) + "k";
        statusPill = `<span class="px-1.5 py-0.5 rounded bg-error/20 text-error border border-error/40 text-[10px] font-mono font-bold shrink-0" title="Video trước đó bị lỗi hoặc ngắt giữa chừng — Đã lọc vào Chưa Render để chạy lại">⚠️ Lỗi Render (${kChars})</span>`;
      } else if (hasScript) {
        const kChars = (pureCount / 1000).toFixed(1) + "k";
        statusPill = `<span class="px-1.5 py-0.5 rounded bg-primary-container/15 text-primary-container border border-primary-container/30 text-[10px] font-mono font-semibold shrink-0">✓ Xong (${kChars})</span>`;
      } else if (isPartialScript) {
        statusPill = `<span class="px-1.5 py-0.5 rounded bg-tertiary/15 text-tertiary border border-tertiary/30 text-[10px] font-mono font-semibold shrink-0">⚠ ${doneParts}/3 Part</span>`;
      } else if (isError) {
        statusPill = `<span class="px-1.5 py-0.5 rounded bg-error/20 text-error border border-error/40 text-[10px] font-mono font-bold shrink-0">❌ Lỗi</span>`;
      }

      const safeTooltip = String(`${maId}: ${fullTitle} (${it.current_step || ""})`).replace(/"/g, "&quot;");

      return `
        <div class="adas-idea-card px-2.5 py-1.5 rounded bg-surface-container-high border border-outline-variant/25 hover:border-secondary-container/40 transition-all flex items-center justify-between gap-2" style="display:flex;" title="${safeTooltip}">
          <div class="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
            <span class="px-1.5 py-0.5 rounded bg-secondary-container/15 text-secondary-container font-mono font-bold text-[10.5px] border border-secondary-container/30 shrink-0">#${maId}</span>
            <span class="text-[11.5px] text-on-surface font-medium truncate flex-1">${fullTitle}</span>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            ${statusPill}
            ${!hasScript ? `
              <button type="button" class="btn-idea-script-only px-2 py-0.5 rounded bg-primary-container text-on-primary-fixed hover:brightness-110 text-[10.5px] font-bold flex items-center gap-0.5 transition-all" data-id="${maId}" title="Viết kịch bản cho mã này">
                <span class="material-symbols-outlined text-[12px]">play_arrow</span>${isPartialScript ? "Tiếp" : "Viết"}
              </button>
            ` : `
              <button type="button" class="btn-idea-render-mp4 px-1.5 py-0.5 rounded bg-secondary-container/20 hover:bg-secondary-container/30 text-secondary-container border border-secondary-container/40 text-[10px] font-bold flex items-center gap-0.5 transition-all" data-id="${maId}" title="Dựng Video MP4">
                <span class="material-symbols-outlined text-[12px]">movie</span>Dựng
              </button>
              <button type="button" class="btn-idea-rewrite px-1.5 py-0.5 rounded bg-surface-container hover:bg-surface-bright text-tertiary border border-tertiary/30 text-[10px] font-semibold transition-all" data-id="${maId}" data-has-script="1" title="Viết lại kịch bản">↻</button>
            `}
            ${(hasScript && !hasThumb) ? `
              <button type="button" class="btn-idea-thumb px-1.5 py-0.5 rounded bg-surface-container hover:bg-surface-bright text-secondary border border-outline-variant/30 text-[10px] transition-all" data-id="${maId}" title="Tạo Thumbnail">🖼</button>
            ` : ""}
            <button type="button" class="btn-idea-view p-1 rounded bg-surface-container hover:bg-surface-bright text-on-surface-variant hover:text-on-surface border border-outline-variant/30 transition-all" data-id="${maId}" title="Xem Chi Tiết Kịch Bản & SEO">
              <span class="material-symbols-outlined text-[13px]">visibility</span>
            </button>
            <button type="button" class="btn-idea-folder p-1 rounded bg-surface-container hover:bg-surface-bright text-on-surface-variant hover:text-tertiary border border-outline-variant/30 transition-all" data-id="${maId}" title="Mở Thư Mục Dự Án">
              <span class="material-symbols-outlined text-[13px]">folder</span>
            </button>
            <button type="button" class="btn-idea-del p-1 rounded bg-surface-container hover:bg-error-container/40 text-on-surface-variant hover:text-error border border-outline-variant/30 transition-all" data-id="${maId}" title="Xóa Mã Này">
              <span class="material-symbols-outlined text-[13px]">delete</span>
            </button>
          </div>
        </div>
      `;
    }).join("");

    const moreBtnHtml = remainingCount > 0
      ? `<button type="button" id="btn-adas-load-more" class="w-full py-1.5 mt-1 rounded bg-surface-container hover:bg-surface-container-high text-secondary font-mono text-[11px] font-semibold border border-surface-container-high transition-all">Xem thêm ${remainingCount} tiêu đề nữa...</button>`
      : "";

    listEl.innerHTML = rowsHtml + moreBtnHtml;

    const loadMoreBtn = document.getElementById("btn-adas-load-more");
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener("click", () => {
        adasVisibleLimit += 50;
        renderSavedIdeasList(lastSavedIdeasCache);
      });
    }

    // Gắn sự kiện cho nút Render MP4 trực tiếp (dành cho các mã đã viết xong kịch bản)
    listEl.querySelectorAll(".btn-idea-render-mp4").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const mid = btn.dataset.id;
        await triggerRenderOnly([mid], false);
      });
    });

    // Gắn sự kiện cho nút Chỉ Viết KB + SEO + Thumbnail (Không Render Video)
    listEl.querySelectorAll(".btn-idea-script-only").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const mid = btn.dataset.id;
        await triggerRunADAS([mid], false, false);
      });
    });

    // Gắn sự kiện cho các nút trên từng thẻ ý tưởng
    listEl.querySelectorAll(".btn-idea-run").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const mid = btn.dataset.id;
        await triggerRunADAS([mid], null, false);
      });
    });

    // Gắn sự kiện cho nút Viết Lại Thủ Công (🔁 Viết Lại)
    listEl.querySelectorAll(".btn-idea-rewrite").forEach((btn) => {
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const mid = btn.dataset.id;
        if (!mid) return;
        const alreadyHasScript = btn.dataset.hasScript === "1";
        if (alreadyHasScript) {
          const ok = confirm(
            `🔁 Bạn có muốn VIẾT LẠI THỦ CÔNG kịch bản cho mã [${mid}] từ đầu không?\n\n` +
            `• Chọn OK: Xóa kịch bản cũ của ${mid} và mở AI viết lại mới hoàn toàn từ Step 2 (kèm tự động Retry tối đa 3 lần nếu lỗi).`
          );
          if (!ok) return;
        }
        appendInstantLogToUI(`🔁 Kích hoạt VIẾT LẠI THỦ CÔNG cho mã [${mid}] (Tự động Retry tối đa 3 lần nếu lỗi)...`, "SCRIPT", "INFO", mid);
        await triggerRunADAS([mid], null, true);
      });
    });

    listEl.querySelectorAll(".btn-idea-thumb").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const mid = btn.dataset.id;
        const origText = btn.innerText;
        btn.disabled = true;
        btn.innerText = "⏳ Đang vẽ...";
        try {
          const res = await fetch(`/api/adas/project/${encodeURIComponent(mid)}/generate-thumbnails?force=true`, {
            method: "POST"
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            alert(data.detail || "Không thể khởi chạy tạo Thumbnail!");
          } else {
            await loadSavedIdeas();
          }
        } catch (e) {
          alert("Lỗi khởi chạy tạo Thumbnail: " + e.message);
        } finally {
          setTimeout(() => {
            btn.disabled = false;
            btn.innerText = origText;
          }, 1500);
        }
      });
    });

    listEl.querySelectorAll(".btn-idea-sync").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const mid = btn.dataset.id;
        const origText = btn.innerText;
        btn.disabled = true;
        btn.innerText = "⏳ Đang check...";
        try {
          const res = await fetch(`/api/adas/project/${encodeURIComponent(mid)}/check-sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ auto_redo: false })
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            alert(`❌ Không thể kiểm định ${mid}: ${err.detail || "Chưa có dữ liệu kịch bản/video"}`);
            return;
          }
          const data = await res.json();
          const rep = data.report || {};
          const sa = rep.sentence_audit || {};
          if (rep.passed) {
            alert(
              `✅ [${mid}] KIỂM ĐỊNH ĐẠT 100%!\n\n` +
              `• Trạng thái: ${rep.status_label}\n` +
              `• Số câu thoại khớp chuẩn: ${sa.passed_sentences}/${sa.total_sentences} câu\n` +
              `• Thời lượng Video MP4: ${rep.video_duration}s\n` +
              `• Thời lượng Voice WAV: ${rep.voice_duration}s\n` +
              `• Độ lệch MP4 vs Voice: ${rep.drift_video_vs_voice_sec}s`
            );
          } else {
            const issuesText = (rep.issues || []).map((x) => "  - " + x).join("\n");
            const confirmRedo = confirm(
              `⚠️ [${mid}] KIỂM ĐỊNH PHÁT HIỆN CHƯA KHỚP:\n\n` +
              `${issuesText}\n` +
              `• Câu đạt chuẩn: ${sa.passed_sentences || 0}/${sa.total_sentences || 0} (Cần làm lại: ${sa.failed_count || 0} câu)\n\n` +
              `👉 Bạn có muốn hệ thống TỰ ĐỘNG LÀM LẠI các câu bị lệch (chế độ 1 Câu = 1 File Voice độc lập) và Render lại Video MP4 ngay bây giờ không?`
            );
            if (confirmRedo) {
              const redoRes = await fetch(`/api/adas/project/${encodeURIComponent(mid)}/check-sync`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  auto_redo: true,
                  video_settings: getCurrentVideoSettings()
                })
              });
              if (redoRes.ok) {
                progressSection.style.display = "block";
                progressMsg.innerText = `[${mid}] 🔄 Đang tự động làm lại các câu lệch Sub-Voice và Render lại Video...`;
              }
            }
          }
        } catch (e) {
          alert("Lỗi kiểm định Sub-Voice: " + e.message);
        } finally {
          btn.disabled = false;
          btn.innerText = origText;
        }
      });
    });

    listEl.querySelectorAll(".btn-idea-view").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const mid = btn.dataset.id;
        await openProjectDetailModal(mid, "seo_pack");
      });
    });

    listEl.querySelectorAll(".btn-idea-folder").forEach((btn) => {
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const mid = btn.dataset.id;
        if (!mid) return;
        const baseOut = (outputDirInput && outputDirInput.value.trim())
          ? outputDirInput.value.trim().replace(/[\\/]+$/, "")
          : "projects";
        const directProjPath = `${baseOut}\\${mid}`;
        await openSystemFolder(directProjPath);
      });
    });

    listEl.querySelectorAll(".btn-idea-del").forEach((btn) => {
      btn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const mid = btn.dataset.id;
        if (!mid) return;
        btn.disabled = true;
        btn.innerText = "⏳";
        appendInstantLogToUI(`🗑️ Đang xóa mã dự án [${mid}] khỏi Kho Dự Án...`, "SCRIPT", "INFO", mid);
        try {
          const res = await fetch("/api/adas/ideas/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ma_id: mid })
          });
          if (res.ok) {
            const data = await res.json();
            renderSavedIdeasList(data.ideas || []);
          } else {
            await loadSavedIdeas();
          }
        } catch (e) {
          console.error("Lỗi xóa mã:", e);
          await loadSavedIdeas();
        }
      });
    });
  }

  async function triggerRenderOnly(maIds = null, onlyUnrendered = false) {
    try {
      const res = await fetch("/api/adas/render-only", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ma_ids: maIds,
          only_unrendered: onlyUnrendered,
          video_settings: getCurrentVideoSettings()
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(data.detail || "Không có kịch bản nào sẵn sàng Render MP4!");
        return;
      }
      switchStudioTab("tab-render");
      if (progressSection) {
        progressSection.style.display = "block";
        progressMsg.innerText = data.message || "🎬 Đang khởi tạo hàng đợi tạo Voice & Render MP4...";
      }
      await loadSavedIdeas();
      await fetchSystemLogs();
    } catch (e) {
      alert("Lỗi khởi chạy Render MP4: " + e.message);
    }
  }

  async function triggerRunADAS(maIds, forceAutoVideo = null, forceRewriteScript = false) {
    if (!maIds || maIds.length === 0) return;
    const accSel = document.getElementById("adas-acc-select");
    const autoVid = document.getElementById("adas-auto-video");
    const outputModeSel = document.getElementById("adas-output-mode-select");
    const lenMode = document.getElementById("adas-length-mode");
    const aiProvSel = document.getElementById("adas-ai-provider-select");
    const chosenProvider = (aiProvSel && aiProvSel.value) ? aiProvSel.value : "chatgpt_web";

    // Nếu người dùng đang chọn chế độ 3 ("render_ready_only" — Chỉ Render các kịch bản đã xong) và không ép chế độ khác
    if (forceAutoVideo === null && !forceRewriteScript && outputModeSel && outputModeSel.value === "render_ready_only") {
      await triggerRenderOnly(maIds, true);
      return;
    }

    let shouldProduceVideo = true;
    if (typeof forceAutoVideo === "boolean") {
      shouldProduceVideo = forceAutoVideo;
    } else if (outputModeSel && outputModeSel.value === "script_seo_thumb_only") {
      shouldProduceVideo = false;
    } else if (autoVid) {
      shouldProduceVideo = autoVid.checked;
    }

    if (!shouldProduceVideo) {
      appendInstantLogToUI(
        `📝 Khởi chạy chế độ CHỈ VIẾT KỊCH BẢN + SEO + THUMBNAIL (Không Render Video) cho ${maIds.length} mã: ${maIds.join(", ")} (Tự động Retry 3 lần nếu lỗi)`,
        "SCRIPT",
        "INFO"
      );
    }

    try {
      const res = await fetch("/api/adas/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ma_ids: maIds,
          preferred_acc_id: accSel && accSel.value ? accSel.value : null,
          auto_produce_video: shouldProduceVideo,
          target_part_min: lenMode ? parseInt(lenMode.value, 10) || 13334 : 13334,
          video_settings: getCurrentVideoSettings(),
          ai_provider: chosenProvider,
          force_rewrite_script: !!forceRewriteScript,
          max_retries: 3
        })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || "Không thể khởi chạy Agent!");
        return;
      }
      await loadSavedIdeas();
      await fetchSystemLogs();
    } catch (e) {
      alert("Lỗi khởi chạy dây chuyền Agent: " + e.message);
    }
  }

  async function openProjectDetailModal(maId, initialTab = "seo_pack") {
    try {
      const res = await fetch(`/api/adas/project/${encodeURIComponent(maId)}`);
      if (!res.ok) return;
      currentProjectDetailData = await res.json();

      const modal = document.getElementById("adas-detail-modal");
      const titleEl = document.getElementById("adas-detail-modal-title");
      if (titleEl) {
        titleEl.innerText = `📄 HỒ SƠ DỰ ÁN & SEO YOUTUBE — MÃ: ${maId}`;
      }
      switchDetailModalTab(initialTab);
      if (modal) modal.style.display = "flex";
    } catch (e) {
      alert("Không thể đọc chi tiết dự án: " + e.message);
    }
  }

  function switchDetailModalTab(tabKey) {
    if (!currentProjectDetailData) return;
    const txtArea = document.getElementById("adas-detail-textarea");
    document.querySelectorAll(".adas-view-tab").forEach((b) => {
      if (b.dataset.tab === tabKey) {
        b.classList.add("active");
        b.style.borderColor = "var(--accent-gold)";
        b.style.color = "var(--accent-gold)";
      } else {
        b.classList.remove("active");
        b.style.borderColor = "rgba(255,255,255,0.2)";
        b.style.color = "#fff";
      }
    });
    const content = currentProjectDetailData[tabKey] || "(Chưa có dữ liệu ở bước này — hãy bấm ▶️ Chạy Step 2→Video để hệ thống tạo)";
    if (txtArea) txtArea.value = content;
  }

  function setupChatGPTAndADASSystem() {
    // 0. Lưu & khôi phục lựa chọn Bộ Máy AI (ChatGPT Web / Gemini 4 Pro / Kết Hợp)
    const aiProvSel = document.getElementById("adas-ai-provider-select");
    if (aiProvSel) {
      const savedProv = localStorage.getItem("adas_ai_provider");
      if (savedProv && ["chatgpt_web", "gemini_4_pro", "hybrid_gemini_chatgpt"].includes(savedProv)) {
        aiProvSel.value = savedProv;
      }
      aiProvSel.addEventListener("change", () => {
        localStorage.setItem("adas_ai_provider", aiProvSel.value);
        appendInstantLogToUI(
          `🧠 Đã chọn cách viết kịch bản: ${aiProvSel.options[aiProvSel.selectedIndex].text}`,
          "SCRIPT",
          "INFO"
        );
      });
    }

    // 0b. Lưu & đồng bộ Chế Độ Chạy (3 Chế Độ: Chỉ Viết KB+Thumb+SEO / Viết + Render Song Song / Chỉ Render Kịch Bản Đã Xong)
    const outputModeSel = document.getElementById("adas-output-mode-select");
    const autoVidChk = document.getElementById("adas-auto-video");
    if (outputModeSel) {
      const savedOutMode = localStorage.getItem("adas_output_mode");
      if (savedOutMode && ["full_video", "script_seo_thumb_only", "render_ready_only"].includes(savedOutMode)) {
        outputModeSel.value = savedOutMode;
        if (autoVidChk) {
          autoVidChk.checked = (savedOutMode !== "script_seo_thumb_only");
        }
      }
      outputModeSel.addEventListener("change", () => {
        const modeVal = outputModeSel.value;
        localStorage.setItem("adas_output_mode", modeVal);
        if (autoVidChk) {
          autoVidChk.checked = (modeVal !== "script_seo_thumb_only");
        }
        const logMsg = modeVal === "script_seo_thumb_only"
          ? "📝 Đã chọn Chế độ 1: CHỈ VIẾT KỊCH BẢN + THUMBNAIL + SEO (Không Render Video)"
          : (modeVal === "render_ready_only"
            ? "🎬 Đã chọn Chế độ 3: CHỈ RENDER CÁC KỊCH BẢN ĐÃ XONG (Không mở AI viết lại)"
            : "🚀 Đã chọn Chế độ 2: VIẾT KỊCH BẢN + THUMBNAIL + SEO & RENDER VIDEO LUÔN (Cứ xong kịch bản nào Render ngay kịch bản đó)");
        appendInstantLogToUI(logMsg, "SCRIPT", "INFO");
      });
    }
    if (autoVidChk && outputModeSel) {
      autoVidChk.addEventListener("change", () => {
        outputModeSel.value = autoVidChk.checked ? "full_video" : "script_seo_thumb_only";
        localStorage.setItem("adas_output_mode", outputModeSel.value);
      });
    }

    // 1. Nút mở từng tài khoản Chrome ChatGPT (Acc #1, Acc #2, Acc #3)
    document.querySelectorAll(".chatgpt-acc-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const accId = btn.dataset.acc || "acc_1";
        const origText = btn.innerText;
        btn.innerText = `⏳ Đang mở ${accId.toUpperCase()}...`;
        try {
          await fetch("/api/chatgpt/open_browser", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ acc_id: accId })
          });
          setTimeout(() => refreshChatGPTAccountsBar(true), 1200);
        } catch (e) {
          btn.innerText = origText;
        }
      });
    });

    // 1b. Nút mở Google Gemini 3.8 High trên cổng Chrome riêng (Gemini #1: 9225, #2: 9226, #3: 9227)
    document.querySelectorAll(".gemini-acc-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const accId = btn.dataset.acc || "acc_1";
        const idx = parseInt(accId.replace("acc_", ""), 10) || 1;
        const port = 9224 + idx;
        btn.innerText = `⏳ Mở Gemini #${idx} (${port})...`;
        try {
          const res = await fetch("/api/gemini/open_browser", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ acc_id: accId })
          });
          const data = await res.json().catch(() => ({}));
          if (res.ok && data.ok) {
            btn.innerText = `✨ Gemini #${idx} (${port}): Đã mở`;
            btn.style.borderColor = "rgba(0, 230, 118, 0.65)";
            btn.style.background = "rgba(0, 230, 118, 0.14)";
            appendInstantLogToUI(
              `✨ Đã mở Google Gemini 3.8 High (https://gemini.google.com/app) trên Cổng riêng ${port} (GEMINI_PROFILE_${idx})!`,
              "CHROME",
              "INFO"
            );
          } else {
            btn.innerText = `✨ GEM ${idx} (${port})`;
          }
          setTimeout(() => refreshChatGPTAccountsBar(true), 1200);
        } catch (e) {
          btn.innerText = `✨ GEM ${idx} (${port})`;
        }
      });
    });

    // 2. Nút Ẩn/Hiện cửa sổ Chrome (-3200, -3200)
    const visBtn = document.getElementById("btn-chatgpt-toggle-vis");
    if (visBtn) {
      visBtn.addEventListener("click", async () => {
        const currentlyVisible = visBtn.dataset.visible === "true";
        const targetVisible = !currentlyVisible;
        await fetch("/api/chatgpt/visibility", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ visible: targetVisible, acc_id: null })
        });
        await refreshChatGPTAccountsBar(true);
      });
    }

    // 3. Nút Dọn Tab Đã Xong
    const sweepBtn = document.getElementById("btn-chatgpt-sweep-tabs");
    if (sweepBtn) {
      sweepBtn.addEventListener("click", async () => {
        const orig = sweepBtn.innerText;
        sweepBtn.innerText = "🧹 Đang dọn...";
        try {
          const res = await fetch("/api/chatgpt/sweep_tabs", { method: "POST" });
          const data = await res.json();
          sweepBtn.innerText = `✅ Đã dọn ${data.closed_tabs || 0} tab`;
          setTimeout(() => { sweepBtn.innerText = orig; }, 2200);
          await refreshChatGPTAccountsBar(true);
        } catch (e) {
          sweepBtn.innerText = orig;
        }
      });
    }

    // 4. Nút Điền Mẫu Chuẩn (Chuẩn Bộ Tiêu Đề Cố Định P01..P20)
    const sampleText = `P20 — 定年退職の日、夫は「お前とは別に暮らす」と言った。妻が差し出した30年前の家計ノートを読んだ夫は、初めて頭を下げた…
VI: Về hưu, chồng đòi sống riêng; sổ chi tiêu 30 năm khiến ông xin lỗi
Keyword: 定年, 熟年離婚, 夫婦, 家計簿 (vidIQ NOT_VERIFIED)
Evidence: 家計ノート / sổ tài chính gia đình
Reveal: Đời vợ có giấc mơ chưa thực hiện, không chỉ đòi công lao
Capacity: PASS`;

    const rawInputEl = document.getElementById("adas-raw-input");
    const customIdEl = document.getElementById("adas-custom-id");
    const detectedBadgeEl = document.getElementById("adas-detected-count-badge");

    const fieldLinePrefixRe = /^(?:(?:\d{1,2}[\.\)\-:]|\-|•|\*)\s*)?(?:vi|vn|dịch\s*ý|tóm\s*tắt|premise|nội\s*dung|keyword|keywords|từ\s*khóa|evidence|proof|vật\s*chứng|bằng\s*chứng|reveal|reveals|ba\s*lớp\s*tiết\s*lộ|3\s*lớp\s*tiết\s*lộ|lớp\s*tiết\s*lộ|tiết\s*lộ|capacity|longform|đánh\s*giá|quan\s*hệ|nhân\s*vật|relation|relationship|trụ\s*cột|nhóm\s*chủ\s*đề|chủ\s*đề|không\s*gian|bối\s*cảnh|setting|xung\s*đột|conflict|câu\s*hỏi|payoff|hệ\s*quả|mức\s*ưu\s*tiên|ưu\s*tiên|priority|trạng\s*thái|status|mã\s*cơ\s*chế|cơ\s*chế|căn\s*cứ|lưu\s*ý|quy\s*tắc|góc\s*thumbnail|nguồn\s*gốc|research_source)\s*[:：]/i;
    const fixedPackHeaderRe = /^(?:(?:#|\*|\-|\•)\s*)?(?:(?:P|ID|IDEA_?|M|T)\s*\d{1,4}|\d{1,3})\s*(?:[—–\-:：\.]+|\s+)\s*.*[\u3040-\u30ff\u4e00-\u9faf].*$/i;
    const titleLabelStartRe = /^(?:(?:\d+[\.\)\-:]|\-|•|\*|#+\s*)\s*)?(?:tiêu\s*đề\s*nhật\s*nháp|tiêu\s*đề\s*nháp|tiêu\s*đề\s*nhật|04\.\s*tiêu\s*đề|title)\s*[:：]/i;

    function countDetectedIdeasInText(text) {
      const t = (text || "").trim();
      if (!t) return 0;
      const lines = t.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      const nonFieldLines = lines.filter(l => !fieldLinePrefixRe.test(l));

      // 1. Đếm theo dòng mở đầu bộ cố định (VD: P01 — ..., P20 — ...)
      const packHeaders = nonFieldLines.filter(l => fixedPackHeaderRe.test(l));
      if (packHeaders.length > 0) {
        return packHeaders.length;
      }

      // 2. Đếm theo nhãn Tiêu đề Nhật nháp:
      const titleLines = nonFieldLines.filter(l => titleLabelStartRe.test(l));
      if (titleLines.length > 0) {
        return titleLines.length;
      }

      // 3. Nếu có các dòng thuộc tính (VI:, Keyword:, Evidence:, Tóm tắt:...) thì đây là 1 bộ
      const hasStruct = lines.some(l => fieldLinePrefixRe.test(l));
      if (hasStruct) {
        return 1;
      }

      // 4. Chỉ khi dán danh sách các dòng tiếng Nhật thuần không có thuộc tính
      const jaLines = nonFieldLines.filter(l => /[\u3040-\u30ff\u4e00-\u9faf]/.test(l) && !/^[-=*#]{3,}$/.test(l));
      return Math.max(1, jaLines.length);
    }

    function refreshDetectedCountBadge() {
      if (!rawInputEl || !detectedBadgeEl) return;
      const c = countDetectedIdeasInText(rawInputEl.value);
      detectedBadgeEl.innerText = c > 1 ? `🔥 Nhận diện: ${c} bộ tiêu đề (SLL)` : `${c} bộ tiêu đề`;
    }

    if (rawInputEl) {
      rawInputEl.addEventListener("input", refreshDetectedCountBadge);
      refreshDetectedCountBadge();
    }

    const fillSampleBtn = document.getElementById("btn-adas-fill-sample");
    if (fillSampleBtn && rawInputEl) {
      fillSampleBtn.addEventListener("click", () => {
        rawInputEl.value = sampleText;
        refreshDetectedCountBadge();
        appendInstantLogToUI("📋 Đã điền mẫu tiêu đề chuẩn vào ô nhập liệu.", "SCRIPT", "INFO");
      });
    }

    const deleteAllBtn = document.getElementById("btn-adas-delete-all");
    if (deleteAllBtn) {
      deleteAllBtn.addEventListener("click", async () => {
        if (!lastSavedIdeasCache || lastSavedIdeasCache.length === 0) {
          alert("Kho dự án hiện đang trống!");
          return;
        }
        if (!confirm(`Bạn có chắc chắn muốn XÓA TẤT CẢ (${lastSavedIdeasCache.length} mã) khỏi danh sách Kho Dự Án không?`)) {
          return;
        }
        deleteAllBtn.disabled = true;
        appendInstantLogToUI(`🗑️ Đang xóa toàn bộ ${lastSavedIdeasCache.length} mã khỏi Kho Dự Án...`, "SCRIPT", "WARN");
        try {
          const res = await fetch("/api/adas/ideas/delete-all", { method: "POST" });
          if (res.ok) {
            const data = await res.json();
            renderSavedIdeasList(data.ideas || []);
          }
        } catch (e) {
          alert("Lỗi khi xóa tất cả: " + e.message);
        } finally {
          deleteAllBtn.disabled = false;
        }
      });
    }

    // 5. Nút Lưu Tiêu Đề & Thông Tin Vào Kho (Hỗ trợ cả Đơn & SLL Hàng Loạt)
    const saveIdeaBtn = document.getElementById("btn-adas-save-idea");
    if (saveIdeaBtn && rawInputEl) {
      saveIdeaBtn.addEventListener("click", async () => {
        const raw = rawInputEl.value.trim();
        if (!raw) {
          alert("Vui lòng dán 1 hoặc nhiều Tiêu đề Nhật nháp / Tóm tắt trước khi lưu!");
          return;
        }
        const cid = customIdEl ? customIdEl.value.trim() : "";
        const res = await fetch("/api/adas/ideas/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: raw, custom_id: cid || null })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          renderSavedIdeasList(data.ideas || []);
          if (customIdEl) customIdEl.value = "";
          const orig = saveIdeaBtn.innerText;
          const cnt = data.saved_count || 1;
          saveIdeaBtn.innerText = cnt > 1
            ? `✅ Đã Lưu Hàng Loạt ${cnt} Mã Vào Kho!`
            : `✅ Đã Lưu Mã ${data.idea.ma_id}!`;
          setTimeout(() => { saveIdeaBtn.innerText = orig; }, 2200);
        } else {
          alert(data.detail || "Lỗi lưu ý tưởng!");
        }
      });
    }

    // 6. Nút Xem Trước Lệnh Step 2 Sẽ Gửi
    const previewStep2Btn = document.getElementById("btn-adas-preview-step2");
    if (previewStep2Btn && rawInputEl) {
      previewStep2Btn.addEventListener("click", async () => {
        const raw = rawInputEl.value.trim();
        if (!raw) {
          alert("Vui lòng dán Tiêu đề Nhật nháp và Tóm tắt để xem lệnh Step 2!");
          return;
        }
        const cid = customIdEl ? customIdEl.value.trim() : "IDEA_PREVIEW";
        const res = await fetch("/api/adas/ideas/preview-prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: raw, custom_id: cid || "IDEA_PREVIEW" })
        });
        if (res.ok) {
          const data = await res.json();
          currentProjectDetailData = {
            ma_id: data.parsed.ma_id,
            step2_prompt: data.step2_prompt,
            seo_pack: "Chưa chạy Step 6",
            script_clean: "Chưa chạy Step 4",
            step2_output: "Chưa chạy Step 2",
            step3_output: "Chưa chạy Step 3",
            step5_output: "Chưa chạy Step 5"
          };
          const modal = document.getElementById("adas-detail-modal");
          const titleEl = document.getElementById("adas-detail-modal-title");
          if (titleEl) titleEl.innerText = `📋 XEM TRƯỚC LỆNH PROMPT STEP 2 — MÃ: ${data.parsed.ma_id}`;
          switchDetailModalTab("step2_prompt");
          if (modal) modal.style.display = "flex";
        }
      });
    }

    // 7. Nút Lưu & Chỉ Viết KB + SEO + Thumbnail (Không Render Video)
    const saveAndScriptOnlyBtn = document.getElementById("btn-adas-save-and-script-only");
    if (saveAndScriptOnlyBtn && rawInputEl) {
      saveAndScriptOnlyBtn.addEventListener("click", async () => {
        const raw = rawInputEl.value.trim();
        if (!raw) {
          alert("Vui lòng dán 1 hoặc nhiều Tiêu đề Nhật nháp / Tóm tắt!");
          return;
        }
        const cid = customIdEl ? customIdEl.value.trim() : "";
        const res = await fetch("/api/adas/ideas/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: raw, custom_id: cid || null })
        });
        const data = await res.json();
        if (res.ok && data.success && data.idea) {
          renderSavedIdeasList(data.ideas || []);
          if (customIdEl) customIdEl.value = "";
          const idsToRun = (data.saved_ids && data.saved_ids.length > 0) ? data.saved_ids : [data.idea.ma_id];
          await triggerRunADAS(idsToRun, false);
        } else {
          alert(data.detail || "Không thể lưu ý tưởng!");
        }
      });
    }

    // 7b. Nút Lưu & Chạy Ngay (Hỗ trợ cả 1 mã hoặc SLL nhiều mã vừa dán)
    const saveAndRunBtn = document.getElementById("btn-adas-save-and-run");
    if (saveAndRunBtn && rawInputEl) {
      saveAndRunBtn.addEventListener("click", async () => {
        const raw = rawInputEl.value.trim();
        if (!raw) {
          alert("Vui lòng dán 1 hoặc nhiều Tiêu đề Nhật nháp / Tóm tắt!");
          return;
        }
        const cid = customIdEl ? customIdEl.value.trim() : "";
        const res = await fetch("/api/adas/ideas/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: raw, custom_id: cid || null })
        });
        const data = await res.json();
        if (res.ok && data.success && data.idea) {
          renderSavedIdeasList(data.ideas || []);
          if (customIdEl) customIdEl.value = "";
          const idsToRun = (data.saved_ids && data.saved_ids.length > 0) ? data.saved_ids : [data.idea.ma_id];
          await triggerRunADAS(idsToRun, null);
        } else {
          alert(data.detail || "Không thể lưu ý tưởng!");
        }
      });
    }

    // 8. Nút Mở Folder Kịch Bản, Nhập Từ Máy Khác, Khôi Phục Kịch Bản Cũ, Render Tất Cả Kịch Bản Đã Xong & Nút Chạy Đa Luồng (Kịch Bản -> Voice)
    const openProjectsDirBtn = document.getElementById("btn-adas-open-projects-dir");
    if (openProjectsDirBtn) {
      openProjectsDirBtn.addEventListener("click", async () => {
        const baseOut = (outputDirInput && outputDirInput.value.trim())
          ? outputDirInput.value.trim().replace(/[\\/]+$/, "")
          : "projects";
        await openSystemFolder(baseOut);
      });
    }

    const importExternalBtn = document.getElementById("btn-adas-import-external");
    if (importExternalBtn) {
      importExternalBtn.addEventListener("click", async () => {
        const origTxt = importExternalBtn.innerText;
        importExternalBtn.disabled = true;
        importExternalBtn.innerText = "📂 Đang chọn thư mục...";
        try {
          const browseRes = await fetch("/api/browse-directory", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "Chọn Thư Mục Chứa Kịch Bản + Thumbnail + SEO Từ Máy Khác" })
          });
          const browseData = await browseRes.json().catch(() => ({}));
          if (!browseData.path) {
            return;
          }
          importExternalBtn.innerText = "⏳ Đang nạp dự án...";
          appendInstantLogToUI(`📥 Đang nhập Kịch bản + Thumbnail + SEO từ thư mục: ${browseData.path}...`, "SCRIPT", "INFO");
          const impRes = await fetch("/api/adas/ideas/import-external", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder_path: browseData.path })
          });
          const impData = await impRes.json().catch(() => ({}));
          if (impRes.ok && impData.success) {
            renderSavedIdeasList(impData.ideas || []);
            const idsStr = (impData.imported_ids || []).join(", ");
            alert(
              `✅ Đã nhập thành công ${impData.imported_count} dự án (Kịch bản + Thumbnail + SEO) từ máy khác!\n\n` +
              `• Các mã vừa nạp: ${idsStr || "(Đã đồng bộ)"}\n` +
              `• Tổng số dự án trong kho: ${impData.total_count} mã\n\n` +
              `👉 Bạn có thể bấm ngay "🎬 Render" trên từng dòng hoặc "🎬 Render Tất Cả Đã Xong"!`
            );
          } else {
            alert(impData.detail || "Không tìm thấy kịch bản hợp lệ trong thư mục đã chọn!");
          }
        } catch (err) {
          alert("Lỗi khi nhập dự án từ máy khác: " + err.message);
        } finally {
          importExternalBtn.disabled = false;
          importExternalBtn.innerText = origTxt;
        }
      });
    }

    async function handleRefreshProjectsFolder(btnEl) {
      if (!btnEl) return;
      const origHtml = btnEl.innerHTML;
      btnEl.disabled = true;
      btnEl.innerText = "⏳ Đang cập nhật...";
      try {
        const customOut = (outputDirInput && outputDirInput.value) ? outputDirInput.value.trim() : "";
        const res = await fetch("/api/adas/ideas/sync-folder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder_path: customOut || "" })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          renderSavedIdeasList(data.ideas || []);
          appendInstantLogToUI(
            `🔄 Đã cập nhật lại thư mục projects/: Hiện có ${data.total_count} dự án (${data.script_done_count} kịch bản xong, ${data.video_done_count} video MP4, +${data.restored_count || 0} mới, -${data.removed_count || 0} đã xóa).`,
            "SCRIPT",
            "INFO"
          );
          alert(
            `✅ Đã cập nhật lại thư mục dự án thành công!\n\n` +
            `• Thư mục: ${data.projects_dir || "projects/"}\n` +
            `• Tổng số folder hiện có: ${data.total_count} mã\n` +
            `• Kịch bản đã viết xong (Sẵn sàng Render): ${data.script_done_count} kịch bản\n` +
            `• Video MP4 đã xuất: ${data.video_done_count} video\n` +
            `• Đã thêm mới: +${data.restored_count || 0} | Đã dọn folder bị xóa: -${data.removed_count || 0}`
          );
        }
      } catch (err) {
        alert("Lỗi khi cập nhật thư mục dự án: " + err.message);
      } finally {
        btnEl.disabled = false;
        btnEl.innerHTML = origHtml;
      }
    }

    ["btn-adas-refresh-folder", "btn-adas-restore-scripts", "btn-render-refresh-folder"].forEach((btnId) => {
      const b = document.getElementById(btnId);
      if (b) {
        b.addEventListener("click", () => handleRefreshProjectsFolder(b));
      }
    });

    async function handleCheckAndRepairAllProjects(btnEl) {
      if (!btnEl) return;
      if (!confirm(
        "🛡️ BẠN CÓ MUỐN QUÉT & DỌN SẠCH TOÀN BỘ KỊCH BẢN + VIDEO LỖI (PHƯƠNG ÁN 1)?\n\n" +
        "Hệ thống sẽ thực hiện tự động:\n" +
        "1️⃣ Quét toàn bộ kịch bản (.txt) và phụ đề (.srt) trong kho để xóa sạch các dòng [LOCKED_TITLE], PART A/B/C, STEP 3 bị rò rỉ.\n" +
        "2️⃣ Với các dự án ĐÃ TẠO VIDEO (.mp4) hoặc VOICE (.wav) bị đọc nhầm câu tiêu đề: Tự động cắt bỏ chính xác giây đọc nhầm bằng FFmpeg Stream Copy (Phương án 1 — chỉ mất vài giây/video, không cần render lại từ đầu).\n" +
        "3️⃣ Xuất báo cáo chi tiết tại BAO_CAO_CHECK_VA_DON_TOAN_BO.txt.\n\n" +
        "Bấm OK để bắt đầu quét và dọn sạch ngay!"
      )) {
        return;
      }

      const allRepairBtns = ["btn-adas-check-repair-all", "btn-check-repair-all-nav"]
        .map((id) => document.getElementById(id))
        .filter(Boolean);
      const origHtmlMap = new Map();
      allRepairBtns.forEach((b) => {
        origHtmlMap.set(b, b.innerHTML);
        b.disabled = true;
        b.innerText = "⏳ Đang quét & dọn lỗi...";
      });

      appendInstantLogToUI(
        "🛡️ [CHECK TOÀN BỘ - PHƯƠNG ÁN 1] Đang quét toàn bộ kịch bản (.txt/.srt) và cắt dọn đoạn đọc nhầm [LOCKED_TITLE] trong file Voice (.wav) & Video (.mp4)...",
        "SYSTEM",
        "INFO"
      );

      try {
        const res = await fetch("/api/adas/check-and-repair-all", {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.success) {
          if (Array.isArray(data.ideas)) {
            renderSavedIdeasList(data.ideas);
          }
          const repairedScriptStr = (data.repaired_script_ids && data.repaired_script_ids.length > 0)
            ? data.repaired_script_ids.join(", ")
            : "Không có (Đã sạch 100%)";
          const repairedVideoStr = (data.repaired_video_ids && data.repaired_video_ids.length > 0)
            ? data.repaired_video_ids.join(", ")
            : "Không có video nào bị dính";
          const repairedVoiceStr = (data.repaired_voice_ids && data.repaired_voice_ids.length > 0)
            ? data.repaired_voice_ids.join(", ")
            : "Không có file voice nào bị dính";

          appendInstantLogToUI(
            `✅ [CHECK TOÀN BỘ HOÀN TẤT] Đã quét ${data.total_projects || 0} dự án (${data.elapsed_sec || 0}s) | ` +
            `Sửa kịch bản: ${data.scripts_repaired_count || 0} mã (${data.total_leaked_lines_removed || 0} dòng) | ` +
            `Dọn phụ đề SRT: ${data.srts_repaired_count || 0} mã | ` +
            `Cắt dọn Voice WAV: ${data.voices_repaired_count || 0} mã | ` +
            `Cắt dọn Video MP4: ${data.videos_repaired_count || 0} video.`,
            "SYSTEM",
            "INFO"
          );

          alert(
            `🎉 HOÀN TẤT CHECK & DỌN SẠCH TOÀN BỘ (PHƯƠNG ÁN 1)!\n\n` +
            `• Tổng số dự án đã kiểm tra: ${data.total_projects || 0} dự án (Thời gian: ${data.elapsed_sec || 0}s)\n` +
            `• Số kịch bản (.txt) đã lọc sạch [LOCKED_TITLE]: ${data.scripts_repaired_count || 0} kịch bản (${data.total_leaked_lines_removed || 0} dòng lỗi)\n` +
            `• Số phụ đề (.srt) đã dọn & dịch khớp thời gian: ${data.srts_repaired_count || 0} file\n` +
            `• Số file Voice (.wav) đã cắt bỏ đoạn đọc nhầm: ${data.voices_repaired_count || 0} file\n` +
            `• Số Video (.mp4) đã cắt bỏ đoạn đọc nhầm: ${data.videos_repaired_count || 0} video\n\n` +
            `📌 Mã kịch bản đã sửa: ${repairedScriptStr}\n` +
            `📌 Mã Voice đã dọn: ${repairedVoiceStr}\n` +
            `📌 Mã Video MP4 đã dọn: ${repairedVideoStr}\n\n` +
            `📄 Báo cáo chi tiết đã lưu tại:\n${data.report_path || "BAO_CAO_CHECK_VA_DON_TOAN_BO.txt"}`
          );
        } else {
          alert("❌ Lỗi khi Check & Dọn Toàn Bộ: " + (data.detail || data.error || "Không xác định"));
        }
      } catch (err) {
        alert("❌ Lỗi kết nối khi Check & Dọn Toàn Bộ: " + err.message);
      } finally {
        allRepairBtns.forEach((b) => {
          b.disabled = false;
          if (origHtmlMap.has(b)) {
            b.innerHTML = origHtmlMap.get(b);
          }
        });
      }
    }

    ["btn-adas-check-repair-all", "btn-check-repair-all-nav"].forEach((btnId) => {
      const b = document.getElementById(btnId);
      if (b) {
        b.addEventListener("click", () => handleCheckAndRepairAllProjects(b));
      }
    });

    const retryErrorsBtn = document.getElementById("btn-adas-retry-errors");
    if (retryErrorsBtn) {
      retryErrorsBtn.addEventListener("click", async () => {
        const res = await fetch("/api/adas/ideas");
        if (!res.ok) return;
        const data = await res.json();
        const errOrIncompleteIds = (data.ideas || [])
          .filter((it) => {
            const hasFullScript = !!it.has_script && (it.pure_char_count || 0) >= 35000;
            const isErr = it.status === "ERROR" || it.status === "ERROR_VIDEO" || it.status === "PARTIAL_SCRIPT";
            return isErr || !hasFullScript;
          })
          .map((it) => it.ma_id);
        if (errOrIncompleteIds.length === 0) {
          alert("✅ Tuyệt vời! Không có kịch bản nào bị lỗi hay thiếu Part trong kho (Tất cả đã hoàn thành đủ 3 Part >= 35,000 chữ).\n\n👉 Nếu bạn muốn viết lại từ đầu cho một mã cụ thể, hãy bấm nút '🔁 Viết Lại' ngay trên dòng của mã đó!");
          return;
        }
        appendInstantLogToUI(
          `🔁 Kích hoạt viết lại / chạy bù cho ${errOrIncompleteIds.length} mã lỗi/thiếu: ${errOrIncompleteIds.join(", ")} (Tự động Retry tối đa 3 lần)...`,
          "SCRIPT",
          "INFO"
        );
        await triggerRunADAS(errOrIncompleteIds, null, false);
      });
    }

    const renderReadyBtn = document.getElementById("btn-adas-render-ready");
    if (renderReadyBtn) {
      renderReadyBtn.addEventListener("click", async () => {
        const res = await fetch("/api/adas/ideas");
        if (!res.ok) return;
        const data = await res.json();
        const readyIds = (data.ideas || [])
          .filter((it) => (!!it.has_script && (it.pure_char_count || 0) >= 35000) && (!it.has_video_mp4 || it.status !== "COMPLETED_VIDEO"))
          .map((it) => it.ma_id);
        if (readyIds.length === 0) {
          alert("Hiện chưa có dự án nào đã viết xong đủ 3 Part kịch bản (>= 35,000 chữ) mà đang chờ xuất MP4!\n\n• Với các dự án đang thiếu Part B/C (màu cam), hãy bấm '▶️ Viết Tiếp' hoặc '▶️ Chạy Đa Luồng' để hoàn thành đủ 3 Part trước.");
          return;
        }
        await triggerRenderOnly(readyIds, true);
      });
    }

    const scriptOnlyAllBtn = document.getElementById("btn-adas-script-only-all");
    if (scriptOnlyAllBtn) {
      scriptOnlyAllBtn.addEventListener("click", async () => {
        const res = await fetch("/api/adas/ideas");
        if (!res.ok) return;
        const data = await res.json();
        const pendingScriptIds = (data.ideas || [])
          .filter((it) => {
            const hasFullScript = !!it.has_script && (it.pure_char_count || 0) >= 35000;
            const hasThumb = !!it.has_thumbnail;
            const hasSeo = !!it.has_seo;
            return !(hasFullScript && hasThumb && hasSeo);
          })
          .map((it) => it.ma_id);
        if (pendingScriptIds.length === 0) {
          alert("Tất cả các mã trong kho đã có đủ Kịch bản 3 Part (>= 35,000 chữ) + SEO + Thumbnail!\n\n👉 Bạn có thể copy thư mục sang máy khác hoặc bấm '🎬 Render Tất Cả Đã Xong' nếu muốn xuất MP4.");
          return;
        }
        await triggerRunADAS(pendingScriptIds, false);
      });
    }

    const runAllBtn = document.getElementById("btn-adas-run-all");
    if (runAllBtn) {
      runAllBtn.addEventListener("click", async () => {
        const res = await fetch("/api/adas/ideas");
        if (!res.ok) return;
        const data = await res.json();
        const pendingIds = (data.ideas || [])
          .filter((it) => !it.has_video_mp4 && it.status !== "COMPLETED_VIDEO")
          .map((it) => it.ma_id);
        if (pendingIds.length === 0) {
          alert("Tất cả các mã trong kho đã hoàn tất xuất Video MP4! Bạn có thể bấm '🎬 Render MP4' trên từng mã nếu muốn xuất lại.");
          return;
        }
        await triggerRunADAS(pendingIds, null);
      });
    }

    const stopBtn = document.getElementById("btn-adas-stop");
    if (stopBtn) {
      stopBtn.addEventListener("click", async () => {
        await fetch("/api/adas/stop", { method: "POST" });
      });
    }

    // 9. Modal Xem Chi Tiết Kết Quả & Đẩy Sang Bàn Sản Xuất Video
    const closeDetailBtn = document.getElementById("btn-close-adas-detail-modal");
    const detailModal = document.getElementById("adas-detail-modal");
    if (closeDetailBtn && detailModal) {
      closeDetailBtn.addEventListener("click", () => { detailModal.style.display = "none"; });
    }

    document.querySelectorAll(".adas-view-tab").forEach((b) => {
      b.addEventListener("click", () => switchDetailModalTab(b.dataset.tab));
    });

    const copyDetailBtn = document.getElementById("btn-adas-copy-detail");
    if (copyDetailBtn) {
      copyDetailBtn.addEventListener("click", () => {
        const txtArea = document.getElementById("adas-detail-textarea");
        if (txtArea && txtArea.value) {
          navigator.clipboard.writeText(txtArea.value);
          const orig = copyDetailBtn.innerText;
          copyDetailBtn.innerText = "✅ Đã Copy!";
          setTimeout(() => { copyDetailBtn.innerText = orig; }, 1800);
        }
      });
    }

    const pushToSingleBtn = document.getElementById("btn-adas-push-to-single");
    if (pushToSingleBtn) {
      pushToSingleBtn.addEventListener("click", () => {
        if (!currentProjectDetailData || !currentProjectDetailData.script_clean) {
          alert("Dự án này chưa có kịch bản tiếng Nhật hoàn chỉnh (Step 4).");
          return;
        }
        currentMode = "single";
        if (scriptTextInput) {
          scriptTextInput.value = currentProjectDetailData.script_clean;
          scriptTextInput.dispatchEvent(new Event("input"));
        }
        if (legacyScriptTextInput && legacyScriptTextInput !== scriptTextInput) {
          legacyScriptTextInput.value = currentProjectDetailData.script_clean;
        }
        if (projectNameInput && currentProjectDetailData.ma_id) {
          projectNameInput.value = currentProjectDetailData.ma_id;
        }
        if (legacyProjectNameInput && currentProjectDetailData.ma_id && legacyProjectNameInput !== projectNameInput) {
          legacyProjectNameInput.value = currentProjectDetailData.ma_id;
        }
        if (detailModal) detailModal.style.display = "none";
        switchStudioTab("tab-render");
        if (tabSingle) tabSingle.click();
      });
    }

    // 10. Modal Cấu Hình Mẫu Lệnh Step 2
    const openTplBtn = document.getElementById("btn-open-step2-tpl-modal");
    const closeTplBtn = document.getElementById("btn-close-step2-tpl-modal");
    const tplModal = document.getElementById("step2-template-modal");
    const tplTextarea = document.getElementById("step2-template-textarea");
    const saveTplBtn = document.getElementById("btn-save-step2-tpl");

    if (openTplBtn && tplModal && tplTextarea) {
      openTplBtn.addEventListener("click", async () => {
        const res = await fetch("/api/adas/template/step2");
        if (res.ok) {
          const data = await res.json();
          tplTextarea.value = data.template_text || "";
        }
        tplModal.style.display = "flex";
      });
    }
    if (closeTplBtn && tplModal) {
      closeTplBtn.addEventListener("click", () => { tplModal.style.display = "none"; });
    }
    if (saveTplBtn && tplTextarea && tplModal) {
      saveTplBtn.addEventListener("click", async () => {
        const res = await fetch("/api/adas/template/step2", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ template_text: tplTextarea.value })
        });
        if (res.ok) {
          tplModal.style.display = "none";
        }
      });
    }

    // Khởi chạy tải dữ liệu ban đầu & lặp kiểm tra trạng thái 3 Acc
    refreshChatGPTAccountsBar(false);
    loadSavedIdeas();
    setInterval(() => refreshChatGPTAccountsBar(false), 6000);
  }

  // ============================================================================
  // 12. TRUNG TÂM NHẬT KÝ HỆ THỐNG, TELEMETRY RADIAL GAUGES & DIAGNOSTICS
  // ============================================================================
  let currentLogLevelFilter = "ALL";
  let currentLogCatFilter = "ALL";
  let latestLogEntriesCache = [];
  let latestLogPathsCache = null;
  let isTerminalAutoScroll = true;

  function setupTelemetryPolling() {
    const CIRCUMFERENCE = 226.2; // 2 * Math.PI * 36

    function updateSvgRadialArc(el, pct) {
      if (!el) return;
      if (el.tagName && el.tagName.toLowerCase() === "path") {
        el.setAttribute("stroke-dasharray", `${pct}, 100`);
      } else {
        const offset = CIRCUMFERENCE * (1 - pct / 100);
        el.setAttribute("stroke-dashoffset", offset.toFixed(1));
      }
    }

    async function pollTelemetryNow() {
      try {
        const res = await fetch("/api/telemetry");
        if (!res.ok) return;
        const t = await res.json();

        // 1. GPU Gauge & VRAM
        const gpuPct = Math.max(0, Math.min(100, Math.round(t.gpu_load_pct ?? t.gpu_percent ?? 0)));
        const gpuCircle = document.getElementById("gauge-gpu-circle");
        const gpuPctEl = document.getElementById("gauge-gpu-pct");
        const gpuTempEl = document.getElementById("gauge-gpu-temp");
        const gpuNameEl = document.getElementById("gauge-gpu-name");
        const vramTextEl = document.getElementById("gauge-vram-text");
        const vramBarEl = document.getElementById("gauge-vram-bar");
        const renderVramBar = document.getElementById("render-vram-bar");
        const renderVramText = document.getElementById("render-vram-text");
        const gpuFanEl = document.getElementById("telemetry-gpu-fan");

        if (gpuPctEl) gpuPctEl.innerText = `${gpuPct}%`;
        updateSvgRadialArc(gpuCircle, gpuPct);
        if (gpuTempEl && t.gpu_temp_c) gpuTempEl.innerText = `${t.gpu_temp_c}°C`;
        if (gpuNameEl && t.gpu_name) gpuNameEl.innerText = t.gpu_name;
        if (t.vram_total_gb) {
          const vramStr = `VRAM: ${Number(t.vram_used_gb || 0).toFixed(1)} / ${Number(t.vram_total_gb).toFixed(1)} GB`;
          const vramPct = Math.max(4, Math.min(100, Math.round(t.vram_pct ?? t.vram_percent ?? 0)));
          if (vramTextEl) vramTextEl.innerText = vramStr;
          if (vramBarEl) vramBarEl.style.width = `${vramPct}%`;
          if (renderVramBar) renderVramBar.style.width = `${vramPct}%`;
          if (renderVramText) renderVramText.innerText = `${Number(t.vram_used_gb || 0).toFixed(1)} / ${Number(t.vram_total_gb).toFixed(1)} GB`;
        }
        if (gpuFanEl && t.gpu_fan_pct !== undefined) {
          const rpmEst = Math.round(900 + (t.gpu_fan_pct / 100) * 1800);
          gpuFanEl.innerText = `${t.gpu_fan_pct}% (${rpmEst} RPM)`;
        }

        // 2. System Memory Gauge
        const ramPct = Math.max(0, Math.min(100, Math.round(t.ram_pct ?? t.ram_percent ?? 0)));
        const ramCircle = document.getElementById("gauge-ram-circle");
        const ramPctEl = document.getElementById("gauge-ram-pct");
        const ramTextEl = document.getElementById("gauge-ram-text");
        const ramBarEl = document.getElementById("gauge-ram-bar");

        if (ramPctEl) ramPctEl.innerText = `${ramPct}%`;
        updateSvgRadialArc(ramCircle, ramPct);
        if (ramTextEl && t.ram_total_gb) {
          ramTextEl.innerText = `${Number(t.ram_used_gb || 0).toFixed(1)} / ${Number(t.ram_total_gb).toFixed(1)} GB RAM`;
        }
        if (ramBarEl) ramBarEl.style.width = `${Math.max(4, ramPct)}%`;

        // 3. CPU Gauge
        const cpuPct = Math.max(0, Math.min(100, Math.round(t.cpu_load_pct ?? t.cpu_percent ?? 0)));
        const cpuCircle = document.getElementById("gauge-cpu-circle");
        const cpuPctEl = document.getElementById("gauge-cpu-pct");
        const cpuThreadsEl = document.getElementById("gauge-cpu-threads");
        const cpuNameEl = document.getElementById("gauge-cpu-name");
        const cpuBarEl = document.getElementById("gauge-cpu-bar");
        const headerCpuThreads = document.getElementById("header-cpu-threads");

        if (cpuPctEl) cpuPctEl.innerText = `${cpuPct}%`;
        updateSvgRadialArc(cpuCircle, cpuPct);
        if (cpuThreadsEl && t.cpu_threads) cpuThreadsEl.innerText = `${t.cpu_threads} Th`;
        if (headerCpuThreads && t.cpu_threads) headerCpuThreads.innerText = `${t.cpu_threads} CORES`;
        if (cpuNameEl && t.cpu_name) cpuNameEl.innerText = t.cpu_name;
        if (cpuBarEl) cpuBarEl.style.width = `${Math.max(4, cpuPct)}%`;

        // 4. CDP AI Chrome Gauge
        const cdpCountEl = document.getElementById("gauge-cdp-count");
        const cdpPortsBox = document.getElementById("gauge-cdp-ports-status");
        if (cdpCountEl && t.cdp_active_count !== undefined) {
          cdpCountEl.innerText = `${t.cdp_active_count}/3 ACTIVE`;
        }
        if (cdpPortsBox && Array.isArray(t.cdp_ports)) {
          cdpPortsBox.innerHTML = t.cdp_ports.map((p) => {
            const label = p.label || p.acc || `P${p.port}`;
            if (p.open) {
              return `<span class="flex items-center gap-1 text-[10px] font-mono text-primary-container"><span class="w-1.5 h-1.5 rounded-full bg-primary-container shadow-[0_0_6px_rgba(0,255,135,0.8)]"></span>${label} Ready</span>`;
            }
            return `<span class="flex items-center gap-1 text-[10px] font-mono text-on-surface-variant"><span class="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>${label} Idle</span>`;
          }).join("");
        }

        // Update GPU balancer badge in Tab 3
        const balEl = document.getElementById("gpu-balancer-badge");
        if (balEl) {
          balEl.innerText = `TỰ CÂN ĐỐI 90%: GPU ${gpuPct}% • CPU ${cpuPct}%`;
        }
      } catch (e) {
        // Ignore transient errors
      }
    }

    pollTelemetryNow();
    setInterval(pollTelemetryNow, 4000);
  }

  function formatLogEntryHtml(e) {
    const lvl = e.level || "INFO";
    const color =
      lvl === "ERROR"
        ? "#ff6b6b"
        : lvl === "WARN"
        ? "#ffd54f"
        : e.category === "VIDEO" || e.category === "VOICE" || e.category === "RENDER"
        ? "#00e676"
        : "#00e5ff";
    const projBadge = e.project_id ? `<strong style="color: var(--accent-gold);">[${e.project_id}]</strong> ` : "";
    const safeMsg = (e.message || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<div style="margin-bottom: 3px; border-bottom: 1px solid rgba(255,255,255,0.04); padding-bottom: 2px;">
      <span style="color: #8899ac;">[${e.timestamp || ""}]</span>
      <span style="color: ${color}; font-weight: 700;">[${lvl}/${e.category || "SYS"}]</span>
      ${projBadge}<span style="color: ${lvl === "ERROR" ? "#ff9e9e" : "#e2e8f0"};">${safeMsg}</span>
    </div>`;
  }

  function entryMatchesFilter(e) {
    if (!e) return false;
    const lvl = (e.level || "INFO").toUpperCase();
    const cat = (e.category || "SYSTEM").toUpperCase();
    if (currentLogLevelFilter === "ERROR") {
      if (lvl !== "ERROR" && lvl !== "WARN" && lvl !== "WARNING" && !(e.message || "").includes("❌") && !(e.message || "").includes("⚠️")) {
        return false;
      }
    }
    if (currentLogCatFilter && currentLogCatFilter !== "ALL") {
      if (currentLogCatFilter === "VIDEO") {
        if (!["VIDEO", "VOICE", "RENDER", "STOCK"].includes(cat)) return false;
      } else if (cat !== currentLogCatFilter) {
        return false;
      }
    }
    return true;
  }

  function pushLogEntryToConsole(entry) {
    if (!entry) return;
    const last = latestLogEntriesCache[latestLogEntriesCache.length - 1];
    if (last && last.timestamp === entry.timestamp && last.message === entry.message) {
      return;
    }
    latestLogEntriesCache.push(entry);
    if (latestLogEntriesCache.length > 300) {
      latestLogEntriesCache = latestLogEntriesCache.slice(-300);
    }
    const lineCntEl = document.getElementById("log-line-count");
    if (lineCntEl) lineCntEl.innerText = `${latestLogEntriesCache.length} dòng`;
    if (!entryMatchesFilter(entry)) return;
    const consoleEl = document.getElementById("system-log-console");
    if (!consoleEl) return;
    if (consoleEl.innerText.includes("Chưa có bản ghi nhật ký") || consoleEl.innerText.includes("Đang tải nhật ký")) {
      consoleEl.innerHTML = "";
    }
    consoleEl.insertAdjacentHTML("beforeend", formatLogEntryHtml(entry));
    if (isTerminalAutoScroll) {
      consoleEl.scrollTop = consoleEl.scrollHeight;
    }
  }

  function appendInstantLogToUI(message, category = "SYSTEM", level = "INFO", projectId = "") {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    const ts = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    pushLogEntryToConsole({
      timestamp: ts,
      level: level,
      category: category,
      project_id: projectId,
      message: message
    });
  }

  async function fetchSystemLogs() {
    const consoleEl = document.getElementById("system-log-console");
    if (!consoleEl) return;
    try {
      const qs = new URLSearchParams({
        limit: "200",
        level: currentLogLevelFilter,
        category: currentLogCatFilter
      });
      const res = await fetch(`/api/logs?${qs.toString()}`);
      if (!res.ok) return;
      const data = await res.json();
      latestLogEntriesCache = data.entries || [];
      latestLogPathsCache = data.log_paths || null;
      const lineCntEl = document.getElementById("log-line-count");
      if (lineCntEl) lineCntEl.innerText = `${latestLogEntriesCache.length} dòng`;

      if (latestLogEntriesCache.length === 0) {
        consoleEl.innerHTML = `<div style="color: var(--text-secondary);">Chưa có bản ghi nhật ký nào khớp bộ lọc hiện tại.</div>`;
        return;
      }

      const wasAtBottom = consoleEl.scrollHeight - consoleEl.scrollTop - consoleEl.clientHeight < 60;
      consoleEl.innerHTML = latestLogEntriesCache.map((e) => formatLogEntryHtml(e)).join("");

      if (isTerminalAutoScroll && wasAtBottom) {
        consoleEl.scrollTop = consoleEl.scrollHeight;
      }
    } catch (e) {
      // Bỏ qua nếu server đang bận
    }
  }

  async function triggerInstallMissingLibs() {
    const btn = document.getElementById("btn-install-missing-libs");
    const origHtml = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>Đang cài đặt...`;
    }
    appendInstantLogToUI("⚡ Đang gửi yêu cầu kiểm tra và cài đặt các thư viện thiếu / PyTorch CUDA...", "SYSTEM", "INFO");
    try {
      const res = await fetch("/api/diagnostics/install-missing?install_cuda=true", { method: "POST" });
      const data = await res.json();
      alert(data.message || "Đã bắt đầu kiểm tra và cài đặt thư viện trong nền. Vui lòng theo dõi bảng Nhật Ký Hệ Thống!");
      await fetchSystemLogs();
    } catch (e) {
      alert("Lỗi khi gọi cài đặt thư viện: " + e.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml || `<span class="material-symbols-outlined text-[16px]">build_circle</span>Cài Thư Viện Thiếu &amp; CUDA`;
      }
    }
  }

  async function runSystemDiagnosticsUI(silentOnStartup = false) {
    const box = document.getElementById("diagnostics-report-box");
    const btn = document.getElementById("btn-run-diagnostics");
    const summaryBadgesEl = document.getElementById("diag-summary-badges");
    const detailsListEl = document.getElementById("diag-details-list");
    const passCounterEl = document.getElementById("diag-pass-counter");
    const origBtnHtml = btn ? btn.innerHTML : "";

    if (!silentOnStartup && btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>Đang kiểm tra...`;
    }

    try {
      const res = await fetch("/api/diagnostics");
      const data = await res.json();
      const checks = data.checks || [];
      const missingReqs = data.missing_requirements || [];

      const okCount = checks.filter(c => c.status === "OK").length;
      if (passCounterEl && checks.length > 0) {
        passCounterEl.innerText = `PASS: ${okCount}/${checks.length} CHECKS`;
      }

      if (summaryBadgesEl && checks.length > 0) {
        summaryBadgesEl.innerHTML = checks.slice(0, 6).map((c) => {
          const isOk = c.status === "OK";
          const isWarn = c.status === "WARN";
          const cls = isOk
            ? "bg-primary-container/10 border-primary-container/30 text-primary-container"
            : isWarn
            ? "bg-tertiary/10 border-tertiary/30 text-tertiary"
            : "bg-error/10 border-error/30 text-error";
          const dotCls = isOk ? "bg-primary-container" : isWarn ? "bg-tertiary" : "bg-error";
          return `<span class="px-2.5 py-1 rounded-md border ${cls} font-mono text-[11px] font-bold flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full ${dotCls}"></span>${c.name}: ${c.status}
          </span>`;
        }).join("");
      }

      if (detailsListEl && checks.length > 0) {
        const missingBannerHtml = missingReqs.length > 0
          ? `<div class="p-2.5 rounded-lg bg-error-container/25 border border-error/40 text-xs space-y-1.5 mb-2">
              <div class="font-bold text-error">⚠️ PHÁT HIỆN ${missingReqs.length} THƯ VIỆN / PHẦN MỀM TỐI ƯU GPU CẦN CÀI ĐẶT:</div>
              ${missingReqs.map((r) => `
                <div class="p-1.5 rounded bg-surface-container-lowest/80 border border-outline-variant/20">
                  <div class="font-bold text-tertiary">🔸 ${r.title}</div>
                  <div class="text-on-surface-variant text-[10px]">• ${r.reason}</div>
                </div>
              `).join("")}
              <button type="button" id="btn-diag-auto-install" class="px-3 py-1 rounded bg-primary-container text-on-primary-container font-bold text-xs">
                ⚡ Tự Động Tải &amp; Cài Thư Viện Thiếu / PyTorch CUDA Ngay
              </button>
            </div>`
          : "";

        detailsListEl.innerHTML = missingBannerHtml + checks.map((c) => {
          const isOk = c.status === "OK";
          const isWarn = c.status === "WARN";
          const iconName = isOk ? "check_circle" : isWarn ? "warning" : "error";
          const iconColor = isOk ? "text-primary-container" : isWarn ? "text-tertiary" : "text-error";
          const badgeCls = isOk
            ? "bg-primary-container/15 text-primary-container border-primary-container/30"
            : isWarn
            ? "bg-tertiary/15 text-tertiary border-tertiary/30"
            : "bg-error/15 text-error border-error/30";
          return `
            <div class="flex items-center justify-between p-2 rounded-lg bg-surface-container/60 border border-outline-variant/15 hover:border-outline-variant/40 transition-colors">
              <div class="flex items-center gap-2.5 min-w-0 pr-2">
                <span class="material-symbols-outlined ${iconColor} text-[16px] shrink-0">${iconName}</span>
                <div class="min-w-0">
                  <div class="text-xs font-bold text-on-surface">${c.name}</div>
                  <div class="text-[10px] font-mono text-on-surface-variant truncate">${c.detail || ""}</div>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded ${badgeCls} font-mono text-[10px] font-bold border shrink-0">${c.status}</span>
            </div>
          `;
        }).join("");

        const autoInstallBtn = document.getElementById("btn-diag-auto-install");
        if (autoInstallBtn) autoInstallBtn.addEventListener("click", triggerInstallMissingLibs);
      }

      await fetchSystemLogs();
    } catch (e) {
      if (box && !silentOnStartup) {
        box.style.display = "block";
        box.innerHTML = `<div class="text-error text-xs">❌ Không kết nối được tới Server để kiểm tra lỗi: ${e.message}</div>`;
      }
    } finally {
      if (btn && !silentOnStartup) {
        btn.disabled = false;
        btn.innerHTML = origBtnHtml || `<span class="material-symbols-outlined text-[16px]">fact_check</span>Kiểm Tra Hệ Thống &amp; Thư Viện`;
      }
    }
  }

  function setupSystemLogsAndDiagnostics() {
    const diagBtn = document.getElementById("btn-run-diagnostics");
    if (diagBtn) {
      diagBtn.addEventListener("click", () => runSystemDiagnosticsUI(false));
    }

    const installLibsBtn = document.getElementById("btn-install-missing-libs");
    if (installLibsBtn) {
      installLibsBtn.addEventListener("click", triggerInstallMissingLibs);
    }

    const openLogsBtn = document.getElementById("btn-open-logs-folder");
    if (openLogsBtn) {
      openLogsBtn.addEventListener("click", async () => {
        const dirPath = (latestLogPathsCache && latestLogPathsCache.logs_dir) ? latestLogPathsCache.logs_dir : "logs";
        await openSystemFolder(dirPath);
      });
    }

    const copyLogsBtn = document.getElementById("btn-copy-logs");
    if (copyLogsBtn) {
      copyLogsBtn.addEventListener("click", () => {
        const text = latestLogEntriesCache
          .map((e) => `[${e.timestamp}] [${e.level}/${e.category}]${e.project_id ? " [" + e.project_id + "]" : ""} ${e.message}`)
          .join("\n");
        navigator.clipboard.writeText(text || "Không có log");
        const orig = copyLogsBtn.innerHTML;
        copyLogsBtn.innerHTML = `<span class="material-symbols-outlined text-[14px]">check</span>Đã Copy!`;
        setTimeout(() => { copyLogsBtn.innerHTML = orig; }, 1800);
      });
    }

    const clearLogsBtn = document.getElementById("btn-clear-logs");
    if (clearLogsBtn) {
      clearLogsBtn.addEventListener("click", async () => {
        await fetch("/api/logs/clear", { method: "POST" });
        await fetchSystemLogs();
      });
    }

    // Auto-scroll toggle button in Terminal Header
    const autoScrollBtn = document.getElementById("btn-quick-autoscroll");
    const autoScrollLbl = document.getElementById("lbl-autoscroll-state");
    if (autoScrollBtn) {
      autoScrollBtn.addEventListener("click", () => {
        isTerminalAutoScroll = !isTerminalAutoScroll;
        if (autoScrollLbl) autoScrollLbl.innerText = isTerminalAutoScroll ? "ON" : "OFF";
        autoScrollBtn.style.opacity = isTerminalAutoScroll ? "1" : "0.55";
      });
    }

    // Terminal Quick Command Injection Bar
    const termInput = document.getElementById("terminal-quick-input");
    const termExecBtn = document.getElementById("btn-terminal-exec");

    async function runTerminalQuickCommand() {
      if (!termInput) return;
      const cmd = termInput.value.trim() || "status";
      termInput.value = "";
      if (termExecBtn) termExecBtn.disabled = true;
      try {
        const res = await fetch("/api/diagnostics/exec-cmd", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: cmd })
        });
        const data = await res.json().catch(() => ({}));
        if (data && data.output) {
          await fetchSystemLogs();
        }
      } catch (e) {
        appendInstantLogToUI(`Lỗi thực thi lệnh '${cmd}': ${e.message}`, "SYSTEM", "ERROR");
      } finally {
        if (termExecBtn) termExecBtn.disabled = false;
      }
    }

    if (termExecBtn) {
      termExecBtn.addEventListener("click", runTerminalQuickCommand);
    }
    if (termInput) {
      termInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          runTerminalQuickCommand();
        }
      });
    }

    document.querySelectorAll(".log-filter-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".log-filter-btn").forEach((b) => {
          b.className = "log-filter-btn px-3 py-1 rounded bg-surface-container hover:bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm transition-all";
        });
        btn.className = "log-filter-btn active px-3 py-1 rounded bg-primary-container text-on-primary-container font-label-sm text-label-sm font-bold shadow-[0_0_8px_rgba(0,255,135,0.3)] transition-all";
        const f = btn.dataset.filter !== undefined ? btn.dataset.filter : "";
        if (f === "ERROR") {
          currentLogLevelFilter = "ERROR";
          currentLogCatFilter = "ALL";
        } else if (f === "ADAS") {
          currentLogLevelFilter = "ALL";
          currentLogCatFilter = "SCRIPT";
        } else if (f === "RENDER" || f === "VOICE") {
          currentLogLevelFilter = "ALL";
          currentLogCatFilter = "VIDEO";
        } else {
          currentLogLevelFilter = btn.dataset.level || "ALL";
          currentLogCatFilter = btn.dataset.cat || "ALL";
        }
        fetchSystemLogs();
      });
    });

    fetchSystemLogs();
    setInterval(fetchSystemLogs, 2500);
    setTimeout(() => runSystemDiagnosticsUI(true), 1500);
  }

  let voicePresetsCache = [];

  async function setupVoiceSelectorAndTuning() {
    const mainSel = document.getElementById("voice-preset-select");
    const adasSel = document.getElementById("adas-voice-select");
    const badgeEl = document.getElementById("voice-engine-badge");
    const descEl = document.getElementById("voice-preset-desc") || document.getElementById("voice-desc-hint");
    const slidersBox = document.getElementById("voice-tuning-sliders");

    const speedRange = document.getElementById("voice-speed-range");
    const pitchRange = document.getElementById("voice-pitch-range");
    const intoRange = document.getElementById("voice-intonation-range");
    const pauseRange = document.getElementById("voice-pause-range");

    const speedVal = document.getElementById("voice-speed-val") || document.getElementById("lbl-voice-speed");
    const pitchVal = document.getElementById("voice-pitch-val") || document.getElementById("lbl-voice-pitch");
    const intoVal = document.getElementById("voice-intonation-val") || document.getElementById("lbl-voice-intonation");
    const pauseVal = document.getElementById("voice-pause-val") || document.getElementById("lbl-voice-pause");

    const previewBtn = document.getElementById("btn-preview-voice");
    const resetDramaBtn = document.getElementById("btn-reset-drama-voice");
    const audioPlayer = document.getElementById("voice-preview-player");
    const srvBtn1 = document.getElementById("btn-gpu-server-1");
    const srvBtn2 = document.getElementById("btn-gpu-server-2");
    const balancerBadge = document.getElementById("gpu-balancer-badge");

    // Mini Preview Player Bar elements
    const btnMiniPlay = document.getElementById("btn-mini-voice-play");
    const miniPlayIcon = document.getElementById("mini-voice-play-icon");
    const miniProgressFill = document.getElementById("voice-mini-progress-fill");
    const miniTimeCur = document.getElementById("voice-mini-time-cur");
    const miniTimeDur = document.getElementById("voice-mini-time-dur");

    function formatShortAudioTime(sec) {
      const s = Math.max(0, Math.floor(sec || 0));
      const mm = String(Math.floor(s / 60)).padStart(2, "0");
      const ss = String(s % 60).padStart(2, "0");
      return `${mm}:${ss}`;
    }

    if (audioPlayer) {
      audioPlayer.addEventListener("loadedmetadata", () => {
        if (miniTimeDur && isFinite(audioPlayer.duration)) {
          miniTimeDur.innerText = formatShortAudioTime(audioPlayer.duration);
        }
      });
      audioPlayer.addEventListener("timeupdate", () => {
        const dur = audioPlayer.duration || 1;
        const cur = audioPlayer.currentTime || 0;
        const pct = Math.max(0, Math.min(100, (cur / dur) * 100));
        if (miniProgressFill) miniProgressFill.style.width = `${pct}%`;
        if (miniTimeCur) miniTimeCur.innerText = formatShortAudioTime(cur);
      });
      audioPlayer.addEventListener("play", () => {
        if (miniPlayIcon) miniPlayIcon.innerText = "pause";
      });
      audioPlayer.addEventListener("pause", () => {
        if (miniPlayIcon) miniPlayIcon.innerText = "play_arrow";
      });
      audioPlayer.addEventListener("ended", () => {
        if (miniPlayIcon) miniPlayIcon.innerText = "play_arrow";
        if (miniProgressFill) miniProgressFill.style.width = "100%";
      });
    }

    if (btnMiniPlay) {
      btnMiniPlay.addEventListener("click", () => {
        if (audioPlayer && audioPlayer.src) {
          if (audioPlayer.paused) {
            audioPlayer.play().catch(() => {});
          } else {
            audioPlayer.pause();
          }
        } else if (previewBtn) {
          previewBtn.click();
        }
      });
    }

    function applyServerButtonsUI(serverMode, statusData) {
      activeGpuServerMode = serverMode || "voicevox_gpu";
      const isOmni = activeGpuServerMode === "omnivoice_gpu";
      const hw = (statusData && statusData.hardware_load) ? statusData.hardware_load : null;

      if (srvBtn1) {
        if (!isOmni) {
          srvBtn1.className = "gpu-server-btn active group relative p-3.5 rounded-xl bg-primary-container/10 border-2 border-primary-container text-left transition-all shadow-[0_0_20px_rgba(0,230,118,0.12)]";
        } else {
          srvBtn1.className = "gpu-server-btn group relative p-3.5 rounded-xl bg-surface-container-low hover:bg-surface-container border border-outline-variant/30 hover:border-primary-container/50 text-left transition-all";
        }
      }
      if (srvBtn2) {
        if (isOmni) {
          srvBtn2.className = "gpu-server-btn active group relative p-3.5 rounded-xl bg-secondary-container/10 border-2 border-secondary-container text-left transition-all shadow-[0_0_20px_rgba(0,210,255,0.12)]";
        } else {
          srvBtn2.className = "gpu-server-btn group relative p-3.5 rounded-xl bg-surface-container-low hover:bg-surface-container border border-outline-variant/30 hover:border-secondary-container/50 text-left transition-all";
        }
      }
      if (balancerBadge && hw) {
        balancerBadge.innerText = `TỰ CÂN ĐỐI 90%: GPU ${Math.round(hw.gpu_percent || 0)}% • CPU ${Math.round(hw.cpu_percent || 0)}%`;
      }
    }

    function applyConfigToUI(cfg, presets, statusData = null) {
      if (!cfg) return;
      const presetId = cfg.selected_preset_id || "Drama";
      if (mainSel && mainSel.value !== presetId) mainSel.value = presetId;
      if (adasSel && adasSel.value !== presetId) adasSel.value = presetId;

      const presetObj = (presets || voicePresetsCache).find((p) => p.id === presetId) || null;
      if (descEl && presetObj) {
        descEl.innerText = presetObj.description || "";
      }

      const isOmni = cfg.active_gpu_server === "omnivoice_gpu" || cfg.engine_mode === "omnivoice" || (presetObj && presetObj.engine === "omnivoice");
      applyServerButtonsUI(isOmni ? "omnivoice_gpu" : "voicevox_gpu", statusData);

      if (badgeEl) {
        if (isOmni) {
          badgeEl.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-secondary-container animate-pulse"></span>OMNIVOICE CUDA READY`;
        } else {
          badgeEl.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-primary-container animate-pulse"></span>VOICEVOX GPU (${presetId})`;
        }
      }
      if (slidersBox) {
        slidersBox.style.opacity = isOmni ? "0.45" : "1";
        slidersBox.style.pointerEvents = isOmni ? "none" : "auto";
      }

      const sp = Number(cfg.speedScale ?? 0.97).toFixed(2);
      const pt = Number(cfg.pitchScale ?? -0.02).toFixed(2);
      const it = Number(cfg.intonationScale ?? 0.95).toFixed(2);
      const pa = Number(cfg.pauseLengthScale ?? 1.12).toFixed(2);

      if (speedRange) speedRange.value = sp;
      if (pitchRange) pitchRange.value = pt;
      if (intoRange) intoRange.value = it;
      if (pauseRange) pauseRange.value = pa;

      if (speedVal) speedVal.innerText = `${sp}x`;
      if (pitchVal) pitchVal.innerText = (Number(pt) > 0 ? `+${pt}` : pt);
      if (intoVal) intoVal.innerText = it;
      if (pauseVal) pauseVal.innerText = `${pa}x`;
    }

    async function saveVoiceSettings(payload) {
      try {
        const res = await fetch("/api/voice-engine/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data && data.config) {
          applyConfigToUI(data.config, voicePresetsCache, data.status || null);
        }
      } catch (e) {}
    }

    async function switchGpuVoiceServer(targetServerMode) {
      const targetBtn = targetServerMode === "omnivoice_gpu" ? srvBtn2 : srvBtn1;
      if (targetBtn) {
        targetBtn.disabled = true;
      }
      try {
        const res = await fetch("/api/voice-engine/switch-server", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active_gpu_server: targetServerMode, activate_server_now: true })
        });
        const data = await res.json();
        if (data && data.config) {
          applyConfigToUI(data.config, voicePresetsCache, data.status || null);
          appendInstantLogToUI(
            targetServerMode === "voicevox_gpu"
              ? "🟢 Đã bật Server 1: VOICEVOX DirectML GPU Cluster (2 cổng GPU 50021/50022 sẵn sàng)!"
              : "🔵 Đã bật Server 2: OmniVoice CUDA GPU (Đã nạp model lên VRAM)!",
            "VOICE",
            "INFO"
          );
        }
      } catch (e) {
        alert("Lỗi chuyển đổi Server GPU: " + e.message);
      } finally {
        if (targetBtn) targetBtn.disabled = false;
      }
    }

    if (srvBtn1) {
      srvBtn1.addEventListener("click", () => switchGpuVoiceServer("voicevox_gpu"));
    }
    if (srvBtn2) {
      srvBtn2.addEventListener("click", () => switchGpuVoiceServer("omnivoice_gpu"));
    }

    try {
      const res = await fetch("/api/voice-engine/status");
      const data = await res.json();
      voicePresetsCache = data.presets || [];
      if (voicePresetsCache.length > 0) {
        if (mainSel) {
          mainSel.innerHTML = voicePresetsCache
            .map((p) => `<option value="${p.id}">${p.name}</option>`)
            .join("");
        }
        if (adasSel) {
          adasSel.innerHTML = voicePresetsCache
            .map((p) => `<option value="${p.id}">🎙️ Voice: ${p.name}</option>`)
            .join("");
        }
      }
      applyConfigToUI(data.config, voicePresetsCache, data);
    } catch (e) {}

    async function onPresetSelectChange(selectedId) {
      const preset = voicePresetsCache.find((p) => p.id === selectedId);
      if (!preset) return;
      const srvMode = preset.engine === "omnivoice" ? "omnivoice_gpu" : "voicevox_gpu";
      await saveVoiceSettings({
        active_gpu_server: srvMode,
        selected_preset_id: preset.id,
        engine_mode: preset.engine,
        speaker_id: preset.speaker_id,
        speedScale: preset.speedScale,
        pitchScale: preset.pitchScale,
        intonationScale: preset.intonationScale,
        pauseLengthScale: preset.pauseLengthScale,
        volumeScale: preset.volumeScale,
        ref_wav: preset.ref_wav,
        activate_server_now: true
      });
    }

    if (mainSel) {
      mainSel.addEventListener("change", () => onPresetSelectChange(mainSel.value));
    }
    if (adasSel) {
      adasSel.addEventListener("change", () => onPresetSelectChange(adasSel.value));
    }

    function bindSlider(rangeEl, valEl, formatFn, fieldKey) {
      if (!rangeEl) return;
      rangeEl.addEventListener("input", () => {
        if (valEl) valEl.innerText = formatFn(rangeEl.value);
      });
      rangeEl.addEventListener("change", async () => {
        const payload = {};
        payload[fieldKey] = parseFloat(rangeEl.value);
        await saveVoiceSettings(payload);
      });
    }

    bindSlider(speedRange, speedVal, (v) => `${Number(v).toFixed(2)}x`, "speedScale");
    bindSlider(pitchRange, pitchVal, (v) => (Number(v) > 0 ? `+${Number(v).toFixed(2)}` : Number(v).toFixed(2)), "pitchScale");
    bindSlider(intoRange, intoVal, (v) => Number(v).toFixed(2), "intonationScale");
    bindSlider(pauseRange, pauseVal, (v) => `${Number(v).toFixed(2)}x`, "pauseLengthScale");

    if (resetDramaBtn) {
      resetDramaBtn.addEventListener("click", async () => {
        await onPresetSelectChange("Drama");
      });
    }

    if (previewBtn) {
      previewBtn.addEventListener("click", async () => {
        const origHtml = previewBtn.innerHTML;
        previewBtn.disabled = true;
        previewBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>Đang tạo âm thanh...`;
        try {
          const res = await fetch("/api/voice-engine/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              selected_preset_id: mainSel ? mainSel.value : "Drama",
              speedScale: speedRange ? parseFloat(speedRange.value) : 0.94,
              pitchScale: pitchRange ? parseFloat(pitchRange.value) : -0.02,
              intonationScale: intoRange ? parseFloat(intoRange.value) : 0.95,
              pauseLengthScale: pauseRange ? parseFloat(pauseRange.value) : 1.12,
            }),
          });
          const data = await res.json();
          if (!res.ok) {
            alert(data.detail || "Không thể tạo âm thanh nghe thử!");
            return;
          }
          if (audioPlayer && data.audio_url) {
            audioPlayer.src = data.audio_url;
            audioPlayer.play().catch(() => {});
          }
        } catch (e) {
          alert("Lỗi nghe thử giọng: " + e.message);
        } finally {
          previewBtn.disabled = false;
          previewBtn.innerHTML = origHtml;
        }
      });
    }
  }

  function setupWindowCloseAutoShutdown() {
    // Báo ngay khi cửa sổ mở (hoặc F5 tải lại) để hủy lệnh tắt nếu người dùng chỉ bấm F5
    fetch("/api/app/heartbeat-alive", { method: "POST" }).catch(() => {});

    let closeSent = false;
    const sendCloseSignal = () => {
      if (closeSent) return;
      closeSent = true;
      try {
        if (navigator.sendBeacon) {
          navigator.sendBeacon("/api/app/window-closed", new Blob(["{}"], { type: "application/json" }));
        } else {
          fetch("/api/app/window-closed", { method: "POST", keepalive: true }).catch(() => {});
        }
      } catch (e) {}
    };

    window.addEventListener("pagehide", sendCloseSignal);
    window.addEventListener("beforeunload", sendCloseSignal);
  }

  function setupGithubOtaAutoUpdater() {
    const verBadge = document.getElementById("app-version-badge");
    const btnCheck = document.getElementById("btn-check-update-header");
    const iconCheck = document.getElementById("icon-check-update-header");
    const textCheck = document.getElementById("text-check-update-header");
    const btnApplyHeader = document.getElementById("btn-apply-update-header");
    const textApplyHeader = document.getElementById("btn-apply-update-header-text");

    const btnCheckNav = document.getElementById("btn-check-update-nav");
    const iconCheckNav = document.getElementById("icon-check-update-nav");
    const textCheckNav = document.getElementById("text-check-update-nav");
    const btnApplyNav = document.getElementById("btn-apply-update-nav");
    const textApplyNav = document.getElementById("btn-apply-update-nav-text");

    const bannerEl = document.getElementById("ota-update-banner");
    const bannerVerTag = document.getElementById("ota-banner-ver-tag");
    const bannerMsg = document.getElementById("ota-banner-msg");
    const btnBannerApply = document.getElementById("btn-ota-banner-apply");
    const textBannerApply = document.getElementById("btn-ota-banner-apply-text");
    const btnBannerDismiss = document.getElementById("btn-ota-banner-dismiss");

    let dismissedVersion = sessionStorage.getItem("dismissed_ota_version") || "";
    let latestUpdateInfo = null;
    let isApplyingUpdate = false;

    const renderUpdateUI = (info, isManualCheck = false) => {
      if (!info) return;
      latestUpdateInfo = info;
      const curVer = info.current_version || "V1.0.0";
      const newVer = info.latest_version || curVer;
      const hasUpdate = !!info.update_available;

      if (verBadge) verBadge.innerText = curVer;
      if (textCheck) {
        textCheck.innerText = hasUpdate ? `Có bản mới: ${newVer}` : `Cập nhật: ${curVer}`;
      }
      if (textCheckNav) {
        textCheckNav.innerText = hasUpdate ? `🔥 CÓ BẢN MỚI: ${newVer}` : `🔄 CẬP NHẬT (${curVer})`;
      }

      if (hasUpdate) {
        if (btnApplyHeader) {
          btnApplyHeader.classList.remove("hidden");
          btnApplyHeader.classList.add("flex");
        }
        if (textApplyHeader) {
          textApplyHeader.innerText = `🚀 Cập nhật ${newVer}`;
        }
        if (btnApplyNav) {
          btnApplyNav.classList.remove("hidden");
          btnApplyNav.classList.add("flex");
        }
        if (textApplyNav) {
          textApplyNav.innerText = `🚀 CẬP NHẬT ${newVer}`;
        }
        if (bannerVerTag) {
          bannerVerTag.innerText = `MỚI: ${newVer}`;
        }
        if (bannerMsg) {
          const note = info.changelog ? ` — ${info.changelog}` : "";
          bannerMsg.innerText = `🎉 Đã có bản cập nhật ${newVer} trên GitHub (Bản hiện tại: ${curVer})${note}`;
          bannerMsg.title = info.changelog || "";
        }
        if (bannerEl && (isManualCheck || dismissedVersion !== `${newVer}_${info.latest_build || ""}`)) {
          bannerEl.classList.remove("hidden");
          bannerEl.classList.add("flex");
        }
        if (isManualCheck) {
          executeApplyUpdate();
        }
      } else {
        if (btnApplyHeader) {
          btnApplyHeader.classList.add("hidden");
          btnApplyHeader.classList.remove("flex");
        }
        if (btnApplyNav) {
          btnApplyNav.classList.add("hidden");
          btnApplyNav.classList.remove("flex");
        }
        if (bannerEl) {
          bannerEl.classList.add("hidden");
          bannerEl.classList.remove("flex");
        }
        if (isManualCheck) {
          if (info.success === false && info.error) {
            alert(`⚠️ Không thể kiểm tra cập nhật lúc này:\n${info.error}`);
          } else if (confirm(`✅ Máy của bạn đang ở phiên bản ${curVer} (Build #${info.current_build || 104}).\n\nBạn có muốn tải và đồng bộ lại mã nguồn mới nhất của bản ${newVer} từ GitHub ngay bây giờ không?`)) {
            executeApplyUpdate();
          }
        }
      }
    };

    const checkUpdateNow = async (forceRefresh = false, isManual = false) => {
      if (isApplyingUpdate) return;
      if (isManual) {
        if (iconCheck) iconCheck.classList.add("animate-spin");
        if (iconCheckNav) iconCheckNav.classList.add("animate-spin");
      }
      try {
        const res = await fetch(`/api/update/check?force=${forceRefresh ? "true" : "false"}`);
        if (res.ok) {
          const data = await res.json();
          renderUpdateUI(data, isManual);
        } else {
          // Dự phòng trực tiếp tới GitHub nếu tiến trình server cũ chưa khởi động lại
          const ghRes = await fetch(`https://raw.githubusercontent.com/phamngocthu661-lang/drama-nhat-studio/main/version.json?t=${Date.now()}`);
          if (ghRes.ok) {
            const ghData = await ghRes.json();
            const curVer = (verBadge && verBadge.innerText.trim()) || "V1.0.0";
            const latestVer = ghData.version || "V1.0.0";
            const latestBuild = Number(ghData.build_number || 100);
            renderUpdateUI({
              success: true,
              update_available: latestVer !== curVer,
              current_version: curVer,
              latest_version: latestVer,
              changelog: ghData.changelog || ""
            }, isManual);
          }
        }
      } catch (e) {
        if (isManual) {
          alert("Không thể kết nối kiểm tra cập nhật: " + e.message);
        }
      } finally {
        if (isManual) {
          if (iconCheck) iconCheck.classList.remove("animate-spin");
          if (iconCheckNav) iconCheckNav.classList.remove("animate-spin");
        }
      }
    };

    const executeApplyUpdate = async () => {
      if (isApplyingUpdate) return;
      const targetVer = (latestUpdateInfo && latestUpdateInfo.latest_version) || "mới nhất";
      const curVer = (latestUpdateInfo && latestUpdateInfo.current_version) || "V1.0.0";
      const note = (latestUpdateInfo && latestUpdateInfo.changelog)
        ? `\n\n📋 Nội dung nâng cấp:\n${latestUpdateInfo.changelog}`
        : "";

      if (!confirm(`🚀 Bạn có muốn tự động tải và cập nhật ứng dụng từ bản [${curVer}] lên bản [${targetVer}] ngay bây giờ không?${note}\n\n(Toàn bộ kịch bản, dự án, kho Stock và cấu hình của bạn được giữ nguyên 100%)`)) {
        return;
      }

      isApplyingUpdate = true;
      if (btnBannerApply) btnBannerApply.disabled = true;
      if (btnApplyHeader) btnApplyHeader.disabled = true;
      if (btnApplyNav) btnApplyNav.disabled = true;
      if (textBannerApply) textBannerApply.innerText = "⏳ Đang tải & cập nhật...";
      if (textApplyHeader) textApplyHeader.innerText = "⏳ Đang cập nhật...";
      if (textApplyNav) textApplyNav.innerText = "⏳ ĐANG CẬP NHẬT...";

      try {
        const res = await fetch("/api/update/apply", { method: "POST" });
        let data = null;
        if (res.status === 404) {
          // Trường hợp tiến trình Server cũ trên máy Admin đã có sẵn file mới trên ổ cứng
          data = { success: true, old_version: curVer, new_version: targetVer };
        } else {
          data = await res.json();
        }
        if ((res.status !== 404 && !res.ok) || !data || !data.success) {
          alert(`❌ Cập nhật thất bại: ${(data && data.error) || "Lỗi không xác định"}`);
          return;
        }
        if (textBannerApply) textBannerApply.innerText = `✅ Đã lên ${data.new_version}!`;
        if (textApplyHeader) textApplyHeader.innerText = `✅ Đã lên ${data.new_version}!`;
        if (textApplyNav) textApplyNav.innerText = `✅ ĐÃ LÊN ${data.new_version}!`;
        alert(`🎉 Đã cập nhật thành công từ ${data.old_version} lên ${data.new_version}!\n\nGiao diện sẽ tự động làm mới ngay bây giờ.`);
        window.location.href = "/?v=" + Date.now();
      } catch (e) {
        alert("❌ Lỗi khi tải bản cập nhật: " + e.message);
      } finally {
        isApplyingUpdate = false;
        if (btnBannerApply) btnBannerApply.disabled = false;
        if (btnApplyHeader) btnApplyHeader.disabled = false;
        if (btnApplyNav) btnApplyNav.disabled = false;
      }
    };

    if (btnCheck) {
      btnCheck.addEventListener("click", () => {
        checkUpdateNow(true, true);
      });
    }
    if (btnCheckNav) {
      btnCheckNav.addEventListener("click", () => {
        checkUpdateNow(true, true);
      });
    }
    if (btnApplyHeader) {
      btnApplyHeader.addEventListener("click", executeApplyUpdate);
    }
    if (btnApplyNav) {
      btnApplyNav.addEventListener("click", executeApplyUpdate);
    }
    if (btnBannerApply) {
      btnBannerApply.addEventListener("click", executeApplyUpdate);
    }
    if (btnBannerDismiss) {
      btnBannerDismiss.addEventListener("click", () => {
        if (latestUpdateInfo && latestUpdateInfo.latest_version) {
          dismissedVersion = latestUpdateInfo.latest_version;
          sessionStorage.setItem("dismissed_ota_version", dismissedVersion);
        }
        if (bannerEl) {
          bannerEl.classList.add("hidden");
          bannerEl.classList.remove("flex");
        }
      });
    }

    // Kiểm tra ngay khi mở ứng dụng và tự động kiểm tra định kỳ mỗi 2 phút
    checkUpdateNow(false, false);
    setInterval(() => {
      checkUpdateNow(false, false);
    }, 120000);
  }

  function setupPerformanceModeSelector() {
    let currentPerfMode = localStorage.getItem("studio_perf_mode") || "full_100";

    const applyPerfModeUI = (mode) => {
      const is70 = mode === "work_70";
      currentPerfMode = is70 ? "work_70" : "full_100";
      localStorage.setItem("studio_perf_mode", currentPerfMode);

      document.querySelectorAll(".perf-mode-btn").forEach((btn) => {
        const active = btn.dataset.perfMode === currentPerfMode;
        if (active) {
          btn.className = "perf-mode-btn active whitespace-nowrap flex items-center gap-1 px-2.5 py-1 rounded bg-primary-container text-on-primary-fixed font-label-md text-[11px] font-bold shadow-[0_0_10px_rgba(0,255,135,0.35)] transition-all";
        } else {
          btn.className = "perf-mode-btn whitespace-nowrap flex items-center gap-1 px-2.5 py-1 rounded bg-transparent hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface font-label-md text-[11px] font-semibold transition-all";
        }
      });

      document.querySelectorAll(".perf-mode-card").forEach((card) => {
        const active = card.dataset.perfMode === currentPerfMode;
        const dot = card.querySelector(".perf-dot");
        const titleDiv = card.querySelector("div:first-child");
        if (active) {
          card.className = "perf-mode-card active p-2 rounded-lg bg-primary-container/15 border-2 border-primary-container text-left transition-all";
          if (titleDiv) {
            titleDiv.classList.add("text-primary");
            titleDiv.classList.remove("text-on-surface");
          }
          if (dot) {
            dot.className = "perf-dot w-2 h-2 rounded-full bg-primary-container shadow-[0_0_6px_rgba(0,255,135,0.8)]";
          }
        } else {
          card.className = "perf-mode-card p-2 rounded-lg bg-surface-container-lowest hover:bg-surface-container border border-surface-container-high text-left transition-all";
          if (titleDiv) {
            titleDiv.classList.remove("text-primary");
            titleDiv.classList.add("text-on-surface");
          }
          if (dot) {
            dot.className = "perf-dot w-2 h-2 rounded-full bg-surface-container-highest";
          }
        }
      });

      document.querySelectorAll(".perf-mode-status-label").forEach((lbl) => {
        lbl.innerText = is70
          ? "Đang chọn: 💼 Chạy 70% (Tối đa 3 luồng)"
          : "Đang chọn: 🔥 Chạy Full 100% (Như hiện tại)";
      });

      const balancerBadge = document.getElementById("gpu-balancer-badge");
      if (balancerBadge) {
        balancerBadge.innerText = is70
          ? "💼 Chế độ 70% (Vừa làm việc khác): Giới hạn ~70% GPU & CPU (Tối đa 3 luồng)"
          : "⚡ Chế độ Full 100%: Mục tiêu ~90% GPU & CPU (Tối đa 5 video)";
      }
    };

    const setPerfMode = async (targetMode, notifyUser = true) => {
      const norm = targetMode === "work_70" ? "work_70" : "full_100";
      applyPerfModeUI(norm);
      try {
        await fetch("/api/performance-mode", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: norm }),
        });
      } catch (e) {}
      if (notifyUser) {
        appendInstantLogToUI(
          norm === "work_70"
            ? "💼 Đã bật Chức năng 2: Chạy 70% Công Suất (Khóa cứng tối đa 3 luồng • Giới hạn 70% CPU/GPU • 1 tab AI/Acc) — Vừa chạy vừa làm việc khác mượt mà!"
            : "🔥 Đã bật Chức năng 1: Chạy Full 100% Công Suất như hiện tại (Ngưỡng 90% CPU/GPU • Tối đa 5 video • 3 tab AI/Acc)!",
          "SYSTEM",
          "INFO"
        );
      }
    };

    document.querySelectorAll(".perf-mode-btn, .perf-mode-card").forEach((el) => {
      el.addEventListener("click", () => {
        const m = el.dataset.perfMode || "full_100";
        setPerfMode(m, true);
      });
    });

    // Đồng bộ trạng thái ban đầu giữa Giao diện và Server
    const explicitLocalMode = localStorage.getItem("studio_perf_mode");
    applyPerfModeUI(currentPerfMode);
    if (explicitLocalMode === "work_70" || explicitLocalMode === "full_100") {
      setPerfMode(explicitLocalMode, false);
    } else {
      fetch("/api/performance-mode")
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (d && d.mode) {
            applyPerfModeUI(d.mode);
          }
        })
        .catch(() => {});
    }
  }

  setupSystemLogsAndDiagnostics();
  setupVoiceSelectorAndTuning();
  setupWindowCloseAutoShutdown();
  setupGithubOtaAutoUpdater();
  setupPerformanceModeSelector();
});
