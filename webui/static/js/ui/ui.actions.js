// -------------------------------------------------------------------
// FILE: webui/static/js/ui/ui.actions.js
// -------------------------------------------------------------------

window.SolomonActions = {

    createActionBar() {
        const bar = document.createElement("div");
        bar.className = "bei-actions";

        bar.appendChild(this.createButton("Print", () => window.print()));
        bar.appendChild(this.createButton("Copy", this.copy));
        bar.appendChild(this.createButton("Download", this.download));

        return bar;
    },

    createButton(label, handler) {
        const btn = document.createElement("button");
        btn.className = "bei-btn";
        btn.innerText = label;
        btn.onclick = handler;
        return btn;
    },

    copy() {
        const text = window.SolomonRender._lastCopyText || "";
        navigator.clipboard.writeText(text);
    },

    download() {
        const text = window.SolomonRender._lastCopyText || "";
        const blob = new Blob([text], { type: "text/plain" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "bei_report.txt";
        a.click();
    }
};