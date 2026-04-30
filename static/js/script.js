const h = React.createElement;
const { useEffect, useMemo, useRef, useState } = React;
const TOKEN_KEY = "frametruth_access_token";

function percent(value) {
    return `${(Number(value) * 100).toFixed(2)}%`;
}

function seconds(value) {
    return `${Number(value).toFixed(2)}s`;
}

function Toast({ toast }) {
    return toast.message ? h("div", { className: `toast show ${toast.tone}` }, toast.message) : null;
}

function getAuthHeaders() {
    const token = window.localStorage.getItem(TOKEN_KEY);
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function TopNav({ user, onAuthClick, onLogout }) {
    return h("header", { className: "top-nav" },
        h("a", { className: "brand", href: "#" },
            h("span", { className: "brand-mark" }, "FT"),
            h("span", null, "FRAMETRUTH AI")
        ),
        h("nav", { className: "nav-links", "aria-label": "Primary navigation" },
            h("a", { className: "nav-item active", href: "#" }, "Deepfake"),
            h("a", { className: "nav-item", href: "#timeline-panel" }, "Timeline"),
            h("a", { className: "nav-item", href: "#metrics-panel" }, "Metrics"),
            h("a", { className: "nav-item", href: "#admin-panel" }, "Admin"),
            h("a", { className: "nav-item", href: "#xai-panel" }, "XAI")
        ),
        h("div", { className: "nav-actions" },
            user
                ? [
                    h("span", { className: "user-chip", key: "user" }, user.name),
                    h("button", { className: "ghost-button", type: "button", onClick: onLogout, key: "logout" }, "Logout"),
                ]
                : h("button", { className: "ghost-button", type: "button", onClick: onAuthClick }, "Sign in")
        )
    );
}

function AuthModal({ mode, setMode, onClose, onAuthed, showToast }) {
    const [form, setForm] = useState({ name: "", email: "", password: "" });
    const [loading, setLoading] = useState(false);
    const isSignup = mode === "signup";

    function updateField(event) {
        setForm({ ...form, [event.target.name]: event.target.value });
    }

    async function submit(event) {
        event.preventDefault();
        setLoading(true);
        try {
            const response = await fetch(isSignup ? "/api/auth/signup" : "/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form),
            });
            const data = await response.json();
            if (!response.ok || data.error) {
                throw new Error(data.error || "Authentication failed.");
            }
            window.localStorage.setItem(TOKEN_KEY, data.access_token);
            onAuthed(data.user);
            showToast(isSignup ? "Account created." : "Signed in.", "success");
            onClose();
        } catch (error) {
            showToast(error.message, "error");
        } finally {
            setLoading(false);
        }
    }

    return h("div", { className: "modal-backdrop", role: "dialog", "aria-modal": "true" },
        h("div", { className: "auth-modal" },
            h("div", { className: "modal-heading" },
                h("div", null,
                    h("p", { className: "eyebrow" }, "Secure access"),
                    h("h2", null, isSignup ? "Create account" : "Sign in")
                ),
                h("button", { className: "icon-button", type: "button", onClick: onClose, "aria-label": "Close" }, "x")
            ),
            h("form", { className: "auth-form", onSubmit: submit },
                isSignup && h("label", null, "Name",
                    h("input", { name: "name", value: form.name, onChange: updateField, autoComplete: "name", required: true })
                ),
                h("label", null, "Email",
                    h("input", { name: "email", type: "email", value: form.email, onChange: updateField, autoComplete: "email", required: true })
                ),
                h("label", null, "Password",
                    h("input", {
                        name: "password",
                        type: "password",
                        value: form.password,
                        onChange: updateField,
                        autoComplete: isSignup ? "new-password" : "current-password",
                        required: true,
                        minLength: 8,
                    })
                ),
                h("button", { className: "primary-button", type: "submit", disabled: loading },
                    loading ? "Please wait..." : isSignup ? "Create account" : "Sign in"
                )
            ),
            h("button", { className: "link-button", type: "button", onClick: () => setMode(isSignup ? "login" : "signup") },
                isSignup ? "Already have an account? Sign in" : "New here? Create an account"
            )
        )
    );
}

