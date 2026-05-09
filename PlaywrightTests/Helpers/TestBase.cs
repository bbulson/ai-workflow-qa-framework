using Microsoft.Playwright.NUnit;
using Microsoft.Playwright;
using NUnit.Framework;
using System.Text.Json;

namespace PlaywrightTests;

/// <summary>
/// Base class for all UI tests. Handles browser setup, teardown,
/// screenshot capture on failure, trace capture on failure,
/// network request logging (always), and shared config like BaseUrl.
///
/// UI tests: network entries are collected automatically via Page.Request /
/// Page.Response event hooks.
///
/// API tests (using IAPIRequestContext): call LogResponse() after each
/// request so the same network log is populated.
///
/// Tracing behaviour:
///   - Always saved on failure.
///   - Also saved on passing tests tagged [Category("AlwaysTrace")], so you
///     can inspect specific tests in the Playwright trace viewer without
///     waiting for them to fail.
/// </summary>
[Parallelizable(ParallelScope.Self)]
public class TestBase : PageTest
{
    protected string BaseUrl { get; private set; } = string.Empty;

    private readonly List<NetworkEntry> _networkLog = new();

    [SetUp]
    public async Task SetUp()
    {
        BaseUrl = Environment.GetEnvironmentVariable("BASE_URL") ?? "https://localhost:5000";

        await Context.SetExtraHTTPHeadersAsync(new Dictionary<string, string>
        {
            ["Accept"] = "application/json, text/html"
        });

        // Start tracing for every test.
        // Saved to disk in TearDown when: (a) the test failed, or
        // (b) the test is tagged [Category("AlwaysTrace")].
        await Context.Tracing.StartAsync(new TracingStartOptions
        {
            Screenshots = false, // don't capture screenshots inside the trace —
                                 // avoids blank PNG artifacts in CI headless mode
            Snapshots = true,    // enables DOM snapshot inspection in trace viewer
            Sources = true       // shows C# source lines alongside each action
        });

        // Automatically capture browser-page network traffic (UI tests)
        _networkLog.Clear();
        Page.Request += (_, req) =>
        {
            _networkLog.Add(new NetworkEntry
            {
                Url = req.Url,
                Method = req.Method,
                RequestTime = DateTime.UtcNow
            });
        };
        Page.Response += (_, resp) =>
        {
            var entry = _networkLog.LastOrDefault(e => e.Url == resp.Url && e.Status == 0);
            if (entry != null)
            {
                entry.Status = resp.Status;
                entry.ResponseTime = DateTime.UtcNow;
            }
        };
    }

    /// <summary>
    /// Called by API test methods (IAPIRequestContext) to record an HTTP
    /// exchange that bypasses the browser page and therefore doesn't fire
    /// Page.Request / Page.Response events.
    /// </summary>
    protected void LogResponse(string method, string url, int status,
                               DateTime requestTime, DateTime responseTime)
    {
        _networkLog.Add(new NetworkEntry
        {
            Method = method,
            Url = url,
            Status = status,
            RequestTime = requestTime,
            ResponseTime = responseTime
        });
    }

    [TearDown]
    public async Task TearDown()
    {
        var failed = TestContext.CurrentContext.Result.Outcome.Status ==
                     NUnit.Framework.Interfaces.TestStatus.Failed;

        // Check for the AlwaysTrace category marker
        var categories = TestContext.CurrentContext.Test.Properties["Category"] as IEnumerable<object>;
        var alwaysTrace = categories?.Contains("AlwaysTrace") ?? false;

        var testName = TestContext.CurrentContext.Test.Name;
        var timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        var workDir   = TestContext.CurrentContext.WorkDirectory;

        // ── Always write network log ──────────────────────────────────
        try
        {
            var netDir = Path.Combine(workDir, "reports", "network");
            Directory.CreateDirectory(netDir);
            var netPath = Path.Combine(netDir, $"{testName}_{timestamp}.json");
            var netJson = JsonSerializer.Serialize(_networkLog,
                new JsonSerializerOptions { WriteIndented = true });
            await File.WriteAllTextAsync(netPath, netJson);
            TestContext.WriteLine($"Network log saved: {netPath}");
        }
        catch (Exception ex)
        {
            TestContext.WriteLine($"Network log write failed: {ex.Message}");
        }

        if (failed || alwaysTrace)
        {
            // ── Screenshot (failure only — not needed alongside a full trace) ─
            if (failed)
            {
                try
                {
                    var screenshotDir = Path.Combine(workDir, "reports", "screenshots");
                    Directory.CreateDirectory(screenshotDir);
                    var screenshotPath = Path.Combine(screenshotDir, $"{testName}_{timestamp}.png");
                    await Page.ScreenshotAsync(new PageScreenshotOptions
                    {
                        Path = screenshotPath,
                        FullPage = true
                    });
                    TestContext.WriteLine($"Screenshot saved: {screenshotPath}");
                }
                catch (Exception ex)
                {
                    TestContext.WriteLine($"Screenshot skipped (page may be closed): {ex.Message}");
                }
            }

            // ── Trace (failure OR AlwaysTrace) ────────────────────────
            try
            {
                var traceDir = Path.Combine(workDir, "reports", "traces");
                Directory.CreateDirectory(traceDir);
                var tracePath = Path.Combine(traceDir, $"{testName}_{timestamp}.zip");
                await Context.Tracing.StopAsync(new TracingStopOptions { Path = tracePath });
                TestContext.WriteLine($"Trace saved: {tracePath}");
            }
            catch (Exception ex)
            {
                TestContext.WriteLine($"Trace save skipped (context may be closed): {ex.Message}");
            }
        }
        else
        {
            // Passed and not marked AlwaysTrace — discard the trace
            try { await Context.Tracing.StopAsync(new TracingStopOptions()); }
            catch { /* context already closed - safe to ignore */ }
        }
    }

    public override BrowserNewContextOptions ContextOptions()
    {
        return new BrowserNewContextOptions
        {
            IgnoreHTTPSErrors = true,
            ViewportSize = new ViewportSize { Width = 1280, Height = 720 },
            RecordVideoDir = Environment.GetEnvironmentVariable("RECORD_VIDEO") == "true"
                ? "reports/videos"
                : null
        };
    }
}

/// <summary>Lightweight record of a single HTTP exchange during a test.</summary>
public class NetworkEntry
{
    public string Url { get; set; } = string.Empty;
    public string Method { get; set; } = string.Empty;
    public int Status { get; set; }
    public DateTime RequestTime { get; set; }
    public DateTime ResponseTime { get; set; }
    public double DurationMs => Status > 0 ? (ResponseTime - RequestTime).TotalMilliseconds : 0;
}
