// Generated from studio/src; run npm --prefix studio run build. Do not edit.
import { authorityText, decodeResponse, element, errorInfo, exportFormat } from "./transport.js";
"use strict";
(() => {
    const tags = {
        "workspace": "main",
        "page-title": "h1",
        "context-badge": "span",
        "context-description": "span",
        "connection-message": "div",
        "error-panel": "section",
        "error-title": "strong",
        "error-message": "p",
        "error-details": "details",
        "error-detail-text": "pre",
        "dismiss-error": "button",
        "build-form": "form",
        "intent-section": "section",
        "intent-title": "h2",
        "mode-badge": "span",
        "intent-description": "p",
        "product-controls": "fieldset",
        "product-options": "div",
        "imported-product": "div",
        "imported-product-name": "strong",
        "cue-label": "span",
        "response-label": "span",
        "intent-source-summary": "p",
        "cell-type": "dd",
        "target-name": "dd",
        "architecture-section": "section",
        "architecture-title": "h2",
        "architecture-controls": "fieldset",
        "max-length": "input",
        "length-help": "p",
        "imported-constraints": "div",
        "imported-constraints-text": "pre",
        "library-label": "p",
        "compile-button": "button",
        "compile-label": "span",
        "build-status": "p",
        "import-panel": "details",
        "request-file": "input",
        "request-json": "textarea",
        "import-help": "p",
        "import-button": "button",
        "example-button": "button",
        "result-section": "section",
        "result-title": "h2",
        "result-badge": "span",
        "empty-result": "div",
        "empty-title": "h3",
        "empty-description": "p",
        "result-content": "div",
        "result-outcome": "div",
        "outcome-eyebrow": "div",
        "outcome-title": "h3",
        "outcome-description": "p",
        "length-metric": "div",
        "result-length": "strong",
        "no-candidate-help": "div",
        "no-candidate-description": "p",
        "molecule-section": "section",
        "molecule-title": "h3",
        "architecture-name": "span",
        "molecule-track": "div",
        "part-legend": "ul",
        "parts-table": "tbody",
        "sequence-section": "section",
        "sequence-title": "h3",
        "copy-sequence": "button",
        "sequence": "pre",
        "protein-sequence": "code",
        "checks-title": "h3",
        "checks-list": "ul",
        "alternatives-details": "details",
        "alternatives-count": "span",
        "selection-explanation": "p",
        "alternatives-list": "div",
        "unresolved-count": "span",
        "unresolved-list": "ul",
        "build-fingerprint": "dd",
        "completion-scope": "dd",
        "therapeutic-status": "dd",
        "admission-status": "dd",
        "source-summary": "dd",
        "download-title": "h3",
        "download-status": "p",
        "app-version": "span"
    };
    function byId(id) { return element(id, tags[id]); }
    const exports = [...document.querySelectorAll("[data-export]")];
    const state = {
        token: null, example: null, mode: "guided", request: null, requestRaw: null, overview: null,
        record: null, recordRaw: null, summary: null, busy: false, revision: 0, operation: 0,
        controller: null,
    };
    const regionNames = {
        five_prime_utr: "5′ UTR", cds: "CDS", three_prime_utr: "3′ UTR", poly_a: "Poly(A)",
    };
    const stageNames = {
        requirements: "Source requirements", selection: "Bounded selection",
        components: "Selected parts", layout: "Molecular layout", molecule: "Exact RNA",
    };
    const productNames = { declared_product: "Product A", alternative_product: "Product B" };
    const MAX_IMPORT_BYTES = 1024 * 1024;
    const MAX_POST_BYTES = 2 * 1024 * 1024;
    // Request/build JSON strings are the authority. Parsed objects are display-only:
    // reserializing them could round large integers or turn authored 1.0 into 1.
    // All artifact and error strings are data. Never insert them as HTML.
    function text(id, value) { byId(id).textContent = value == null ? "—" : String(value); }
    function node(tag, content, className) {
        const element = document.createElement(tag);
        if (content != null)
            element.textContent = String(content);
        if (className)
            element.className = className;
        return element;
    }
    function label(value) { return String(value == null ? "Unspecified" : value).replaceAll("_", " "); }
    function selected(name) { const input = document.querySelector(`input[name="${name}"]:checked`); if (!input)
        throw new Error(`Select a ${name}.`); return input.value; }
    function guidedProductName() { return productNames[selected("product")] || "the product"; }
    function regionClass(kind) { return `region-${Object.hasOwn(regionNames, kind) ? kind : "other"}`; }
    function hideError() { byId("error-panel").hidden = true; }
    function showError(value, title = "The build needs attention") {
        const error = errorInfo(value);
        text("error-title", title);
        text("error-message", error.message || "The local compiler could not complete this operation. Try again.");
        const details = error.details == null ? error.code : error.details;
        byId("error-details").hidden = !details;
        text("error-detail-text", typeof details === "string" ? details : JSON.stringify(details, null, 2));
        byId("error-panel").hidden = false;
    }
    async function api(path, payload, signal) {
        const options = { credentials: "same-origin", cache: "no-store", ...(signal ? { signal } : {}) };
        if (payload !== undefined) {
            if (!state.token)
                throw new Error("The Studio session is missing. Reload the page.");
            options.method = "POST";
            options.headers = { "Content-Type": "application/json", "X-Biocompiler-Token": state.token };
            options.body = JSON.stringify(payload);
            if (new Blob([options.body]).size > MAX_POST_BYTES) {
                throw new Error("This operation exceeds the studio's 2 MiB request limit after JSON encoding. Use a smaller request or the command-line workflow for this build.");
            }
        }
        let response;
        try {
            response = await fetch(path, options);
        }
        catch (error) {
            if (errorInfo(error).name === "AbortError")
                throw error;
            throw new Error("Cannot reach the local compiler. Make sure the studio server is still running, then try again.");
        }
        let envelope;
        try {
            envelope = await response.json();
        }
        catch {
            throw new Error("The server returned an unreadable response. Reload the studio and try again.");
        }
        return decodeResponse(path, envelope, response.status);
    }
    function syncControls() {
        const ready = Boolean(state.token);
        byId("request-file").disabled = !ready;
        byId("request-json").disabled = !ready;
        byId("product-controls").disabled = !ready || state.mode !== "guided";
        byId("architecture-controls").disabled = !ready || state.mode !== "guided";
        byId("compile-button").disabled = !ready || state.busy || (state.mode === "imported" && !state.request);
        byId("import-button").disabled = !ready || state.busy || !byId("request-json").value.trim();
        byId("example-button").disabled = !ready || state.mode === "guided";
        exports.forEach((button) => {
            button.disabled = !state.record || state.busy || (button.dataset.export === "fasta" && !state.summary?.sequence);
        });
        byId("copy-sequence").disabled = !state.summary?.sequence || state.busy;
        byId("result-section").setAttribute("aria-busy", String(state.busy));
        byId("result-section").classList.toggle("is-working", state.busy);
    }
    function clearResult(message) {
        state.record = null;
        state.recordRaw = null;
        state.summary = null;
        byId("result-content").hidden = true;
        byId("empty-result").hidden = false;
        text("sequence", "");
        text("protein-sequence", "");
        text("copy-sequence", "Copy sequence");
        text("download-status", "");
        text("result-badge", message ? "Inputs changed" : "Ready when you are");
        byId("result-badge").className = "small-badge";
        text("empty-title", message ? "Ready for a fresh build." : "A precise sequence, with its reasoning.");
        text("empty-description", message || "Compile the guided example to see the selected parts, every RNA letter and the checks behind the result.");
    }
    function invalidate(message, clearRequest = true) {
        state.revision += 1;
        state.operation += 1;
        state.controller?.abort();
        state.controller = null;
        state.busy = false;
        if (clearRequest) {
            state.request = null;
            state.requestRaw = null;
        }
        clearResult(message);
        hideError();
        text("compile-label", "Compile RNA candidate");
        text("build-status", state.mode === "imported" && !state.request ? "Validate the imported request to continue." : "Inputs changed. Compile to check a new candidate.");
        syncControls();
    }
    function startOperation() {
        state.controller?.abort();
        const ticket = { revision: state.revision, operation: ++state.operation, controller: new AbortController() };
        state.controller = ticket.controller;
        state.busy = true;
        hideError();
        syncControls();
        return ticket;
    }
    function current(ticket) { return ticket.revision === state.revision && ticket.operation === state.operation; }
    function finish(ticket) {
        if (!current(ticket))
            return;
        state.busy = false;
        state.controller = null;
        text("compile-label", "Compile RNA candidate");
        syncControls();
    }
    function showMode() {
        const imported = state.mode === "imported";
        byId("product-controls").hidden = imported;
        byId("architecture-controls").hidden = imported;
        byId("imported-product").hidden = !imported;
        byId("imported-constraints").hidden = !imported;
        text("mode-badge", imported ? "Imported · read-only" : "Guided example");
        text("intent-description", imported ? "The product requirement is retained from your source." : "Select the product this RNA should encode.");
        syncControls();
    }
    function showOverview(overview) {
        state.overview = overview;
        const guided = state.mode === "guided";
        text("cell-type", label(overview.cell_type));
        text("target-name", label(overview.target_name));
        text("cue-label", guided ? `${label(overview.cue)} is high` : "Authored condition");
        text("response-label", `Secrete ${guided ? guidedProductName() : overview.product}`);
        text("intent-source-summary", overview.source_summary);
        text("library-label", `Supplied library: ${overview.library_name}`);
        text("imported-product-name", overview.product);
        text("imported-constraints-text", overview.constraints_json || "Exact constraints are unavailable. Reload the studio before compiling.");
        text("context-badge", overview.fixture ? "Artificial example" : "Imported request");
        text("context-description", overview.fixture
            ? "These short parts test the compiler. A checked cassette does not implement sensing, secretion or a therapy."
            : "Your original requirements are retained. Structural checking does not establish biological function or human applicability.");
        showMode();
    }
    function populateProducts(overview) {
        const options = byId("product-options");
        options.replaceChildren();
        const products = [...overview.product_options].sort((a, b) => {
            if (a.id === "declared_product")
                return -1;
            if (b.id === "declared_product")
                return 1;
            return String(a.id).localeCompare(String(b.id));
        });
        products.forEach((product) => {
            const choice = node("label", null, "product-choice");
            const input = document.createElement("input");
            input.type = "radio";
            input.name = "product";
            input.value = product.id;
            input.checked = product.id === overview.product;
            const card = node("span");
            card.append(node("strong", productNames[product.id] || product.label), node("small", `Protein ${product.protein}`));
            choice.append(input, card);
            options.append(choice);
        });
    }
    function exampleControls() {
        const field = byId("max-length");
        const raw = field.value.trim();
        const maximum = raw === "" ? null : Number(raw);
        if (field.validity.badInput || (maximum !== null && (!Number.isSafeInteger(maximum) || maximum < 0))) {
            field.setCustomValidity("Enter a whole number of zero or more, or leave the field blank.");
            field.reportValidity();
            throw new Error("Maximum length must be a nonnegative whole number, or blank for no limit.");
        }
        field.setCustomValidity("");
        return { product: selected("product"), architecture: selected("architecture"), max_length: maximum };
    }
    function listItem(container, content, className) { const item = node("li", content, className); container.append(item); return item; }
    function renderParts(parts, length) {
        const track = byId("molecule-track");
        const legend = byId("part-legend");
        const table = byId("parts-table");
        track.replaceChildren();
        legend.replaceChildren();
        table.replaceChildren();
        const description = [];
        parts.forEach((part) => {
            const size = part.end - part.start;
            const name = regionNames[part.kind] || label(part.kind);
            const color = regionClass(part.kind);
            const segment = node("div", size / length >= .12 ? name : "", `molecule-segment ${color}`);
            segment.style.flex = `${Math.max(0, size)} 1 0%`;
            segment.title = `${name}: ${size} nucleotides · ${part.id}`;
            segment.setAttribute("aria-hidden", "true");
            track.append(segment);
            const item = listItem(legend, null);
            const swatch = node("span", null, `legend-swatch ${color}`);
            swatch.setAttribute("aria-hidden", "true");
            item.append(swatch, node("span", name), node("small", `${size} nt`));
            const row = node("tr");
            row.append(node("td", part.id), node("td", name), node("td", `${part.start + 1}–${part.end}`));
            table.append(row);
            description.push(`${name}, ${size} nucleotides`);
        });
        track.setAttribute("aria-label", `RNA from 5 prime to 3 prime: ${description.join("; ")}. Proportional region lengths.`);
    }
    function renderChecks(checks) {
        const list = byId("checks-list");
        list.replaceChildren();
        checks.forEach((check) => {
            const passed = String(check.outcome).toLowerCase() === "pass";
            const item = listItem(list, null);
            const icon = node("span", passed ? "✓" : "!", `check-icon${passed ? "" : " not-pass"}`);
            icon.setAttribute("aria-hidden", "true");
            const copy = node("span", `${stageNames[check.stage] || label(check.stage)} · ${passed ? "passed" : label(check.outcome)}`);
            if (check.detail)
                copy.title = typeof check.detail === "string" ? check.detail : JSON.stringify(check.detail);
            item.append(icon, copy);
        });
    }
    function renderAlternatives(alternatives, hasCandidate) {
        const list = byId("alternatives-list");
        list.replaceChildren();
        text("alternatives-count", alternatives.length);
        const preference = state.overview?.constraints?.preference;
        text("selection-explanation", hasCandidate
            ? `All supplied matching combinations were considered. Eligible options were ranked by ${preference === "lexical" ? "architecture and CDS identity" : "length, then architecture and CDS identity"}. This is a bounded structural selection.`
            : "No supplied combination was eligible under the current request. This does not establish biological infeasibility.");
        if (!alternatives.length)
            list.append(node("p", "No product binding was found in the supplied library. Check the exact authored product identity and library bindings."));
        alternatives.forEach((alternative) => {
            const card = node("div", null, `alternative${alternative.selected ? " is-selected" : ""}`);
            const heading = node("div", null, "alternative-heading");
            heading.append(node("strong", label(alternative.architecture_id)), node("span", alternative.selected ? "Selected" : alternative.rejections.length ? "Excluded" : "Eligible", "small-badge"));
            card.append(heading, node("p", `${alternative.length_nt} nt · CDS ${alternative.cds_part_id}`));
            if (alternative.rejections.length) {
                const reasons = node("ul");
                alternative.rejections.forEach((reason) => listItem(reasons, reason.message));
                card.append(reasons);
            }
            else
                card.append(node("p", alternative.selected ? "Meets structural checks and the authored constraints; first under the declared ranking." : "Meets structural checks and constraints; another option ranked first."));
            list.append(card);
        });
        byId("alternatives-details").open = !hasCandidate;
    }
    function renderResult(summary) {
        const hasCandidate = Boolean(summary.sequence);
        byId("empty-result").hidden = true;
        byId("result-content").hidden = false;
        byId("molecule-section").hidden = !hasCandidate;
        byId("sequence-section").hidden = !hasCandidate;
        byId("length-metric").hidden = !hasCandidate;
        byId("no-candidate-help").hidden = hasCandidate;
        text("result-badge", hasCandidate ? "Structure checked" : "No eligible candidate");
        byId("result-badge").className = `small-badge ${hasCandidate ? "success" : "warning"}`;
        text("outcome-eyebrow", hasCandidate ? "STRUCTURAL CANDIDATE" : "BOUNDED SEARCH COMPLETE");
        text("outcome-title", hasCandidate ? "Your RNA cassette is assembled." : "No candidate met this request.");
        text("outcome-description", hasCandidate ? "Exact supplied parts, automatically arranged and independently checked. Therapeutic behavior remains partial." : "The compiler retained each alternative and its reasons. No molecular sequence was emitted.");
        text("no-candidate-description", state.mode === "guided"
            ? "Review the reasons below. Try removing the length bound or allowing an automatic architecture, then compile again."
            : "Review the reasons below. Update the original source or library as needed, then import the complete revised request. Its settings remain unchanged here.");
        text("result-length", summary.length_nt);
        text("architecture-name", label(summary.architecture));
        text("sequence", summary.sequence || "");
        text("protein-sequence", summary.protein || "No encoded protein reported");
        renderParts(summary.parts || [], summary.length_nt || 1);
        renderChecks(summary.checks || []);
        renderAlternatives(summary.alternatives || [], hasCandidate);
        const obligations = byId("unresolved-list");
        obligations.replaceChildren();
        text("unresolved-count", summary.unresolved?.length || 0);
        (summary.unresolved || []).forEach((obligation) => {
            const item = listItem(obligations, null);
            item.append(node("strong", label(obligation.id)), node("p", obligation.description));
        });
        text("build-fingerprint", summary.build_fingerprint);
        text("completion-scope", label(summary.scope));
        text("therapeutic-status", label(summary.therapeutic_implementation));
        text("admission-status", label(summary.human_therapeutic_admission));
        text("source-summary", state.overview?.source_summary);
        text("download-status", hasCandidate ? "FASTA contains bases and scope labels. Build JSON retains chemistry, checks and unresolved requirements." : "Request and build JSON retain the checked search and its rejection reasons. FASTA requires an emitted molecule.");
        text("build-status", hasCandidate ? "Build checked. Review the result and remaining obligations." : "Search checked. Review excluded alternatives.");
    }
    async function compile(event) {
        event.preventDefault();
        if (!state.token || state.busy)
            return;
        let controls;
        if (state.mode === "guided") {
            try {
                controls = exampleControls();
            }
            catch (error) {
                showError(error);
                return;
            }
        }
        else if (!state.request)
            return;
        clearResult();
        const ticket = startOperation();
        text("compile-label", "Compiling and checking…");
        text("result-badge", "Checking");
        text("empty-title", "Building from your request…");
        text("empty-description", "Selecting eligible parts, deriving their layout and independently checking the emitted molecule.");
        text("build-status", "Preparing your request…");
        try {
            let requestRaw = state.requestRaw;
            if (controls) {
                const prepared = await api("/api/prepare", { example: controls }, ticket.controller.signal);
                if (!current(ticket))
                    return;
                state.request = prepared.request;
                requestRaw = prepared.request_json;
                state.requestRaw = requestRaw;
                showOverview(prepared.overview);
            }
            text("build-status", "Compiling and independently checking…");
            if (!requestRaw)
                throw new Error("The original request authority is missing. Prepare the request again.");
            const result = await api("/api/compile", { request_json: requestRaw }, ticket.controller.signal);
            if (!current(ticket))
                return;
            state.request = result.request;
            state.requestRaw = result.request_json;
            state.record = result.record;
            state.recordRaw = result.record_json;
            state.summary = result.summary;
            renderResult(result.summary);
            if (window.matchMedia("(max-width: 710px)").matches)
                byId("result-section").scrollIntoView({ block: "start", behavior: "auto" });
        }
        catch (error) {
            if (!current(ticket) || errorInfo(error).name === "AbortError")
                return;
            clearResult("No result was accepted. Review the message, correct your request and compile again.");
            text("result-badge", "Needs attention");
            text("build-status", "Build not accepted. Your inputs are retained.");
            showError(error);
        }
        finally {
            finish(ticket);
        }
    }
    function importedDraft() {
        state.mode = "imported";
        invalidate("The imported request changed. Validate it before compiling a fresh build.");
        text("imported-product-name", "Import awaiting validation");
        text("imported-constraints-text", "Settings will appear after validation.");
        text("cue-label", "Authored condition");
        text("response-label", "Authored response");
        text("cell-type", "Awaiting validation");
        text("target-name", "Awaiting validation");
        text("intent-source-summary", "");
        text("library-label", "The imported library is retained as authored.");
        text("context-badge", "Imported request");
        text("context-description", "Validate the complete request, then compile its unchanged source, library and constraints.");
        showMode();
    }
    async function importRequest() {
        if (state.busy || !state.token)
            return;
        importedDraft();
        let source;
        try {
            source = authorityText(byId("request-json").value);
            if (new Blob([source]).size > MAX_IMPORT_BYTES)
                throw new Error("Choose a request no larger than 1 MiB. Larger requests can use the command-line workflow.");
            JSON.parse(source); // Syntax feedback only; the original bytes go to the server.
        }
        catch (error) {
            showError(error instanceof SyntaxError ? new Error("This is not valid JSON. Check that you pasted a complete CandidateRequest object, then try again.") : error, "Import needs attention");
            return;
        }
        const ticket = startOperation();
        text("build-status", "Validating the imported request…");
        try {
            const prepared = await api("/api/prepare", { request_json: source }, ticket.controller.signal);
            if (!current(ticket))
                return;
            state.request = prepared.request;
            state.requestRaw = prepared.request_json;
            showOverview(prepared.overview);
            text("build-status", "Imported request validated. Ready to compile as authored.");
            text("empty-title", "Your request is ready.");
            text("empty-description", "Compile to inspect the exact candidate permitted by your imported source, library and constraints.");
        }
        catch (error) {
            if (!current(ticket) || errorInfo(error).name === "AbortError")
                return;
            text("build-status", "Import not accepted. Correct the JSON or return to the guided example.");
            showError(error, "Import needs attention");
        }
        finally {
            finish(ticket);
        }
    }
    async function download(format) {
        if (!state.record || state.busy)
            return;
        const request = state.request;
        const record = state.record;
        const ticket = startOperation();
        text("download-status", "Verifying the current request and build before download…");
        try {
            if (!state.requestRaw || !state.recordRaw)
                throw new Error("Original request or build authority is missing. Compile again before exporting.");
            const result = await api("/api/export", { request_json: state.requestRaw, record_json: state.recordRaw, format }, ticket.controller.signal);
            if (!current(ticket) || state.record !== record || state.request !== request)
                return;
            const blob = new Blob([result.content], { type: result.mime_type });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = String(result.filename).split(/[\\/]/).pop() || "biocompiler-export";
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            text("download-status", `Verified ${format === "fasta" ? "RNA FASTA" : format + " JSON"} downloaded.`);
        }
        catch (error) {
            if (!current(ticket) || errorInfo(error).name === "AbortError")
                return;
            text("download-status", "Download withheld because fresh verification did not complete.");
            showError(error, "Export was not verified");
        }
        finally {
            finish(ticket);
        }
    }
    byId("build-form").addEventListener("submit", compile);
    byId("build-form").addEventListener("input", () => {
        if (state.mode !== "guided")
            return;
        byId("max-length").setCustomValidity("");
        invalidate("Your inputs changed. Compile again to get a result for the current request.");
        text("response-label", `Secrete ${guidedProductName()}`);
        text("intent-source-summary", "The guided example requests secretion when its cue is high. Sensing, control and secretion remain unimplemented.");
    });
    byId("request-json").addEventListener("input", importedDraft);
    byId("request-file").addEventListener("change", async () => {
        const file = byId("request-file").files?.[0];
        if (!file)
            return;
        byId("request-json").value = "";
        importedDraft();
        const revision = state.revision;
        try {
            if (file.size > MAX_IMPORT_BYTES)
                throw new Error("Choose a request no larger than 1 MiB. Larger requests can use the command-line workflow.");
            const source = await file.text();
            if (revision !== state.revision)
                return;
            byId("request-json").value = source;
            syncControls();
            await importRequest();
        }
        catch (error) {
            if (revision === state.revision)
                showError(error, "Could not read the request file");
        }
    });
    byId("import-button").addEventListener("click", importRequest);
    byId("example-button").addEventListener("click", () => {
        if (!state.example)
            return;
        state.mode = "guided";
        invalidate("The guided example is ready. Compile to build a fresh candidate.");
        populateProducts(state.example.overview);
        const automatic = document.querySelector('input[name="architecture"][value="auto"]');
        if (!automatic)
            throw new Error("The automatic architecture option is missing.");
        automatic.checked = true;
        byId("max-length").value = "";
        byId("max-length").setCustomValidity("");
        byId("request-json").value = "";
        byId("request-file").value = "";
        showOverview(state.example.overview);
        text("build-status", "Ready to compile the artificial example.");
        syncControls();
    });
    byId("dismiss-error").addEventListener("click", hideError);
    exports.forEach((button) => button.addEventListener("click", () => download(exportFormat(button.dataset.export))));
    byId("copy-sequence").addEventListener("click", async () => {
        if (!state.summary?.sequence || state.busy)
            return;
        const revision = state.revision;
        try {
            if (!navigator.clipboard)
                throw new Error("Clipboard access is unavailable. Select the sequence text to copy it, or download verified FASTA.");
            await navigator.clipboard.writeText(state.summary.sequence);
            if (revision === state.revision)
                text("copy-sequence", "Copied");
        }
        catch (error) {
            if (revision === state.revision)
                showError(error, "Could not copy the sequence");
        }
    });
    async function initialize() {
        try {
            const result = await api("/api/session");
            state.token = result.token;
            state.example = result.example;
            state.request = result.example.request;
            state.requestRaw = result.example.request_json;
            text("app-version", result.version);
            populateProducts(result.example.overview);
            showOverview(result.example.overview);
            text("build-status", "Ready to compile the artificial example.");
            byId("connection-message").hidden = true;
            syncControls();
        }
        catch (error) {
            text("connection-message", "The local compiler could not connect. Keep the server running and reload this page to retry.");
            showError(error, "Studio could not connect");
        }
    }
    initialize();
})();
