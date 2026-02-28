function stripQuotes(value = "") {
  const text = String(value || "").trim();
  if ((text.startsWith('"') && text.endsWith('"')) || (text.startsWith("'") && text.endsWith("'"))) {
    return text.slice(1, -1).trim();
  }
  return text;
}

function parseFenceDescriptor(descriptor = "") {
  const text = String(descriptor || "").trim();
  if (!text) return null;

  const byColon = text.match(/^([^\s:]+):(.+)$/);
  if (byColon) {
    const language = byColon[1].trim();
    const filename = stripQuotes(byColon[2]);
    if (!filename) return null;
    return { language, filename };
  }

  const byFilenameWithLang = text.match(/^([^\s]+)\s+filename\s*=\s*(.+)$/i);
  if (byFilenameWithLang) {
    const language = byFilenameWithLang[1].trim();
    const filename = stripQuotes(byFilenameWithLang[2]);
    if (!filename) return null;
    return { language, filename };
  }

  const byFilenameOnly = text.match(/^filename\s*=\s*(.+)$/i);
  if (byFilenameOnly) {
    const filename = stripQuotes(byFilenameOnly[1]);
    if (!filename) return null;
    return { language: "", filename };
  }

  return null;
}

export function createStreamingArtifactParser() {
  let pendingLine = "";
  let activeArtifact = null;

  const processLine = (line, hasNewline, events) => {
    const normalized = String(line || "");

    if (!activeArtifact) {
      const fenceMatch = normalized.match(/^\s*```(.*)$/);
      if (!fenceMatch) return;

      const descriptor = parseFenceDescriptor(fenceMatch[1] || "");
      if (!descriptor) return;

      activeArtifact = {
        filename: descriptor.filename,
        language: descriptor.language,
        rawFenceLine: normalized.trim(),
        content: "",
      };
      events.push({
        type: "artifact_open",
        filename: activeArtifact.filename,
        language: activeArtifact.language,
        rawFenceLine: activeArtifact.rawFenceLine,
      });
      return;
    }

    if (normalized.trim() === "```") {
      events.push({
        type: "artifact_complete",
        filename: activeArtifact.filename,
        language: activeArtifact.language,
        content: activeArtifact.content,
      });
      activeArtifact = null;
      return;
    }

    const chunk = hasNewline ? `${normalized}\n` : normalized;
    if (!chunk) return;
    activeArtifact.content += chunk;
    events.push({
      type: "artifact_chunk",
      filename: activeArtifact.filename,
      appendedText: chunk,
    });
  };

  return {
    feed(deltaText = "") {
      const events = [];
      pendingLine += String(deltaText || "");

      let newlineIndex = pendingLine.indexOf("\n");
      while (newlineIndex >= 0) {
        const line = pendingLine.slice(0, newlineIndex);
        processLine(line, true, events);
        pendingLine = pendingLine.slice(newlineIndex + 1);
        newlineIndex = pendingLine.indexOf("\n");
      }

      return events;
    },
    finalize() {
      const events = [];
      if (!activeArtifact) {
        pendingLine = "";
        return events;
      }

      if (pendingLine) {
        activeArtifact.content += pendingLine;
        events.push({
          type: "artifact_chunk",
          filename: activeArtifact.filename,
          appendedText: pendingLine,
        });
        pendingLine = "";
      }

      events.push({
        type: "artifact_complete",
        filename: activeArtifact.filename,
        language: activeArtifact.language,
        content: activeArtifact.content,
      });
      activeArtifact = null;
      return events;
    },
    reset() {
      pendingLine = "";
      activeArtifact = null;
    },
  };
}
