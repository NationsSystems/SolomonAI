// -------------------------------------------------------------------
// FILE: webui/static/js/ui/ui.text.js
// -------------------------------------------------------------------

window.SolomonText = {
    normalize(text) {
        if (!text) return "";
        let t = String(text).replace(/\r\n/g, "\n");
        t = t.replace(/\n{3,}/g, "\n\n");
        return t.trim();
    }
};