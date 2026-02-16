const fs = require("fs");
const crypto = require("crypto");

module.exports = async ({ github, context, core }) => {
  const owner = context.repo.owner;
  const repo = context.repo.repo;
  const issue_number = context.issue.number;

  if (!issue_number) {
    core.warning("No pull request context. Skipping comment publish.");
    return;
  }

  if (!fs.existsSync("result.json")) {
    core.warning("result.json not found. Skipping comment publish.");
    return;
  }

  let result;
  try {
    result = JSON.parse(fs.readFileSync("result.json", "utf8"));
  } catch (error) {
    core.warning(`Failed to parse result.json: ${error.message}`);
    return;
  }

  const issues = Array.isArray(result.issues) ? result.issues : [];
  const summary = String(result.summary || "").trim();
  const decision = String(result.decision || "WARN").toUpperCase();
  const stats =
    result.stats && typeof result.stats === "object" ? result.stats : {};
  const riskScore = stats.risk_score ?? "n/a";

  const summaryMarker = "<!-- ai-review:summary -->";
  const issueMarkerPrefix = "<!-- ai-review:item:";
  const keysMarkerPrefix = "<!-- ai-review:keys:";

  const toPositiveInt = (raw, fallback) => {
    const n = Number.parseInt(raw, 10);
    return Number.isFinite(n) && n >= 0 ? n : fallback;
  };

  const limits = {
    maxSummaryItems: toPositiveInt(process.env.AI_REVIEW_MAX_SUMMARY_ITEMS, 20),
    maxMessageChars: toPositiveInt(process.env.AI_REVIEW_MAX_MESSAGE_CHARS, 220),
    maxSuggestionChars: toPositiveInt(
      process.env.AI_REVIEW_MAX_SUGGESTION_CHARS,
      160
    ),
  };

  const severityOrder = {
    BLOCKER: 0,
    IMPORTANT: 1,
    CRITICAL: 2,
    HIGH: 3,
    MEDIUM: 4,
    LOW: 5,
    WARNING: 6,
    QUESTION: 7,
    NIT: 8,
  };

  const criticalSet = new Set(["BLOCKER", "IMPORTANT", "CRITICAL", "HIGH"]);

  const normalizeSeverity = (value) => {
    const severity = String(value || "NIT").trim().toUpperCase();
    return severity || "NIT";
  };

  const confidenceValue = (issue) =>
    typeof issue.confidence === "number" && Number.isFinite(issue.confidence)
      ? issue.confidence
      : -1;

  const truncate = (value, maxChars) => {
    const text = String(value || "")
      .replace(/\s+/g, " ")
      .trim();
    if (!text) {
      return "";
    }
    if (text.length <= maxChars) {
      return text;
    }
    const head = Math.max(0, maxChars - 3);
    return `${text.slice(0, head).trimEnd()}...`;
  };

  const issueLocation = (issue) => {
    const path = issue.path || "unknown";
    const lineStart = issue.line_start ?? "?";
    const lineEnd = issue.line_end ?? lineStart;
    return `${path}:${lineStart}-${lineEnd}`;
  };

  const toIssueKey = (issue) => {
    const source = issue.fingerprint
      ? `fingerprint:${issue.fingerprint}`
      : issue.id != null && issue.id !== ""
        ? `id:${issue.id}:${issue.path || "unknown"}:${issue.line_start || "?"}`
        : `loc:${issue.path || "unknown"}:${issue.line_start || "?"}:${issue.title || "Issue"}`;
    return crypto
      .createHash("sha1")
      .update(String(source))
      .digest("hex")
      .slice(0, 16);
  };

  const compareEntries = (a, b) => {
    const rankA = severityOrder[a.severity] ?? 99;
    const rankB = severityOrder[b.severity] ?? 99;
    if (rankA !== rankB) {
      return rankA - rankB;
    }
    const confidenceDelta = confidenceValue(b.issue) - confidenceValue(a.issue);
    if (confidenceDelta !== 0) {
      return confidenceDelta;
    }
    const pathA = String(a.issue.path || "");
    const pathB = String(b.issue.path || "");
    if (pathA !== pathB) {
      return pathA.localeCompare(pathB);
    }
    return (a.issue.line_start ?? 0) - (b.issue.line_start ?? 0);
  };

  const formatIssueLine = (entry, includeSuggestion = false) => {
    const issue = entry.issue;
    const title = issue.title || "Issue";
    const location = issueLocation(issue);
    const message = truncate(issue.message, limits.maxMessageChars);
    const suggestion = truncate(issue.suggestion, limits.maxSuggestionChars);

    let line = `- [${entry.severity}] ${title} (\`${location}\`)`;
    if (message) {
      line += `: ${message}`;
    }
    if (includeSuggestion && suggestion) {
      line += ` | fix: ${suggestion}`;
    }
    return line;
  };

  const parseKeysMarker = (body) => {
    const text = String(body || "");
    const match = text.match(/<!-- ai-review:keys:([a-f0-9,]*) -->/);
    if (!match || !match[1]) {
      return new Set();
    }
    return new Set(match[1].split(",").filter(Boolean));
  };

  const uniqueByKey = new Map();
  for (const issue of issues) {
    const key = toIssueKey(issue);
    if (!uniqueByKey.has(key)) {
      uniqueByKey.set(key, issue);
    }
  }

  const issueEntries = Array.from(uniqueByKey.entries())
    .map(([key, issue]) => ({
      key,
      issue,
      severity: normalizeSeverity(issue.severity),
    }))
    .sort(compareEntries);

  const existingComments = await github.paginate(github.rest.issues.listComments, {
    owner,
    repo,
    issue_number,
    per_page: 100,
  });

  const summaryComments = existingComments
    .filter((c) => (c.body || "").includes(summaryMarker))
    .sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  const previousSummary = summaryComments[0];
  const previousKeys = parseKeysMarker(previousSummary ? previousSummary.body : "");
  const currentKeys = new Set(issueEntries.map((entry) => entry.key));
  const newKeys = issueEntries
    .filter((entry) => !previousKeys.has(entry.key))
    .map((entry) => entry.key);
  const resolvedKeys = Array.from(previousKeys).filter(
    (key) => !currentKeys.has(key)
  );
  const unchangedCount = currentKeys.size - newKeys.length;
  const newKeySet = new Set(newKeys);

  const severityCounts = new Map();
  for (const entry of issueEntries) {
    const current = severityCounts.get(entry.severity) || 0;
    severityCounts.set(entry.severity, current + 1);
  }
  const severityBreakdown = Array.from(severityCounts.entries())
    .sort((a, b) => (severityOrder[a[0]] ?? 99) - (severityOrder[b[0]] ?? 99))
    .map(([severity, count]) => `${severity}: ${count}`)
    .join(" | ");

  const criticalNow = issueEntries.filter((entry) =>
    criticalSet.has(entry.severity)
  );
  const criticalNew = issueEntries.filter(
    (entry) => newKeySet.has(entry.key) && criticalSet.has(entry.severity)
  );
  const compactList = issueEntries.slice(0, limits.maxSummaryItems);
  const hiddenCount = Math.max(0, issueEntries.length - compactList.length);
  const keysMarker = `${keysMarkerPrefix}${issueEntries.map((entry) => entry.key).join(",")} -->`;

  const formatSummaryBody = () => {
    const topLine = "### Ai review";
    const statusLine = `**Decision**: ${decision} | **Risk score**: ${riskScore}`;
    const countLine = issueEntries.length
      ? `**Issues**: ${issueEntries.length} (${severityBreakdown})`
      : "**Issues**: 0";
    const deltaLine = `**Delta vs previous run**: +${newKeys.length} new | -${resolvedKeys.length} resolved | ${unchangedCount} unchanged`;
    const summaryText = summary || "No summary provided.";

    const criticalNowSection = criticalNow.length
      ? [
        "#### Critical now (top 5)",
        ...criticalNow.slice(0, 5).map((entry) => formatIssueLine(entry, true)),
      ].join("\n")
      : "#### Critical now\nNo critical issues detected.";

    const criticalNewSection = criticalNew.length
      ? [
        "#### New critical since last run",
        ...criticalNew.slice(0, 5).map((entry) => formatIssueLine(entry, false)),
      ].join("\n")
      : "#### New critical since last run\nNone.";

    const compactSection = issueEntries.length
      ? [
        "<details>",
        `<summary>All issues (compact, showing ${compactList.length}/${issueEntries.length})</summary>`,
        "",
        ...compactList.map((entry) => formatIssueLine(entry, false)),
        hiddenCount > 0 ? `- ... and ${hiddenCount} more.` : "",
        "</details>",
      ]
        .filter(Boolean)
        .join("\n")
      : "";

    return [
      summaryMarker,
      topLine,
      "",
      statusLine,
      countLine,
      deltaLine,
      "",
      summaryText,
      "",
      criticalNowSection,
      "",
      criticalNewSection,
      "",
      compactSection,
      keysMarker,
    ]
      .join("\n")
      .replace(/\n{3,}/g, "\n\n");
  };

  const summaryBody = formatSummaryBody();
  const managedComments = existingComments.filter((comment) => {
    const body = comment.body || "";
    return body.includes(summaryMarker) || body.includes(issueMarkerPrefix);
  });

  for (const comment of managedComments) {
    await github.rest.issues.deleteComment({
      owner,
      repo,
      comment_id: comment.id,
    });
  }

  await github.rest.issues.createComment({
    owner,
    repo,
    issue_number,
    body: summaryBody,
  });

  core.info(
    `Published Ai review: total issues=${issueEntries.length}, replaced comments=${managedComments.length}.`
  );
};
