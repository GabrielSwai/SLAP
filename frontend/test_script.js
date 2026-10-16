// =====================================================================================
// Surrogate Language Alignment Program
// Verify desktop saving and browser download state without a graphical backend.
// =====================================================================================

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// Function:     createContext
// Inputs:       desktop | whether native saving is enabled (boolean)
// Outputs:      context | isolated DOM and desktop bridge doubles (object)
// Description:  Loads the browser workflow without modifying application code.

function createContext(desktop) {
    const elements = new Map();
    const element = () => ({
        disabled: false, options: [{}, {}], dataset: {url: "/download/RUN_ID"},
        classList: {toggle() {}}, setAttribute() {}, addEventListener() {},
        replaceChildren(...options) {this.options = options;}, append(item) {this.options.push(item);},
        add(option) {this.options.push(option);}, click() {}, remove() {},
    });
    const context = vm.createContext({
        document: {
            querySelector(selector) {
                if (!elements.has(selector)) elements.set(selector, element());
                return elements.get(selector);
            },
            createElement: element,
            body: {dataset: {desktop: String(desktop), cleanupUrl: "/runs/RUN_ID/delete"}, append() {}},
        },
        window: {pywebview: {api: {save_output: async () => ({saved: true})}}},
        Option: function (text, value) {this.value = value;},
        URL: {createObjectURL() {return "blob:output";}, revokeObjectURL() {}},
        setTimeout(callback) {callback();},
        fetch: async () => ({ok: true, blob: async () => ({})}),
    });
    vm.runInContext(fs.readFileSync(`${__dirname}/static/script.js`, "utf8"), context);
    vm.runInContext('runId = "surrogate-aligner-test"; outputReady = true;', context);
    return {context, elements};
}

// Function:     main
// Inputs:       None
// Outputs:      None
// Description:  Checks success, cancellation, failures, and the browser fallback.

async function main() {
    for (const result of [{cancelled: true}, {error: "Folder is read-only"}, {saved: true}]) {
        const {context, elements} = createContext(true);
        context.fetch = async () => {throw new Error("Native saves must not consume the HTTP download");};
        context.window.pywebview.api.save_output = async () => result;
        await vm.runInContext("downloadOutput()", context);
        assert.equal(vm.runInContext("runId", context), result.saved ? null : "surrogate-aligner-test");
        assert.equal(elements.get("#download").disabled, Boolean(result.saved));
        if (result.error) assert.equal(elements.get("#status").textContent, result.error);
    }
    const missingBridge = createContext(true);
    delete missingBridge.context.window.pywebview;
    await vm.runInContext("downloadOutput()", missingBridge.context);
    assert.equal(vm.runInContext("outputReady", missingBridge.context), true);
    assert.match(missingBridge.elements.get("#status").textContent, /not ready/);

    const browser = createContext(false);
    browser.context.window.pywebview.api.save_output = async () => {throw new Error("Browser must not use native saving");};
    await vm.runInContext("downloadOutput()", browser.context);
    assert.equal(vm.runInContext("runId", browser.context), null);
    assert.equal(browser.elements.get("#download").disabled, true);

    // Partial output must list counts and the exact interval omitted from the export.
    const partial = createContext(false);
    const payload = {total_count: 2, processed_count: 1, skipped_count: 1,
        skipped_segments: [{start: .5, end: 1, label: "a", reason: "No note onsets detected."}]};
    partial.context.payload = payload;
    vm.runInContext("showSummary(payload)", partial.context);
    assert.equal(partial.elements.get("#analysis-summary").hidden, false);
    assert.match(partial.elements.get("#analysis-counts").textContent, /1 of 2 phrases aligned; 1 skipped/);
    assert.match(partial.elements.get("#skipped-phrases").options[0].textContent, /0.500–1.000 s/);
    vm.runInContext("resetResults()", partial.context);
    assert.equal(partial.elements.get("#analysis-summary").hidden, true);
    console.log("Desktop save states and browser downloads passed.");
}

main().catch(error => {console.error(error); process.exitCode = 1;});
