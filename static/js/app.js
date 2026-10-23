/**
 * ClauseLens Frontend Application
 * Vanilla JS, Zero External Libraries.
 * Implements hash routing, CSRF handling, accessible DOM manipulation,
 * XSS-safe text rendering, split-screen review, and keyboard navigation.
 */

(function () {
    "use strict";

    // Application State
    const state = {
        csrfToken: "",
        policies: [],
        currentAnalysis: null,
        currentSegments: [],
        currentFindings: [],
        filteredFindings: [],
        activeFindingIndex: -1,
        activeFilter: "all",
        selectedFile: null
    };

    // DOM Elements Cache
    const el = {
        mainContent: document.getElementById("mainContent"),
        toastContainer: document.getElementById("toastContainer"),
        navItems: document.querySelectorAll(".nav-item"),
        viewSections: document.querySelectorAll(".view-section"),
        mobileNavToggle: document.getElementById("mobileNavToggle"),
        sidebar: document.getElementById("sidebar"),

        // Dashboard
        statDocs: document.getElementById("stat-docs"),
        statConflicts: document.getElementById("stat-conflicts"),
        statManual: document.getElementById("stat-manual"),
        recentEmptyState: document.getElementById("recentEmptyState"),
        recentTable: document.getElementById("recentTable"),
        recentTableBody: document.getElementById("recentTableBody"),

        // New Analysis
        dropZone: document.getElementById("dropZone"),
        fileInput: document.getElementById("contractFileInput"),
        fileSelectedInfo: document.getElementById("fileSelectedInfo"),
        selectedFileName: document.getElementById("selectedFileName"),
        selectedFileSize: document.getElementById("selectedFileSize"),
        removeFileBtn: document.getElementById("removeFileBtn"),
        policyChecklist: document.getElementById("policyChecklist"),
        toggleAllPoliciesBtn: document.getElementById("toggleAllPoliciesBtn"),
        nemotronOptIn: document.getElementById("nemotronOptIn"),
        startAnalyzeBtn: document.getElementById("startAnalyzeBtn"),
        analyzeBtnSpinner: document.getElementById("analyzeBtnSpinner"),
        analyzeBtnText: document.getElementById("analyzeBtnText"),
        analysisProgressBox: document.getElementById("analysisProgressBox"),

        // Review Workspace
        reviewDocTitle: document.getElementById("reviewDocTitle"),
        reviewDocTypeBadge: document.getElementById("reviewDocTypeBadge"),
        downloadPdfReportBtn: document.getElementById("downloadPdfReportBtn"),
        nemotronStatusBanner: document.getElementById("nemotronStatusBanner"),
        nemotronBannerText: document.getElementById("nemotronBannerText"),
        scannedAlertBanner: document.getElementById("scannedAlertBanner"),
        scannedAlertMessage: document.getElementById("scannedAlertMessage"),
        summaryConflictsCount: document.getElementById("summaryConflictsCount"),
        summaryReviewsCount: document.getElementById("summaryReviewsCount"),
        summaryNoConflictsCount: document.getElementById("summaryNoConflictsCount"),
        summaryPoliciesList: document.getElementById("summaryPoliciesList"),
        segmentsContainer: document.getElementById("segmentsContainer"),
        findingsContainer: document.getElementById("findingsContainer"),
        prevFindingBtn: document.getElementById("prevFindingBtn"),
        nextFindingBtn: document.getElementById("nextFindingBtn"),
        findingIndexIndicator: document.getElementById("findingIndexIndicator"),
        filterChips: document.querySelectorAll(".filter-chip"),
        tabBtnDocument: document.getElementById("tabBtnDocument"),
        tabBtnFindings: document.getElementById("tabBtnFindings"),
        mobileFindingsBadge: document.getElementById("mobileFindingsBadge"),
        reviewLeftPanel: document.getElementById("reviewLeftPanel"),
        reviewRightPanel: document.getElementById("reviewRightPanel"),

        // Counts
        cntAll: document.getElementById("cnt-all"),
        cntConflicts: document.getElementById("cnt-conflicts"),
        cntManual: document.getElementById("cnt-manual"),
        cntPayment: document.getElementById("cnt-payment"),
        cntRenewal: document.getElementById("cnt-renewal"),
        cntLiability: document.getElementById("cnt-liability"),
        cntJurisdiction: document.getElementById("cnt-jurisdiction"),
        cntOther: document.getElementById("cnt-other"),

        // Policies View
        policiesListEmpty: document.getElementById("policiesListEmpty"),
        policiesListGrid: document.getElementById("policiesListGrid"),
        openAddPolicyModalBtn: document.getElementById("openAddPolicyModalBtn"),
        seedExamplePoliciesBtn: document.getElementById("seedExamplePoliciesBtn"),

        // Policy Modal
        policyModal: document.getElementById("policyModal"),
        policyModalTitle: document.getElementById("policyModalTitle"),
        closePolicyModalBtn: document.getElementById("closePolicyModalBtn"),
        cancelPolicyBtn: document.getElementById("cancelPolicyBtn"),
        policyForm: document.getElementById("policyForm"),
        policyEditId: document.getElementById("policyEditId"),
        policyNameInput: document.getElementById("policyNameInput"),
        policyTypeSelect: document.getElementById("policyTypeSelect"),
        policyModeSelect: document.getElementById("policyModeSelect"),
        policyExplanationInput: document.getElementById("policyExplanationInput"),
        policyEnabledInput: document.getElementById("policyEnabledInput"),

        // Parameter groups
        paramGroupPayment: document.getElementById("paramGroupPayment"),
        paramGroupRenewal: document.getElementById("paramGroupRenewal"),
        paramGroupLiability: document.getElementById("paramGroupLiability"),
        paramGroupJurisdiction: document.getElementById("paramGroupJurisdiction"),
        paramMaxPaymentDays: document.getElementById("paramMaxPaymentDays"),
        paramAutoRenewalProhibited: document.getElementById("paramAutoRenewalProhibited"),
        paramMaxNoticeDays: document.getElementById("paramMaxNoticeDays"),
        paramLiabilityRule: document.getElementById("paramLiabilityRule"),
        paramApprovedJurisdictions: document.getElementById("paramApprovedJurisdictions"),

        // History View
        historyEmptyState: document.getElementById("historyEmptyState"),
        historyTable: document.getElementById("historyTable"),
        historyTableBody: document.getElementById("historyTableBody"),
        purgeRetentionBtn: document.getElementById("purgeRetentionBtn"),
        deleteAllHistoryBtn: document.getElementById("deleteAllHistoryBtn")
    };

    // --- XSS-Safe Element Creation Helpers ---

    function createEl(tag, className, textContent) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (textContent !== undefined && textContent !== null) node.textContent = String(textContent);
        return node;
    }

    function showToast(message, type = "info") {
        const toast = createEl("div", `toast toast-${type}`, message);
        el.toastContainer.appendChild(toast);
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 4000);
    }

    // --- CSRF & API Helpers ---

    async function initCsrfToken() {
        try {
            const res = await fetch("/api/csrf");
            if (res.ok) {
                const data = await res.json();
                state.csrfToken = data.token;
            }
        } catch (e) {
            console.warn("Could not fetch initial CSRF token:", e);
        }
    }

    async function apiFetch(url, options = {}) {
        options.headers = options.headers || {};
        if (options.method && options.method.toUpperCase() !== "GET") {
            if (state.csrfToken) {
                options.headers["X-CSRF-Token"] = state.csrfToken;
            }
        }
        const resp = await fetch(url, options);
        if (!resp.ok) {
            let errorMsg = `HTTP Error ${resp.status}`;
            try {
                const errData = await resp.json();
                if (errData && errData.error && errData.error.message) {
                    errorMsg = errData.error.message;
                }
            } catch (_) {}
            throw new Error(errorMsg);
        }
        const contentType = resp.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
            return await resp.json();
        }
        return resp;
    }

    // --- Routing ---

    function navigate(hash) {
        window.location.hash = hash;
    }

    function handleHashChange() {
        const rawHash = window.location.hash || "#dashboard";
        const parts = rawHash.replace(/^#/, "").split("/");
        const primaryRoute = parts[0] || "dashboard";
        const routeParam = parts[1] || null;

        // Hide all views
        el.viewSections.forEach(section => section.classList.remove("active"));
        el.navItems.forEach(nav => nav.classList.remove("active"));

        // Close mobile sidebar if open
        if (el.sidebar) el.sidebar.classList.remove("mobile-open");

        if (primaryRoute === "review" && routeParam) {
            const reviewSec = document.getElementById("view-review");
            if (reviewSec) reviewSec.classList.add("active");
            loadAnalysisReview(routeParam);
        } else {
            const targetSec = document.getElementById(`view-${primaryRoute}`);
            if (targetSec) {
                targetSec.classList.add("active");
            } else {
                document.getElementById("view-dashboard").classList.add("active");
            }

            const activeNav = document.getElementById(`nav-${primaryRoute}`);
            if (activeNav) activeNav.classList.add("active");

            // Trigger view-specific data loaders
            if (primaryRoute === "dashboard") loadDashboardData();
            else if (primaryRoute === "new-analysis") prepareNewAnalysisView();
            else if (primaryRoute === "policies") loadPoliciesView();
            else if (primaryRoute === "history") loadHistoryView();
        }
    }

    // --- Dashboard View ---

    async function loadDashboardData() {
        try {
            const stats = await apiFetch("/api/stats");
            el.statDocs.textContent = stats.documents_analyzed;
            el.statConflicts.textContent = stats.policy_conflicts;
            el.statManual.textContent = stats.manual_reviews;

            el.recentTableBody.innerHTML = "";
            if (!stats.recent || stats.recent.length === 0) {
                el.recentEmptyState.classList.remove("hidden");
                el.recentTable.classList.add("hidden");
            } else {
                el.recentEmptyState.classList.add("hidden");
                el.recentTable.classList.remove("hidden");

                stats.recent.forEach(item => {
                    const tr = document.createElement("tr");

                    // Filename (Safe text)
                    const tdName = createEl("td", "td-filename", item.filename);
                    tr.appendChild(tdName);

                    // Type
                    const tdType = createEl("td", null, (item.file_type || "pdf").toUpperCase());
                    tr.appendChild(tdType);

                    // Date
                    const dateStr = item.created_at ? item.created_at.split("T")[0] : "";
                    const tdDate = createEl("td", null, dateStr);
                    tr.appendChild(tdDate);

                    // Conflicts
                    const tdConf = document.createElement("td");
                    const spanConf = createEl("span", "status-badge status-potential_conflict", `⚠️ ${item.conflicts}`);
                    tdConf.appendChild(spanConf);
                    tr.appendChild(tdConf);

                    // Reviews
                    const tdRev = document.createElement("td");
                    const spanRev = createEl("span", "status-badge status-review_recommended", `🔎 ${item.reviews}`);
                    tdRev.appendChild(spanRev);
                    tr.appendChild(tdRev);

                    // Action
                    const tdAction = document.createElement("td");
                    const btnOpen = createEl("button", "btn btn-secondary btn-sm", "View Review");
                    btnOpen.addEventListener("click", () => navigate(`review/${item.id}`));
                    tdAction.appendChild(btnOpen);
                    tr.appendChild(tdAction);

                    el.recentTableBody.appendChild(tr);
                });
            }
        } catch (e) {
            showToast("Failed to load dashboard metrics.", "error");
        }
    }

    // --- New Analysis View ---

    async function prepareNewAnalysisView() {
        // Load active policies checklist
        try {
            const policies = await apiFetch("/api/policies");
            state.policies = policies;
            renderPolicyChecklist(policies);
        } catch (e) {
            showToast("Failed to load policies.", "error");
        }
    }

    function renderPolicyChecklist(policies) {
        el.policyChecklist.innerHTML = "";
        if (!policies || policies.length === 0) {
            const p = createEl("p", "empty-desc", "No policies available. Click 'Configure Policies' to create or seed policies.");
            el.policyChecklist.appendChild(p);
            return;
        }

        policies.forEach(p => {
            const itemLabel = createEl("label", "policy-check-item");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = p.id;
            checkbox.checked = p.enabled === 1;

            const customCheck = createEl("span", "checkbox-custom");
            const infoDiv = createEl("div", "policy-check-info");
            const titleSpan = createEl("span", "policy-check-title", p.name);
            const descSpan = createEl("span", "policy-check-desc", p.explanation || `Category: ${p.category}`);

            infoDiv.appendChild(titleSpan);
            infoDiv.appendChild(descSpan);

            itemLabel.appendChild(checkbox);
            itemLabel.appendChild(customCheck);
            itemLabel.appendChild(infoDiv);

            el.policyChecklist.appendChild(itemLabel);
        });
    }

    function setSelectedFile(file) {
        state.selectedFile = file;
        if (file) {
            el.selectedFileName.textContent = file.name;
            const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
            el.selectedFileSize.textContent = `${sizeMb} MB`;
            el.fileSelectedInfo.classList.remove("hidden");
            el.dropZone.classList.add("hidden");
            el.startAnalyzeBtn.disabled = false;
        } else {
            el.fileSelectedInfo.classList.add("hidden");
            el.dropZone.classList.remove("hidden");
            el.fileInput.value = "";
            el.startAnalyzeBtn.disabled = true;
        }
    }

    // Drag and drop handlers
    el.dropZone.addEventListener("click", () => el.fileInput.click());
    el.dropZone.addEventListener("dragover", e => {
        e.preventDefault();
        el.dropZone.classList.add("dragover");
    });
    el.dropZone.addEventListener("dragleave", () => el.dropZone.classList.remove("dragover"));
    el.dropZone.addEventListener("drop", e => {
        e.preventDefault();
        el.dropZone.classList.remove("dragover");
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            setSelectedFile(file);
        }
    });
    el.fileInput.addEventListener("change", e => {
        if (e.target.files && e.target.files.length > 0) {
            setSelectedFile(e.target.files[0]);
        }
    });
    el.removeFileBtn.addEventListener("click", () => setSelectedFile(null));

    // Demo sample chips quick-loader
    document.querySelectorAll(".sample-chip").forEach(chip => {
        chip.addEventListener("click", async () => {
            const sampleName = chip.getAttribute("data-sample");
            try {
                const resp = await fetch(`/sample_contracts/${sampleName}`);
                if (!resp.ok) throw new Error("Sample file not found.");
                const blob = await resp.blob();
                const file = new File([blob], sampleName, { type: blob.type });
                setSelectedFile(file);
                showToast(`Loaded sample contract: ${sampleName}`, "success");
            } catch (err) {
                showToast(`Could not load sample contract (${err.message})`, "error");
            }
        });
    });

    // Toggle All Policies
    el.toggleAllPoliciesBtn.addEventListener("click", () => {
        const checkboxes = el.policyChecklist.querySelectorAll("input[type='checkbox']");
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => (cb.checked = !allChecked));
        el.toggleAllPoliciesBtn.textContent = allChecked ? "Select All" : "Deselect All";
    });

    // Run Analysis
    el.startAnalyzeBtn.addEventListener("click", async () => {
        if (!state.selectedFile) return;

        const checkedBoxes = el.policyChecklist.querySelectorAll("input[type='checkbox']:checked");
        const selectedPolicyIds = Array.from(checkedBoxes).map(cb => cb.value).join(",");
        const useNemotron = el.nemotronOptIn.checked;

        const formData = new FormData();
        formData.append("file", state.selectedFile);
        if (selectedPolicyIds) formData.append("policy_ids", selectedPolicyIds);
        formData.append("use_nemotron", useNemotron ? "true" : "false");

        // UI progress state
        el.startAnalyzeBtn.disabled = true;
        el.analyzeBtnSpinner.classList.remove("hidden");
        el.analyzeBtnText.textContent = "Analyzing Document...";
        el.analysisProgressBox.classList.remove("hidden");

        try {
            const result = await apiFetch("/api/analyze", {
                method: "POST",
                body: formData
            });

            showToast("Contract analysis completed!", "success");
            // Reset input
            setSelectedFile(null);
            // Navigate directly to the review workspace
            navigate(`review/${result.analysis_id}`);
        } catch (err) {
            showToast(err.message, "error");
        } finally {
            el.startAnalyzeBtn.disabled = false;
            el.analyzeBtnSpinner.classList.add("hidden");
            el.analyzeBtnText.textContent = "Analyze Contract";
            el.analysisProgressBox.classList.add("hidden");
        }
    });

    // --- Review Workspace ---

    async function loadAnalysisReview(analysisId) {
        try {
            const data = await apiFetch(`/api/history/${analysisId}`);
            state.currentAnalysis = data.analysis;
            state.currentSegments = data.segments || [];
            state.currentFindings = data.findings || [];
            state.activeFilter = "all";
            state.activeFindingIndex = -1;

            renderReviewWorkspace(data);
        } catch (err) {
            showToast(`Could not load analysis #${analysisId}: ${err.message}`, "error");
            navigate("history");
        }
    }

    function renderReviewWorkspace(data) {
        const analysis = data.analysis;
        const findings = data.findings || [];
        const segments = data.segments || [];
        const summary = data.summary || {};

        // Title and header
        el.reviewDocTitle.textContent = analysis.filename;
        el.reviewDocTypeBadge.textContent = (analysis.file_type || "pdf").toUpperCase();

        // Download Report Button Link
        el.downloadPdfReportBtn.onclick = () => {
            window.location.href = `/api/reports/${analysis.id}`;
        };

        // Nemotron status banner
        if (analysis.nemotron_used) {
            el.nemotronStatusBanner.className = "info-banner";
            el.nemotronBannerText.textContent = "Advanced AI interpretation (Nemotron) was applied to ambiguous clauses.";
        } else {
            el.nemotronStatusBanner.className = "info-banner";
            el.nemotronBannerText.textContent = analysis.nemotron_note || "Advanced interpretation was not used. Results are rule-based.";
        }

        // Scanned Document Alert
        if (analysis.extraction_status === "scanned_no_text") {
            el.scannedAlertBanner.classList.remove("hidden");
            el.scannedAlertMessage.textContent = "This PDF appears to be scanned images with no extractable text. OCR is required and is not enabled in this version.";
        } else {
            el.scannedAlertBanner.classList.add("hidden");
        }

        // Summary counts
        el.summaryConflictsCount.textContent = summary.potential_conflicts || 0;
        el.summaryReviewsCount.textContent = summary.review_recommended || 0;
        el.summaryNoConflictsCount.textContent = summary.no_conflict_detected || 0;

        // Policies evaluated list
        const policiesSnapshot = analysis.policies_snapshot || [];
        if (policiesSnapshot.length > 0) {
            el.summaryPoliciesList.textContent = policiesSnapshot.map(p => p.name).join(", ");
        } else {
            el.summaryPoliciesList.textContent = "None";
        }

        // Filter Counts
        updateFilterCounts(findings);

        // Render Left Panel: Segments in Document Order
        renderSegments(segments);

        // Render Right Panel: Findings
        filterAndRenderFindings();

        // Auto select first finding if available
        if (findings.length > 0) {
            selectFindingByIndex(0);
        }
    }

    function updateFilterCounts(findings) {
        const counts = {
            all: findings.length,
            conflicts: findings.filter(f => f.status === "potential_conflict").length,
            manual: findings.filter(f => f.manual_review === 1).length,
            payment: findings.filter(f => f.category === "payment").length,
            renewal: findings.filter(f => f.category === "renewal").length,
            liability: findings.filter(f => f.category === "liability").length,
            jurisdiction: findings.filter(f => f.category === "jurisdiction").length,
            other: findings.filter(f => !["payment", "renewal", "liability", "jurisdiction"].includes(f.category)).length
        };

        el.cntAll.textContent = counts.all;
        el.cntConflicts.textContent = counts.conflicts;
        el.cntManual.textContent = counts.manual;
        el.cntPayment.textContent = counts.payment;
        el.cntRenewal.textContent = counts.renewal;
        el.cntLiability.textContent = counts.liability;
        el.cntJurisdiction.textContent = counts.jurisdiction;
        el.cntOther.textContent = counts.other;
        el.mobileFindingsBadge.textContent = counts.all;
    }

    function renderSegments(segments) {
        el.segmentsContainer.innerHTML = "";
        if (!segments || segments.length === 0) {
            const p = createEl("p", "empty-desc", "No extracted text layer found in this document.");
            el.segmentsContainer.appendChild(p);
            return;
        }

        let currentPageOrPara = null;

        segments.forEach(seg => {
            const locType = seg.location_type;
            const pageNum = seg.page_number;
            const paraIdx = seg.paragraph_index;

            // Page or Block Divider
            if (locType === "page" && pageNum !== currentPageOrPara) {
                currentPageOrPara = pageNum;
                const div = createEl("div", "page-divider", `— Page ${pageNum} —`);
                el.segmentsContainer.appendChild(div);
            } else if (locType === "paragraph" && paraIdx !== currentPageOrPara && (paraIdx === 1 || paraIdx % 10 === 0)) {
                currentPageOrPara = paraIdx;
                const div = createEl("div", "page-divider", `— Paragraph ${paraIdx} —`);
                el.segmentsContainer.appendChild(div);
            }

            // Segment Element (XSS-safe textContent)
            const segDiv = createEl("div", "segment-item", seg.text);
            segDiv.id = `seg-${seg.evidence_id}`;
            segDiv.setAttribute("data-evidence-id", seg.evidence_id);
            el.segmentsContainer.appendChild(segDiv);
        });
    }

    function filterAndRenderFindings() {
        const filter = state.activeFilter;
        let list = state.currentFindings;

        if (filter === "conflicts") {
            list = list.filter(f => f.status === "potential_conflict");
        } else if (filter === "manual") {
            list = list.filter(f => f.manual_review === 1);
        } else if (filter === "payment") {
            list = list.filter(f => f.category === "payment");
        } else if (filter === "renewal") {
            list = list.filter(f => f.category === "renewal");
        } else if (filter === "liability") {
            list = list.filter(f => f.category === "liability");
        } else if (filter === "jurisdiction") {
            list = list.filter(f => f.category === "jurisdiction");
        } else if (filter === "other") {
            list = list.filter(f => !["payment", "renewal", "liability", "jurisdiction"].includes(f.category));
        }

        state.filteredFindings = list;
        el.findingsContainer.innerHTML = "";

        if (list.length === 0) {
            const emptyP = createEl("p", "empty-desc", "No findings match the selected filter.");
            el.findingsContainer.appendChild(emptyP);
            el.findingIndexIndicator.textContent = "0 of 0";
            return;
        }

        list.forEach((finding, idx) => {
            const card = renderFindingCard(finding, idx);
            el.findingsContainer.appendChild(card);
        });

        if (state.activeFindingIndex >= 0 && state.activeFindingIndex < list.length) {
            selectFindingByIndex(state.activeFindingIndex);
        } else {
            selectFindingByIndex(0);
        }
    }

    function renderFindingCard(finding, index) {
        const card = createEl("div", `finding-card status-${finding.status}`);
        card.id = `finding-card-${index}`;

        // Header Row
        const headerRow = createEl("div", "finding-header-row");
        const title = createEl("span", "finding-title", finding.title);

        let badgeIcon = "✓";
        let badgeLabel = "No Conflict Detected";
        if (finding.status === "potential_conflict") {
            badgeIcon = "⚠️";
            badgeLabel = "Potential Conflict";
        } else if (finding.status === "review_recommended") {
            badgeIcon = "🔎";
            badgeLabel = "Review Recommended";
        }

        const badge = createEl("span", `status-badge status-${finding.status}`, `${badgeIcon} ${badgeLabel}`);
        headerRow.appendChild(title);
        headerRow.appendChild(badge);
        card.appendChild(headerRow);

        // Metadata Row
        const metaRow = createEl("div", "finding-meta-row");
        const catTag = createEl("span", "meta-tag", (finding.category || "").toUpperCase());
        const locTag = createEl("span", "meta-tag", finding.location_label || "Document-wide");

        metaRow.appendChild(catTag);
        metaRow.appendChild(locTag);

        let policySnap = null;
        try {
            policySnap = JSON.parse(finding.policy_snapshot_json);
        } catch (_) {}

        if (policySnap && policySnap.name) {
            const polTag = createEl("span", "meta-policy", `Policy: ${policySnap.name}`);
            metaRow.appendChild(polTag);
        }
        card.appendChild(metaRow);

        // Plain-Language Explanation (XSS safe)
        const expP = createEl("p", "finding-explanation", finding.explanation);
        card.appendChild(expP);

        // Verified Quote Box
        if (finding.quote && finding.quote !== "No matching clause detected in document.") {
            const quoteBox = createEl("div", "finding-quote-box");
            const qLabel = createEl("span", "quote-label", `Verified Quote (${finding.location_label}):`);
            const qText = createEl("span", null, `"${finding.quote}"`);
            quoteBox.appendChild(qLabel);
            quoteBox.appendChild(qText);
            card.appendChild(quoteBox);
        }

        // Actionable Next Step Box
        if (finding.next_step) {
            const nextBox = createEl("div", "finding-next-step-box");
            const icon = createEl("span", "next-step-icon", "👉");
            const text = createEl("span", null, finding.next_step);
            nextBox.appendChild(icon);
            nextBox.appendChild(text);
            card.appendChild(nextBox);
        }

        // Manual Review Indicator
        if (finding.manual_review === 1) {
            const manDiv = createEl("div", "manual-indicator-pill", "👤 Manual review required by reviewer");
            card.appendChild(manDiv);
        }

        // Click to select & scroll
        card.addEventListener("click", () => selectFindingByIndex(index));

        return card;
    }

    function selectFindingByIndex(index) {
        if (!state.filteredFindings || state.filteredFindings.length === 0) return;
        if (index < 0 || index >= state.filteredFindings.length) return;

        state.activeFindingIndex = index;
        const finding = state.filteredFindings[index];

        // Update nav buttons & counter
        el.findingIndexIndicator.textContent = `${index + 1} of ${state.filteredFindings.length}`;

        // Highlight card in right panel
        document.querySelectorAll(".finding-card").forEach((c, idx) => {
            if (idx === index) c.classList.add("active-finding");
            else c.classList.remove("active-finding");
        });

        // Scroll finding card into view smoothly
        const activeCard = document.getElementById(`finding-card-${index}`);
        if (activeCard) {
            activeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }

        // Highlight and scroll left panel evidence
        highlightEvidenceSegment(finding);
    }

    function highlightEvidenceSegment(finding) {
        // Clear previous highlights
        document.querySelectorAll(".segment-item").forEach(item => {
            item.classList.remove("active-evidence");
            // If the element was altered by mark tag, restore textContent
            if (item.querySelector("mark")) {
                const rawText = item.getAttribute("data-original-text");
                if (rawText !== null) item.textContent = rawText;
            }
        });

        const evId = finding.evidence_id;
        if (!evId || evId === "doc_wide") return;

        const targetSeg = document.getElementById(`seg-${evId}`);
        if (!targetSeg) return;

        targetSeg.classList.add("active-evidence");

        // Character offset verification
        const originalText = targetSeg.textContent;
        targetSeg.setAttribute("data-original-text", originalText);

        const quote = (finding.quote || "").trim();
        let exactHighlightSuccess = false;

        if (quote && originalText.includes(quote)) {
            // Safe char highlight injection
            const matchIndex = originalText.indexOf(quote);
            const before = originalText.substring(0, matchIndex);
            const matchText = originalText.substring(matchIndex, matchIndex + quote.length);
            const after = originalText.substring(matchIndex + quote.length);

            targetSeg.innerHTML = "";
            targetSeg.appendChild(document.createTextNode(before));
            const mark = createEl("mark", "char-highlight", matchText);
            targetSeg.appendChild(mark);
            targetSeg.appendChild(document.createTextNode(after));
            exactHighlightSuccess = true;
        }

        // Scroll into view
        targetSeg.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    // Previous / Next Navigation
    el.prevFindingBtn.addEventListener("click", () => {
        if (state.activeFindingIndex > 0) {
            selectFindingByIndex(state.activeFindingIndex - 1);
        }
    });

    el.nextFindingBtn.addEventListener("click", () => {
        if (state.activeFindingIndex < state.filteredFindings.length - 1) {
            selectFindingByIndex(state.activeFindingIndex + 1);
        }
    });

    // Keyboard Shortcuts (ArrowUp / ArrowDown in review workspace)
    document.addEventListener("keydown", e => {
        const reviewSection = document.getElementById("view-review");
        if (reviewSection && reviewSection.classList.contains("active")) {
            if (e.key === "ArrowDown" || e.key === "j") {
                if (state.activeFindingIndex < state.filteredFindings.length - 1) {
                    e.preventDefault();
                    selectFindingByIndex(state.activeFindingIndex + 1);
                }
            } else if (e.key === "ArrowUp" || e.key === "k") {
                if (state.activeFindingIndex > 0) {
                    e.preventDefault();
                    selectFindingByIndex(state.activeFindingIndex - 1);
                }
            }
        }
        if (e.key === "Escape") {
            closePolicyModal();
        }
    });

    // Filters Bar Clicks
    el.filterChips.forEach(chip => {
        chip.addEventListener("click", () => {
            el.filterChips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            state.activeFilter = chip.getAttribute("data-filter");
            filterAndRenderFindings();
        });
    });

    // Mobile Switcher Tabs
    el.tabBtnDocument.addEventListener("click", () => {
        el.tabBtnDocument.classList.add("active");
        el.tabBtnFindings.classList.remove("active");
        el.reviewLeftPanel.classList.add("mobile-active");
        el.reviewRightPanel.classList.remove("mobile-active");
    });
    el.tabBtnFindings.addEventListener("click", () => {
        el.tabBtnFindings.classList.add("active");
        el.tabBtnDocument.classList.remove("active");
        el.reviewRightPanel.classList.add("mobile-active");
        el.reviewLeftPanel.classList.remove("mobile-active");
    });

    // --- Policies View & Modal ---

    async function loadPoliciesView() {
        try {
            const policies = await apiFetch("/api/policies");
            state.policies = policies;
            renderPoliciesGrid(policies);
        } catch (err) {
            showToast("Failed to load policy list.", "error");
        }
    }

    function renderPoliciesGrid(policies) {
        el.policiesListGrid.innerHTML = "";
        if (!policies || policies.length === 0) {
            el.policiesListEmpty.classList.remove("hidden");
            return;
        }
        el.policiesListEmpty.classList.add("hidden");

        policies.forEach(p => {
            const card = createEl("div", "policy-card");

            const topDiv = createEl("div", "policy-card-top");
            const header = createEl("div", "policy-card-header");
            const title = createEl("span", "policy-card-title", p.name);
            const typeBadge = createEl("span", "policy-type-tag", p.type);
            header.appendChild(title);
            header.appendChild(typeBadge);
            topDiv.appendChild(header);

            const desc = createEl("p", "policy-card-desc", p.explanation || "No description provided.");
            topDiv.appendChild(desc);

            const paramsStr = typeof p.params === "object" ? JSON.stringify(p.params) : p.params_json;
            const paramTag = createEl("div", "policy-params-tag", `Mode: ${p.mode} | Params: ${paramsStr}`);
            topDiv.appendChild(paramTag);

            card.appendChild(topDiv);

            // Action row
            const actionRow = createEl("div", "policy-card-actions");
            const toggleLabel = createEl("label", "checkbox-label");
            const toggleInput = document.createElement("input");
            toggleInput.type = "checkbox";
            toggleInput.checked = p.enabled === 1;
            toggleInput.addEventListener("change", async () => {
                await togglePolicyEnabled(p, toggleInput.checked);
            });
            const toggleCustom = createEl("span", "checkbox-custom");
            const toggleText = createEl("span", null, toggleInput.checked ? "Enabled" : "Disabled");
            toggleLabel.appendChild(toggleInput);
            toggleLabel.appendChild(toggleCustom);
            toggleLabel.appendChild(toggleText);

            const btnGroup = createEl("div", "policy-buttons-group");
            const editBtn = createEl("button", "btn btn-secondary btn-sm", "Edit");
            editBtn.addEventListener("click", () => openEditPolicyModal(p));

            const delBtn = createEl("button", "btn btn-danger-outline btn-sm", "Delete");
            delBtn.addEventListener("click", () => deletePolicy(p.id));

            btnGroup.appendChild(editBtn);
            btnGroup.appendChild(delBtn);

            actionRow.appendChild(toggleLabel);
            actionRow.appendChild(btnGroup);
            card.appendChild(actionRow);

            el.policiesListGrid.appendChild(card);
        });
    }

    async function togglePolicyEnabled(policy, isEnabled) {
        try {
            await apiFetch(`/api/policies/${policy.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: policy.name,
                    type: policy.type,
                    mode: policy.mode,
                    params: policy.params,
                    explanation: policy.explanation,
                    enabled: isEnabled ? 1 : 0
                })
            });
            showToast(`Policy '${policy.name}' updated.`, "success");
            loadPoliciesView();
        } catch (err) {
            showToast(`Error updating policy: ${err.message}`, "error");
        }
    }

    // Example Policies Seed Button
    el.seedExamplePoliciesBtn.addEventListener("click", async () => {
        try {
            const resp = await apiFetch("/api/policies/seed_examples", { method: "POST" });
            showToast(`Seeded ${resp.count} recommended demo policies.`, "success");
            loadPoliciesView();
        } catch (err) {
            showToast(`Failed to seed policies: ${err.message}`, "error");
        }
    });

    // Modal Form Logic
    function updateParamFieldVisibility() {
        const type = el.policyTypeSelect.value;
        const mode = el.policyModeSelect.value;

        if (mode === "free_text") {
            el.paramGroupPayment.classList.add("hidden");
            el.paramGroupRenewal.classList.add("hidden");
            el.paramGroupLiability.classList.add("hidden");
            el.paramGroupJurisdiction.classList.add("hidden");
            return;
        }

        el.paramGroupPayment.classList.toggle("hidden", type !== "payment");
        el.paramGroupRenewal.classList.toggle("hidden", type !== "renewal");
        el.paramGroupLiability.classList.toggle("hidden", type !== "liability");
        el.paramGroupJurisdiction.classList.toggle("hidden", type !== "jurisdiction");
    }

    el.policyTypeSelect.addEventListener("change", updateParamFieldVisibility);
    el.policyModeSelect.addEventListener("change", updateParamFieldVisibility);

    function openAddPolicyModal() {
        el.policyModalTitle.textContent = "Add New Policy";
        el.policyEditId.value = "";
        el.policyNameInput.value = "";
        el.policyTypeSelect.value = "payment";
        el.policyModeSelect.value = "structured";
        el.policyExplanationInput.value = "";
        el.policyEnabledInput.checked = true;

        el.paramMaxPaymentDays.value = 30;
        el.paramAutoRenewalProhibited.checked = true;
        el.paramMaxNoticeDays.value = 30;
        el.paramLiabilityRule.value = "cap_not_exceed_fees";
        el.paramApprovedJurisdictions.value = "India, Indian law, Chennai, Bengaluru";

        updateParamFieldVisibility();
        el.policyModal.classList.remove("hidden");
        el.policyNameInput.focus();
    }

    function openEditPolicyModal(p) {
        el.policyModalTitle.textContent = "Edit Policy";
        el.policyEditId.value = p.id;
        el.policyNameInput.value = p.name;
        el.policyTypeSelect.value = p.type;
        el.policyModeSelect.value = p.mode;
        el.policyExplanationInput.value = p.explanation || "";
        el.policyEnabledInput.checked = p.enabled === 1;

        const params = p.params || {};
        if (p.type === "payment") {
            el.paramMaxPaymentDays.value = params.max_payment_days || 30;
        } else if (p.type === "renewal") {
            el.paramAutoRenewalProhibited.checked = params.auto_renewal_prohibited !== false;
            el.paramMaxNoticeDays.value = params.max_notice_days || 30;
        } else if (p.type === "liability") {
            el.paramLiabilityRule.value = params.rule || "cap_not_exceed_fees";
        } else if (p.type === "jurisdiction") {
            const list = params.approved || ["India", "Chennai"];
            el.paramApprovedJurisdictions.value = list.join(", ");
        }

        updateParamFieldVisibility();
        el.policyModal.classList.remove("hidden");
        el.policyNameInput.focus();
    }

    function closePolicyModal() {
        el.policyModal.classList.add("hidden");
    }

    el.openAddPolicyModalBtn.addEventListener("click", openAddPolicyModal);
    el.closePolicyModalBtn.addEventListener("click", closePolicyModal);
    el.cancelPolicyBtn.addEventListener("click", closePolicyModal);

    el.policyForm.addEventListener("submit", async e => {
        e.preventDefault();
        const editId = el.policyEditId.value;
        const name = el.policyNameInput.value.trim();
        const pType = el.policyTypeSelect.value;
        const pMode = el.policyModeSelect.value;
        const explanation = el.policyExplanationInput.value.trim();
        const enabled = el.policyEnabledInput.checked ? 1 : 0;

        const params = {};
        if (pMode === "structured") {
            if (pType === "payment") {
                params.max_payment_days = parseInt(el.paramMaxPaymentDays.value, 10);
            } else if (pType === "renewal") {
                params.auto_renewal_prohibited = el.paramAutoRenewalProhibited.checked;
                const noticeVal = el.paramMaxNoticeDays.value;
                params.max_notice_days = noticeVal ? parseInt(noticeVal, 10) : null;
            } else if (pType === "liability") {
                params.rule = el.paramLiabilityRule.value;
            } else if (pType === "jurisdiction") {
                params.approved = el.paramApprovedJurisdictions.value
                    .split(",")
                    .map(x => x.trim())
                    .filter(x => x.length > 0);
            }
        }

        const payload = {
            name: name,
            type: pType,
            mode: pMode,
            params: params,
            explanation: explanation,
            enabled: enabled
        };

        try {
            if (editId) {
                await apiFetch(`/api/policies/${editId}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                showToast("Policy updated successfully.", "success");
            } else {
                await apiFetch("/api/policies", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                showToast("Policy created successfully.", "success");
            }
            closePolicyModal();
            loadPoliciesView();
        } catch (err) {
            showToast(err.message, "error");
        }
    });

    async function deletePolicy(policyId) {
        if (!confirm(`Are you sure you want to delete policy #${policyId}?`)) return;
        try {
            await apiFetch(`/api/policies/${policyId}`, { method: "DELETE" });
            showToast("Policy deleted.", "success");
            loadPoliciesView();
        } catch (err) {
            showToast(`Could not delete policy: ${err.message}`, "error");
        }
    }

    // --- History View ---

    async function loadHistoryView() {
        try {
            const items = await apiFetch("/api/history");
            el.historyTableBody.innerHTML = "";

            if (!items || items.length === 0) {
                el.historyEmptyState.classList.remove("hidden");
                el.historyTable.classList.add("hidden");
                return;
            }

            el.historyEmptyState.classList.add("hidden");
            el.historyTable.classList.remove("hidden");

            items.forEach(item => {
                const tr = document.createElement("tr");

                const tdName = createEl("td", "td-filename", item.filename);
                tr.appendChild(tdName);

                const tdType = createEl("td", null, (item.file_type || "pdf").toUpperCase());
                tr.appendChild(tdType);

                const dateStr = item.created_at ? item.created_at.split("T")[0] : "";
                const tdDate = createEl("td", null, dateStr);
                tr.appendChild(tdDate);

                const tdStatus = createEl("td", null, item.extraction_status);
                tr.appendChild(tdStatus);

                const tdConf = document.createElement("td");
                const confCount = item.summary ? item.summary.potential_conflicts : 0;
                const spanConf = createEl("span", "status-badge status-potential_conflict", `⚠️ ${confCount}`);
                tdConf.appendChild(spanConf);
                tr.appendChild(tdConf);

                const tdRev = document.createElement("td");
                const revCount = item.summary ? item.summary.review_recommended : 0;
                const spanRev = createEl("span", "status-badge status-review_recommended", `🔎 ${revCount}`);
                tdRev.appendChild(spanRev);
                tr.appendChild(tdRev);

                const tdAction = document.createElement("td");
                const openBtn = createEl("button", "btn btn-secondary btn-sm", "Open");
                openBtn.addEventListener("click", () => navigate(`review/${item.id}`));

                const delBtn = createEl("button", "btn btn-danger-outline btn-sm", "Delete");
                delBtn.addEventListener("click", async () => {
                    if (confirm(`Delete analysis for "${item.filename}"?`)) {
                        await deleteAnalysis(item.id);
                    }
                });

                tdAction.appendChild(openBtn);
                tdAction.appendChild(document.createTextNode(" "));
                tdAction.appendChild(delBtn);
                tr.appendChild(tdAction);

                el.historyTableBody.appendChild(tr);
            });
        } catch (err) {
            showToast("Failed to load history.", "error");
        }
    }

    async function deleteAnalysis(analysisId) {
        try {
            await apiFetch(`/api/history/${analysisId}`, { method: "DELETE" });
            showToast("Analysis deleted.", "success");
            loadHistoryView();
        } catch (err) {
            showToast(`Could not delete analysis: ${err.message}`, "error");
        }
    }

    el.purgeRetentionBtn.addEventListener("click", async () => {
        try {
            const resp = await apiFetch("/api/retention/purge", { method: "POST" });
            showToast(`Purged ${resp.count} expired analyses.`, "success");
            loadHistoryView();
        } catch (err) {
            showToast(`Error purging retention: ${err.message}`, "error");
        }
    });

    el.deleteAllHistoryBtn.addEventListener("click", async () => {
        if (!confirm("Are you sure you want to delete ALL stored contract analyses from this machine? This action cannot be undone.")) return;
        try {
            const resp = await apiFetch("/api/history", { method: "DELETE" });
            showToast(`Deleted all ${resp.count} stored analyses.`, "success");
            loadHistoryView();
        } catch (err) {
            showToast(`Error deleting history: ${err.message}`, "error");
        }
    });

    // Mobile nav toggle
    if (el.mobileNavToggle && el.sidebar) {
        el.mobileNavToggle.addEventListener("click", () => {
            el.sidebar.classList.toggle("mobile-open");
            const isOpen = el.sidebar.classList.contains("mobile-open");
            el.mobileNavToggle.setAttribute("aria-expanded", String(isOpen));
        });
    }

    // App Initialization
    async function init() {
        await initCsrfToken();
        window.addEventListener("hashchange", handleHashChange);
        handleHashChange();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
