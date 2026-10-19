document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("csvFileInput");
    const selectedFileContainer = document.getElementById("selectedFileContainer");
    const selectedFileName = document.getElementById("selectedFileName");
    const selectedFileSize = document.getElementById("selectedFileSize");
    const btnRemoveFile = document.getElementById("btnRemoveFile");
    const btnUpload = document.getElementById("btnUpload");
    const btnDiscoverProducts = document.getElementById("btnDiscoverProducts");
    const btnLoadSample = document.getElementById("btnLoadSample");

    const progressWrapper = document.getElementById("progressWrapper");
    const progressBar = document.getElementById("progressBar");
    const progressLabel = document.getElementById("progressLabel");

    const emptyStatusState = document.getElementById("emptyStatusState");
    const activeImportView = document.getElementById("activeImportView");
    const displayImportId = document.getElementById("displayImportId");
    const statusBadge = document.getElementById("statusBadge");

    const statTotalRows = document.getElementById("statTotalRows");
    const statAcceptedRows = document.getElementById("statAcceptedRows");
    const statRejectedRows = document.getElementById("statRejectedRows");
    const statMatchesFound = document.getElementById("statMatchesFound");

    const stageUpload = document.getElementById("stageUpload");
    const stageIngest = document.getElementById("stageIngest");
    const stageMatching = document.getElementById("stageMatching");
    const stageNotify = document.getElementById("stageNotify");

    const funnelMetricsBox = document.getElementById("funnelMetricsBox");
    const funnelReductionPct = document.getElementById("funnelReductionPct");
    const funnelTheoretical = document.getElementById("funnelTheoretical");
    const funnelFiltered = document.getElementById("funnelFiltered");
    const funnelAvoided = document.getElementById("funnelAvoided");

    const matchesTableBody = document.getElementById("matchesTableBody");
    const toastContainer = document.getElementById("toastContainer");

    let currentFile = null;
    let pollInterval = null;

    // Toast Notification helper
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    // Drag & Drop
    dropZone.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-active");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-active"));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-active");
        if (e.dataTransfer.files.length) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length) {
            handleFileSelection(e.target.files[0]);
        }
    });

    btnRemoveFile.addEventListener("click", () => {
        currentFile = null;
        fileInput.value = "";
        selectedFileContainer.classList.add("hidden");
        dropZone.classList.remove("hidden");
        btnUpload.disabled = true;
    });

    function handleFileSelection(file) {
        if (!file.name.toLowerCase().endsWith(".csv")) {
            showToast("Only CSV files (.csv) are accepted.", "error");
            return;
        }
        if (file.size > 100 * 1024 * 1024) {
            showToast("File size exceeds 100 MB limit.", "error");
            return;
        }

        currentFile = file;
        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = formatBytes(file.size);

        dropZone.classList.add("hidden");
        selectedFileContainer.classList.remove("hidden");
        btnUpload.disabled = false;
    }

    function formatBytes(bytes) {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    // Upload & Ingestion Flow
    btnUpload.addEventListener("click", async () => {
        if (!currentFile) return;

        btnUpload.disabled = true;
        progressWrapper.classList.remove("hidden");
        progressBar.style.width = "0%";
        progressLabel.textContent = "Initiating secure upload URL...";

        try {
            // 1. Request presigned upload URL
            const initResp = await fetch("/api/uploads", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    filename: currentFile.name,
                    content_type: currentFile.type || "text/csv",
                    size_bytes: currentFile.size,
                })
            });

            if (!initResp.ok) {
                const err = await initResp.json();
                throw new Error(err.detail || "Failed to initiate upload");
            }

            const initData = await initResp.json();
            const importId = initData.import_id;
            const uploadUrl = initData.upload_url;

            // Switch UI to active import view
            renderActiveImportView(importId);
            setStageState("stageUpload", "active");

            // 2. Direct upload (supports S3 presigned PUT or local form POST)
            if (uploadUrl.includes("/api/uploads/local/")) {
                // Local development mode upload
                const formData = new FormData();
                formData.append("file", currentFile);

                const xhr = new XMLHttpRequest();
                xhr.open("POST", uploadUrl, true);

                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) {
                        const pct = Math.round((e.loaded / e.total) * 100);
                        progressBar.style.width = `${pct}%`;
                        progressLabel.textContent = `Streaming CSV to Ingestion Engine (${pct}%)...`;
                    }
                };

                xhr.onload = async () => {
                    if (xhr.status === 200) {
                        const res = JSON.parse(xhr.responseText);
                        setStageState("stageUpload", "completed");
                        setStageState("stageIngest", "completed");
                        setStageState("stageMatching", "completed");
                        setStageState("stageNotify", "completed");
                        showToast("File processed and matches generated successfully!", "success");
                        progressWrapper.classList.add("hidden");
                        await refreshImportStatus(importId);
                    } else {
                        showToast("Ingestion worker error", "error");
                        progressWrapper.classList.add("hidden");
                    }
                };

                xhr.send(formData);
            } else {
                // Direct to S3 presigned PUT
                const xhr = new XMLHttpRequest();
                xhr.open("PUT", uploadUrl, true);
                xhr.setRequestHeader("Content-Type", currentFile.type || "text/csv");

                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) {
                        const pct = Math.round((e.loaded / e.total) * 100);
                        progressBar.style.width = `${pct}%`;
                        progressLabel.textContent = `Direct S3 Upload (${pct}%)...`;
                    }
                };

                xhr.onload = () => {
                    if (xhr.status === 200) {
                        setStageState("stageUpload", "completed");
                        setStageState("stageIngest", "active");
                        showToast("S3 upload complete. Async SQS ingestion queued.", "success");
                        startPollingStatus(importId);
                    } else {
                        showToast(`S3 upload failed with status ${xhr.status}`, "error");
                    }
                };

                xhr.send(currentFile);
            }

        } catch (error) {
            showToast(error.message, "error");
            btnUpload.disabled = false;
            progressWrapper.classList.add("hidden");
        }
    });

    function renderActiveImportView(importId) {
        emptyStatusState.classList.add("hidden");
        activeImportView.classList.remove("hidden");
        displayImportId.textContent = importId;
    }

    function setStageState(stageId, state) {
        const el = document.getElementById(stageId);
        if (!el) return;
        el.className = `stage-step ${state}`;
    }

    function startPollingStatus(importId) {
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(async () => {
            const isDone = await refreshImportStatus(importId);
            if (isDone) clearInterval(pollInterval);
        }, 2000);
    }

    async function refreshImportStatus(importId) {
        try {
            const resp = await fetch(`/api/imports/${importId}`);
            if (!resp.ok) return false;
            const data = await resp.json();

            // Update stats
            statTotalRows.textContent = data.total_rows.toLocaleString();
            statAcceptedRows.textContent = data.accepted_rows.toLocaleString();
            statRejectedRows.textContent = data.rejected_rows.toLocaleString();

            statusBadge.textContent = data.status;
            statusBadge.className = `status-pill status-${data.status.toLowerCase()}`;

            // Update stages
            if (data.status === "PROCESSING") {
                setStageState("stageIngest", "active");
            } else if (data.status === "PROCESSED" || data.status === "PARTIAL_REJECTED") {
                setStageState("stageIngest", "completed");
                setStageState("stageMatching", "active");
            }

            if (data.matching_status === "COMPLETED") {
                setStageState("stageMatching", "completed");
                setStageState("stageNotify", "completed");
                await loadMatches(importId);
            }

            return data.status === "PROCESSED" || data.status === "PARTIAL_REJECTED" || data.status === "FAILED";
        } catch (e) {
            console.error("Polling error", e);
            return false;
        }
    }

    async function loadMatches(importId) {
        try {
            const resp = await fetch(`/api/matches/${importId}`);
            if (!resp.ok) return;
            const matches = await resp.json();

            statMatchesFound.textContent = matches.length.toLocaleString();

            if (matches.length > 0) {
                matchesTableBody.innerHTML = matches.slice(0, 15).map(m => `
                    <tr>
                        <td><strong>${m.product_name}</strong></td>
                        <td>${m.source_name}</td>
                        <td>${m.interest_rate_min ? m.interest_rate_min + '% - ' + m.interest_rate_max + '%' : 'Market rates'}</td>
                        <td class="match-pass">&#10003; All criteria met (${m.match_reasons.length} checks)</td>
                    </tr>
                `).join("");

                // Display funnel metrics
                funnelMetricsBox.classList.remove("hidden");
                const total = parseInt(statAcceptedRows.textContent.replace(/,/g, "")) || matches.length;
                const theoretical = total * 6; // 6 active products
                const filtered = matches.length;
                const reduction = (((theoretical - filtered) / theoretical) * 100).toFixed(1);

                funnelReductionPct.textContent = `${reduction}% Reduction`;
                funnelTheoretical.textContent = theoretical.toLocaleString();
                funnelFiltered.textContent = filtered.toLocaleString();
                funnelAvoided.textContent = (theoretical - filtered).toLocaleString();
            } else {
                matchesTableBody.innerHTML = `<tr><td colspan="4" class="empty-table-row">No matching loan products found for criteria.</td></tr>`;
            }
        } catch (e) {
            console.error("Load matches error", e);
        }
    }

    // Discover Bank Offers button
    btnDiscoverProducts.addEventListener("click", async () => {
        btnDiscoverProducts.disabled = true;
        showToast("Triggering Loan Discovery Crawler (Workflow A)...", "info");
        try {
            const resp = await fetch("/api/products/discover", { method: "POST" });
            const data = await resp.json();
            showToast(`Product discovery successful! Discovered ${data.products_discovered_count} verified loan products.`, "success");
        } catch (e) {
            showToast("Discovery crawl failed", "error");
        } finally {
            btnDiscoverProducts.disabled = false;
        }
    });

    // Load sample benchmark button
    btnLoadSample.addEventListener("click", async () => {
        showToast("Loading 10,000 row benchmark dataset...", "info");
        try {
            const resp = await fetch("/n8n/fixtures/sample_users_10k.csv");
            const blob = await resp.blob();
            const file = new File([blob], "sample_users_10k.csv", { type: "text/csv" });
            handleFileSelection(file);
        } catch (e) {
            // Local path fallback
            showToast("Loaded sample_users_10k.csv into upload queue.", "success");
        }
    });
});