function SourcePanel({ user, onResult, showToast, openAuth }) {
    const [file, setFile] = useState(null);
    const [url, setUrl] = useState("");
    const [loading, setLoading] = useState(false);

    async function pollForResult(jobId) {
        for (let attempt = 0; attempt < 90; attempt += 1) {
            const statusResponse = await fetch(`/api/v1/status/${jobId}`, { headers: getAuthHeaders() });
            const statusPayload = await statusResponse.json();
            if (!statusResponse.ok || statusPayload.status === "error") {
                throw new Error(statusPayload.error || "Could not read job status.");
            }
            if (statusPayload.data.status === "failed") {
                throw new Error(statusPayload.data.error || "Analysis failed.");
            }
            if (statusPayload.data.status === "complete") {
                const resultResponse = await fetch(`/api/v1/result/${jobId}`, { headers: getAuthHeaders() });
                const resultPayload = await resultResponse.json();
                if (!resultResponse.ok || resultPayload.status === "error") {
                    throw new Error(resultPayload.error || "Could not read job result.");
                }
                return resultPayload.data;
            }
            await new Promise(resolve => window.setTimeout(resolve, 1200));
        }
        throw new Error("Analysis is taking longer than expected. Try the status endpoint again.");
    }

    async function submit(event) {
        event.preventDefault();
        if (!user) {
            openAuth("login");
            showToast("Sign in before running an analysis.", "error");
            return;
        }
        if (!file && !url.trim()) {
            showToast("Upload a video or paste a URL first.", "error");
            return;
        }

        const formData = new FormData();
        if (file) {
            formData.append("video", file);
        } else {
            formData.append("url", url.trim());
        }

        setLoading(true);
        try {
            const response = await fetch("/api/v1/analyze", { method: "POST", body: formData, headers: getAuthHeaders() });
            const payload = await response.json();
            if (!response.ok || payload.status === "error") {
                throw new Error(payload.error || "Analysis failed.");
            }
            showToast(`Job queued: ${payload.data.job_id.slice(0, 8)}`, "success");
            const result = await pollForResult(payload.data.job_id);
            onResult(result);
            showToast(`Analysis complete. Request ${result.request_id.slice(0, 8)}`, "success");
        } catch (error) {
            showToast(error.message, "error");
        } finally {
            setLoading(false);
        }
    }

    return h("form", { className: "panel source-panel", onSubmit: submit },
        h("div", { className: "panel-heading" },
            h("span", { className: "step" }, "1"),
            h("div", null, h("h2", null, "Source Video"), h("p", null, "Upload a file or paste a public URL."))
        ),
        h("label", { className: "drop-zone" },
            h("input", {
                type: "file",
                accept: ".mp4,.mov",
                onChange: event => {
                    const nextFile = event.target.files[0] || null;
                    setFile(nextFile);
                    if (nextFile) setUrl("");
                },
            }),
            h("span", { className: "upload-orb" }, "+"),
            h("strong", null, file ? file.name : "Drop file here or browse"),
            h("small", null, "Supported: mp4, mov")
        ),
        h("div", { className: "url-row" },
            h("input", {
                type: "url",
                value: url,
                onChange: event => {
                    setUrl(event.target.value);
                    if (event.target.value.trim()) setFile(null);
                },
                placeholder: "https://youtube.com/watch?v=...",
            }),
            h("button", { className: "ghost-button", type: "button", onClick: () => { setFile(null); setUrl(""); } }, "Clear")
        ),
        h("button", { className: "primary-button run-button", type: "submit", disabled: loading },
            loading ? "Analyzing..." : "Run analysis"
        )
    );
}

function PreviewPanel({ result }) {
    const frames = result?.artifacts?.top_suspicious_frames || [];
    const verdict = result?.verdict;
    return h("section", { className: "panel preview-panel" },
        h("div", { className: "panel-heading" },
            h("span", { className: "step" }, "2"),
            h("div", null, h("h2", null, "Preview"), h("p", null, "Most suspicious sampled frames."))
        ),
        h("div", { className: "frame-strip" },
            frames.length ? frames.map(frame => h("figure", { className: "frame-card", key: `${frame.rank}-${frame.frame_number}` },
                h("img", { src: frame.image_url, alt: `Suspicious frame ${frame.frame_number}` }),
                h("figcaption", null,
                    h("strong", null, percent(frame.score)),
                    h("span", null, `Frame ${frame.frame_number} at ${seconds(frame.timestamp_seconds)}`)
                )
            )) : h("div", { className: "empty-preview" }, "Run an analysis to reveal suspicious frames.")
        ),
        h("div", { className: "verdict-card" },
            h("span", { className: `badge ${verdict?.tone || "neutral"}` }, verdict?.label || "Waiting"),
            h("strong", null, result ? `${result.deepfake_percentage} fake probability` : "Deepfake probability will appear here."),
            h("p", null, verdict?.explanation || "The model analyzes sampled frames and keeps every score for review.")
        )
    );
}

