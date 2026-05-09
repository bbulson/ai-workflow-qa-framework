using Microsoft.Playwright.NUnit;
using Microsoft.Playwright;
using NUnit.Framework;

namespace PlaywrightTests;

/// <summary>
/// Base class for all UI tests. Handles browser setup, teardown,
/// screenshot capture on failure, trace capture on failure,
/// and shared config like BaseUrl.
/// All test classes inherit from this instead of PageTest directly.
/// </summary>
[Parallelizable(ParallelScope.Self)]
public class TestBase : PageTest
{
    protected string BaseUrl { get; private set; } = string.Empty;

    [SetUp]
    public async Task SetUp()
    {
        // Reads BASE_URL from env (set in CI) or falls back to local mock server
        BaseUrl = Environment.GetEnvironmentVariable("BASE_URL") ?? "https://localhost:5000";

        // Ignore SSL cert errors - the mock server uses a self-signed cert (same as Python tests)
        await Context.SetExtraHTTPHeadersAsync(new Dictionary<string, string>
        {
            ["Accept"] = "application/json, text/html"
        });

        // Start tracing for every test - we save the trace only on failure in TearDown
        await Context.Tracing.StartAsync(new TracingStartOptions
        {
            Screenshots = true,  // embed screenshots in the trace timeline
            Snapshots = true,    // enable snapshot-based step inspection in trace viewer
            Sources = true       // embed C# source lines in the trace
        });
    }

    [TearDown]
    public async Task TearDown()
    {
        var failed = TestContext.CurrentContext.Result.Outcome.Status ==
                     NUnit.Framework.Interfaces.TestStatus.Failed;

        var testName = TestContext.CurrentContext.Test.Name;
        var timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        var workDir  = TestContext.CurrentContext.WorkDirectory;

        if (failed)
        {
            // ── Screenshot ────────────────────────────────────────────────
            var screenshotDir = Path.Combine(workDir, "reports", "screenshots");
            Directory.CreateDirectory(screenshotDir);

            var screenshotPath = Path.Combine(screenshotDir, $"{testName}_{timestamp}.png");
            await Page.ScreenshotAsync(new PageScreenshotOptions
            {
                Path = screenshotPath,
                FullPage = true
            });
            TestContext.WriteLine($"Screenshot saved: {screenshotPath}");

            // ── Trace ─────────────────────────────────────────────────────
            var traceDir = Path.Combine(workDir, "reports", "traces");
            Directory.CreateDirectory(traceDir);

            var tracePath = Path.Combine(traceDir, $"{testName}_{timestamp}.zip");
            await Context.Tracing.StopAsync(new TracingStopOptions
            {
                Path = tracePath
            });
            TestContext.WriteLine($"Trace saved: {tracePath}");
        }
        else
        {
            // Stop tracing without saving - test passed, no need to keep the trace
            await Context.Tracing.StopAsync(new TracingStopOptions());
        }
    }

    /// <summary>
    /// Returns Playwright browser context options - headless in CI, headed locally.
    /// </summary>
    public override BrowserNewContextOptions ContextOptions()
    {
        return new BrowserNewContextOptions
        {
            // Trust self-signed certs from the mock server (mirrors Python's verify=False)
            IgnoreHTTPSErrors = true,
            ViewportSize = new ViewportSize { Width = 1280, Height = 720 },
            RecordVideoDir = Environment.GetEnvironmentVariable("RECORD_VIDEO") == "true"
                ? "reports/videos"
                : null
        };
    }
}
