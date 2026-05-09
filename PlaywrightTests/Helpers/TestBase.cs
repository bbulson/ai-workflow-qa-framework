using Microsoft.Playwright.NUnit;
using Microsoft.Playwright;
using NUnit.Framework;

namespace PlaywrightTests;

/// <summary>
/// Base class for all UI tests. Handles browser setup, teardown,
/// screenshot capture on failure, and shared config like BaseUrl.
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
    }

    [TearDown]
    public async Task TearDown()
    {
        // On failure, capture a screenshot for the CI artifact report
        if (TestContext.CurrentContext.Result.Outcome.Status == NUnit.Framework.Interfaces.TestStatus.Failed)
        {
            var screenshotDir = Path.Combine(TestContext.CurrentContext.WorkDirectory, "reports", "screenshots");
            Directory.CreateDirectory(screenshotDir);

            var fileName = $"{TestContext.CurrentContext.Test.Name}_{DateTime.Now:yyyyMMdd_HHmmss}.png";
            var screenshotPath = Path.Combine(screenshotDir, fileName);

            await Page.ScreenshotAsync(new PageScreenshotOptions
            {
                Path = screenshotPath,
                FullPage = true
            });

            TestContext.WriteLine($"Screenshot saved: {screenshotPath}");
        }
    }

    /// <summary>
    /// Returns Playwright browser launch options - headless in CI, headed locally.
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