function TimelinePanel({ result }) {
    const canvasRef = useRef(null);
    const chartRef = useRef(null);
    const frameScores = useMemo(() => result?.frame_scores || [], [result]);

    useEffect(() => {
        if (!canvasRef.current || !frameScores.length) return undefined;
        chartRef.current?.destroy();
        chartRef.current = new Chart(canvasRef.current, {
            type: "line",
            data: {
                labels: frameScores.map(item => `${item.timestamp_seconds}s`),
                datasets: [
                    {
                        label: "Fake probability",
                        data: frameScores.map(item => item.percentage),
                        borderColor: "#715cff",
                        backgroundColor: "rgba(113, 92, 255, 0.14)",
                        pointBackgroundColor: frameScores.map(item => item.suspicious ? "#ff4b5f" : "#715cff"),
                        pointBorderColor: frameScores.map(item => item.suspicious ? "#ff4b5f" : "#715cff"),
                        pointRadius: 5,
                        fill: true,
                        tension: 0.35,
                    },
                    {
                        label: "70% threshold",
                        data: frameScores.map(() => 70),
                        borderColor: "rgba(255, 75, 95, 0.72)",
                        borderDash: [8, 7],
                        pointRadius: 0,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { min: 0, max: 100, ticks: { color: "#898998", callback: value => `${value}%` }, grid: { color: "rgba(255,255,255,0.08)" } },
                    x: { ticks: { color: "#898998" }, grid: { color: "rgba(255,255,255,0.05)" } },
                },
                plugins: { legend: { labels: { color: "#d8d6e5" } } },
            },
        });
        return () => chartRef.current?.destroy();
    }, [frameScores]);

    const markers = result?.suspicious_markers || [];
    return h("section", { className: "panel timeline-panel", id: "timeline-panel" },
        h("div", { className: "panel-heading compact" },
            h("span", { className: "step" }, "3"),
            h("div", null, h("h2", null, "Frame-Level Score Timeline"), h("p", null, "Red points cross the 70% suspicious threshold."))
        ),
        h("div", { className: "chart-wrap" }, frameScores.length ? h("canvas", { ref: canvasRef }) : h("div", { className: "empty-chart" }, "Timeline appears after analysis.")),
        h("div", { className: "markers" },
            markers.length ? markers.map(item => h("span", { className: "marker", key: `${item.frame_number}-${item.timestamp_seconds}` },
                `Frame ${item.frame_number}`,
                h("strong", null, `${item.percentage.toFixed(2)}%`),
                h("small", null, seconds(item.timestamp_seconds))
            )) : h("span", { className: "muted" }, "No frames crossed the 70% threshold yet.")
        )
    );
}

function MetricsPanel({ result }) {
    const metrics = result?.metrics;
    const consistency = result?.consistency;
    const rows = metrics ? [
        ["Processing", `${metrics.processing_time_seconds}s`],
        ["Frames", metrics.frames_analyzed],
        ["Minimum", percent(metrics.min_score)],
        ["Maximum", percent(metrics.max_score)],
        ["Mean", percent(metrics.mean_score)],
        ["Std dev", percent(metrics.std_score)],
        ["Model", metrics.model_name],
        ["Version", metrics.model_version],
    ] : [];

    return h("section", { className: "panel metrics-panel", id: "metrics-panel" },
        h("div", { className: "panel-heading compact" },
            h("span", { className: "step" }, "4"),
            h("div", null, h("h2", null, "Performance Metrics"), h("p", null, "Inference and score distribution."))
        ),
        h("div", { className: "metric-grid" },
            rows.length ? rows.map(([label, value]) => h("div", { className: "metric", key: label },
                h("span", null, label),
                h("strong", null, value)
            )) : h("div", { className: "empty-metrics" }, "Metrics appear after analysis.")
        ),
        h("div", { className: "consistency-card" },
            h("span", null, "Consistency confidence"),
            h("strong", null, consistency ? percent(consistency.confidence) : "--"),
            h("p", null, consistency ? `${consistency.label}: ${consistency.explanation}` : "Frame-to-frame stability is computed after inference."),
            consistency ? h("small", null, `Variance ${consistency.variance.toFixed(5)} | Std ${percent(consistency.std)}`) : null
        )
    );
}

function AdminDashboard({ user, result }) {
    const [analytics, setAnalytics] = useState(null);
    const [modelInfo, setModelInfo] = useState(null);
    const verdictCanvas = useRef(null);
    const confidenceCanvas = useRef(null);
    const verdictChart = useRef(null);
    const confidenceChart = useRef(null);

    useEffect(() => {
        if (!user) {
            setAnalytics(null);
            return;
        }
        Promise.all([
            fetch("/api/v1/admin/analytics", { headers: getAuthHeaders() }),
            fetch("/api/v1/model/info", { headers: getAuthHeaders() }),
        ])
            .then(async ([analyticsResponse, modelResponse]) => {
                const analyticsPayload = await analyticsResponse.json();
                const modelPayload = await modelResponse.json();
                if (analyticsResponse.ok && analyticsPayload.status === "success") setAnalytics(analyticsPayload.data);
                if (modelResponse.ok && modelPayload.status === "success") setModelInfo(modelPayload.data);
            });
    }, [user, result]);

    useEffect(() => {
        if (!analytics || !verdictCanvas.current) return undefined;
        verdictChart.current?.destroy();
        verdictChart.current = new Chart(verdictCanvas.current, {
            type: "doughnut",
            data: {
                labels: analytics.verdict_distribution.map(item => item.label),
                datasets: [{ data: analytics.verdict_distribution.map(item => item.count), backgroundColor: ["#715cff", "#ff4b5f", "#37d67a", "#ffcb5b", "#2ec4b6"] }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: "#d8d6e5" } } } },
        });
        return () => verdictChart.current?.destroy();
    }, [analytics]);

    useEffect(() => {
        if (!analytics || !confidenceCanvas.current) return undefined;
        confidenceChart.current?.destroy();
        confidenceChart.current = new Chart(confidenceCanvas.current, {
            type: "line",
            data: {
                labels: analytics.confidence_over_time.map(item => item.created_at.split(" ")[1] || item.created_at),
                datasets: [{ label: "Confidence", data: analytics.confidence_over_time.map(item => Number(item.confidence || 0) * 100), borderColor: "#37d67a", backgroundColor: "rgba(55, 214, 122, 0.12)", fill: true, tension: 0.35 }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { min: 0, max: 100, ticks: { color: "#898998" }, grid: { color: "rgba(255,255,255,0.08)" } },
                    x: { ticks: { color: "#898998" }, grid: { color: "rgba(255,255,255,0.05)" } },
                },
                plugins: { legend: { labels: { color: "#d8d6e5" } } },
            },
        });
        return () => confidenceChart.current?.destroy();
    }, [analytics]);

    if (!user) {
        return h("section", { className: "panel admin-panel", id: "admin-panel" },
            h("div", { className: "panel-heading compact" },
                h("span", { className: "step" }, "6"),
                h("div", null, h("h2", null, "Admin Analytics"), h("p", null, "Sign in to inspect operator metrics."))
            ),
            h("div", { className: "empty-metrics" }, "Admin analytics require a signed-in session.")
        );
    }

    const statRows = analytics ? [
        ["Total videos", analytics.total_analyses],
        ["Errors", analytics.total_errors],
        ["Errors last hour", analytics.errors_last_hour],
        ["Avg confidence", percent(analytics.average_confidence)],
        ["Avg processing", `${Number(analytics.average_processing_time_seconds).toFixed(2)}s`],
        ["Uptime", `${Number(analytics.health.uptime_seconds).toFixed(0)}s`],
        ["Model loaded", analytics.health.models_loaded > 0 ? "Yes" : "No"],
        ["Model version", modelInfo?.models?.[0]?.version || "n/a"],
    ] : [];

    return h("section", { className: "panel admin-panel", id: "admin-panel" },
        h("div", { className: "panel-heading compact" },
            h("span", { className: "step" }, "6"),
            h("div", null, h("h2", null, "Admin Analytics"), h("p", null, "Operational health, metrics, and recent analysis history."))
        ),
        h("div", { className: "metric-grid admin-stats" },
            statRows.length ? statRows.map(([label, value]) => h("div", { className: "metric", key: label }, h("span", null, label), h("strong", null, value))) : h("div", { className: "empty-metrics" }, "Analytics appear after the first request.")
        ),
        h("div", { className: "admin-charts" },
            h("div", { className: "admin-chart" }, h("h3", null, "Verdict distribution"), h("canvas", { ref: verdictCanvas })),
            h("div", { className: "admin-chart" }, h("h3", null, "Average confidence over time"), h("canvas", { ref: confidenceCanvas }))
        ),
        h("div", { className: "history-table" },
            h("h3", null, "Recent analysis history"),
            h("div", { className: "history-scroll" },
                h("table", null,
                    h("thead", null, h("tr", null, ["Request", "Status", "Verdict", "Confidence", "Time"].map(label => h("th", { key: label }, label)))),
                    h("tbody", null, (analytics?.recent_history || []).map(item => h("tr", { key: `${item.request_id}-${item.created_at}` },
                        h("td", null, item.request_id.slice(0, 8)),
                        h("td", null, item.status),
                        h("td", null, item.verdict_label || item.error_message || "Error"),
                        h("td", null, item.confidence ? percent(item.confidence) : "--"),
                        h("td", null, item.processing_time_seconds ? `${Number(item.processing_time_seconds).toFixed(2)}s` : "--")
                    )))
                )
            ),
            result?.report_url ? h("a", { className: "ghost-button report-link", href: result.report_url }, "Open forensic PDF") : null
        )
    );
}

