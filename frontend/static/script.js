// =====================================================================================
// Surrogate Language Aligner
// Connect the frontend controls to the local Flask routes.
// =====================================================================================

const uploadForm = document.querySelector("#upload-form");
const inputTier = document.querySelector("#input-tier");
const defaultTone = document.querySelector("#default-tone");
const parseForm = document.querySelector("#parse-form");
const detectForm = document.querySelector("#detect-form");
const detectionFields = document.querySelector("#detection-fields");
const uploadFields = document.querySelector("#upload-fields");
const processingFields = document.querySelector("#processing-fields");
const downloadButton = document.querySelector("#download");
const status = document.querySelector("#status");
let tonesReady = false;
let runId = null;
let outputReady = false;

// Function:     setBusy
// Inputs:       busy | whether a request is running (boolean)
// Outputs:      None
// Description:  Prevents overlapping requests and enables available actions.

function setBusy(busy) {
    uploadFields.disabled = busy;
    processingFields.disabled = busy || !runId || inputTier.options.length < 2;
    detectionFields.disabled = busy || !runId || !tonesReady;
    downloadButton.disabled = busy || !outputReady;

    // Expose processing activity to assistive technology
    document.querySelector("#workspace").setAttribute("aria-busy", String(busy));
}

// Function:     showStatus
// Inputs:       message | status text (string)
//               isError | whether the request failed (boolean)
// Outputs:      None
// Description:  Displays feedback without inserting HTML.

function showStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle("error", isError);
}

// Function:     resetResults
// Inputs:       None
// Outputs:      None
// Description:  Resets processing progress when the input changes.

function resetResults() {
    outputReady = false;
    tonesReady = false;
    document.querySelector("#analysis-summary").hidden = true;
    document.querySelector("#skipped-phrases").replaceChildren();
}

// Function:     showSummary
// Inputs:       payload | phrase counts and skipped intervals from detection (object)
// Outputs:      None
// Description:  Makes partial alignments and omitted phrases explicit before export.

function showSummary(payload) {
    if (!Number.isInteger(payload.total_count)) return;
    document.querySelector("#analysis-summary").hidden = false;
    document.querySelector("#analysis-counts").textContent =
        `${payload.processed_count} of ${payload.total_count} phrases aligned; ${payload.skipped_count} skipped.`;
    const list = document.querySelector("#skipped-phrases");
    list.replaceChildren();
    for (const segment of payload.skipped_segments || []) {
        const item = document.createElement("li");
        item.textContent = `${segment.start.toFixed(3)}–${segment.end.toFixed(3)} s: ${segment.label || "(empty annotation)"} — ${segment.reason}`;
        list.append(item);
    }
}

// Function:     populateTiers
// Inputs:       tiers | tier names from the uploaded ELAN file (array)
// Outputs:      None
// Description:  Replaces annotation tier choices with the uploaded file's tiers.

function populateTiers(tiers = []) {
    inputTier.replaceChildren(new Option(
        tiers.length ? "Select an annotation tier" : "No annotation tiers available", ""
    ));
    for (const tier of tiers) {
        inputTier.add(new Option(tier, tier));
    }
}

// Function:     submitForm
// Inputs:       form | submitted form (HTMLFormElement)
//               message | progress message (string)
// Outputs:      None
// Description:  Submits inputs and displays results or backend errors.

async function submitForm(form, message) {
    const data = new FormData(form);
    if (form === uploadForm) {
        runId = null;
        resetResults();
        populateTiers();
    } else {
        data.set("run_id", runId);
        data.set("input_tier", inputTier.value);
        data.set("default_tone", defaultTone.value);
        outputReady = false;
        document.querySelector("#analysis-summary").hidden = true;
        document.querySelector("#skipped-phrases").replaceChildren();
        if (form === parseForm) resetResults();
    }
    setBusy(true);
    showStatus(message);

    try {
        const response = await fetch(form.action, { method: "POST", body: data });
        const payload = await response.json();
        if (form === detectForm) showSummary(payload);
        if (!response.ok) throw new Error(payload.error || "The request failed.");

        // Expected upload response: {run_id: "...", tiers: ["..."]}.
        // Detection must explicitly confirm that an output file is ready.
        if (form === uploadForm) {
            if (!payload.run_id) throw new Error("The server did not return a run ID.");
            runId = String(payload.run_id);
            populateTiers(payload.tiers || []);
            showStatus(inputTier.options.length > 1
                ? "Files uploaded. Select an annotation tier and parse tones."
                : "The uploaded ELAN file has no annotation tiers.", inputTier.options.length < 2);
        } else if (form === parseForm) {
            tonesReady = payload.segments?.some(segment => segment.word_sequence?.length > 0);
            showStatus(tonesReady
                ? "Tones parsed. Detect note boundaries next."
                : "The selected tier has no annotations.");
        } else {
            outputReady = payload.output_ready === true;
            showStatus(outputReady
                ? payload.skipped_count > 0
                    ? "Partial alignment ready. Review the skipped phrases below before downloading."
                    : "Alignment complete. Your ELAN file is ready to download."
                : "Note boundaries detected. The ELAN output is not ready yet.");
        }
    } catch (error) {
        showStatus(error.message || "Could not reach the local server.", true);
    } finally {
        setBusy(false);
    }
}

// Reset the run when different input files are selected.
uploadForm.addEventListener("change", () => {
    // Release the abandoned upload without blocking selection of replacement files.
    if (runId) {
        const url = document.body.dataset.cleanupUrl.replace("RUN_ID", encodeURIComponent(runId));
        fetch(url, {method: "POST", keepalive: true}).catch(() => {});
    }
    runId = null;
    resetResults();
    populateTiers();
    setBusy(false);
    showStatus("Upload the selected files to begin.");
});

uploadForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitForm(uploadForm, "Uploading files…");
});

// Invalidate previous results when the selected annotation tier changes.
inputTier.addEventListener("change", () => {
    resetResults();
    setBusy(false);
});

// Invalidate previous results when the default tone changes.
defaultTone.addEventListener("change", () => {
    resetResults();
    setBusy(false);
});

parseForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!inputTier.value) {
        showStatus("Select an input annotation tier.", true);
        return;
    }
    submitForm(parseForm, "Parsing tones…");
});

// Submit the recording for note boundary detection after parsing tones.
detectForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!tonesReady) return;
    submitForm(detectForm, "Detecting note boundaries…");
});

// Function:     downloadOutput
// Inputs:       None
// Outputs:      None
// Description:  Downloads the generated EAF file and reports server errors.

async function downloadOutput() {
    if (!runId || !outputReady) return;
    setBusy(true);
    showStatus("Downloading output…");
    try {
        if (document.body.dataset.desktop === "true") {
            // Save natively without consuming the download on cancellation or failure.
            if (!window.pywebview?.api?.save_output) {
                throw new Error("The desktop connection is not ready. Try saving again.");
            }
            const result = await window.pywebview.api.save_output(runId);
            if (result.cancelled) {
                showStatus("Save cancelled. Your alignment is still ready to download.");
                return;
            }
            if (!result.saved) throw new Error(result.error || "Could not save the output.");
        } else {
            const url = downloadButton.dataset.url.replace("RUN_ID", encodeURIComponent(runId));
            const response = await fetch(url);
            if (!response.ok) {
                const payload = await response.json();
                throw new Error(payload.error || "Download failed.");
            }
            const objectUrl = URL.createObjectURL(await response.blob());
            const link = document.createElement("a");
            link.href = objectUrl;
            link.download = "aligned_output.eaf";
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        }
        // The completed run is removed only after download or native saving succeeds.
        runId = null;
        resetResults();
        populateTiers();
        showStatus("Output saved. Upload files to start another alignment.");
    } catch (error) {
        showStatus(error.message || "Could not download the output.", true);
    } finally {
        setBusy(false);
    }
}

downloadButton.addEventListener("click", downloadOutput);