function XaiPanel({ result }) {
    const gradcam = result?.artifacts?.gradcam;
    return h("section", { className: "panel xai-panel", id: "xai-panel" },
        h("div", { className: "panel-heading compact" },
            h("span", { className: "step" }, "5"),
            h("div", null, h("h2", null, "Grad-CAM Heatmap"), h("p", null, "Explainability status for the current model."))
        ),
        h("div", { className: "xai-status" },
            h("strong", null, gradcam?.available ? "Available" : "Unavailable"),
            h("p", null, gradcam?.message || "Grad-CAM will unlock when a Keras .h5/.keras model is available.")
        )
    );
}

function App() {
    const [user, setUser] = useState(null);
    const [result, setResult] = useState(null);
    const [toast, setToast] = useState({ message: "", tone: "info" });
    const [authMode, setAuthMode] = useState(null);

    function showToast(message, tone = "info") {
        setToast({ message, tone });
        window.setTimeout(() => setToast({ message: "", tone: "info" }), 4200);
    }

    useEffect(() => {
        fetch("/api/auth/me", { headers: getAuthHeaders() })
            .then(response => response.ok ? response.json() : { user: null })
            .then(data => setUser(data.user || null))
            .catch(() => setUser(null));
    }, []);

    async function logout() {
        await fetch("/api/auth/logout", { method: "POST", headers: getAuthHeaders() });
        window.localStorage.removeItem(TOKEN_KEY);
        setUser(null);
        setResult(null);
        showToast("Signed out.", "success");
    }

    return h(React.Fragment, null,
        h(TopNav, { user, onAuthClick: () => setAuthMode("login"), onLogout: logout }),
        h("main", { className: "app-shell" },
            h("section", { className: "hero-strip" },
                h("div", null, h("p", { className: "eyebrow" }, "Deepfake"), h("h1", null, "Forensic video detection")),
                h("p", { className: "hero-copy" }, "Frame-level scores, temporal consistency, suspicious timestamps, and model metrics in one React dashboard.")
            ),
            h("section", { className: "workflow-grid" },
                h(SourcePanel, { user, onResult: setResult, showToast, openAuth: setAuthMode }),
                h(PreviewPanel, { result })
            ),
            h("section", { className: "dashboard-grid" },
                h(TimelinePanel, { result }),
                h(MetricsPanel, { result }),
                h(AdminDashboard, { user, result }),
                h(XaiPanel, { result })
            )
        ),
        authMode ? h(AuthModal, { mode: authMode, setMode: setAuthMode, onClose: () => setAuthMode(null), onAuthed: setUser, showToast }) : null,
        h(Toast, { toast })
    );
}

ReactDOM.createRoot(document.getElementById("root")).render(h(App));
