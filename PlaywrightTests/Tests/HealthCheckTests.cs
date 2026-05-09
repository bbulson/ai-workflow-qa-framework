using FluentAssertions;
using NUnit.Framework;
using PlaywrightTests.Pages;

namespace PlaywrightTests.Tests;

/// <summary>
/// UI-layer health checks.
/// Mirrors test_api_health.py from the Python suite, but validates
/// what the *user actually sees* in the browser, not just HTTP status codes.
/// </summary>
[TestFixture]
[Category("Health")]
public class HealthCheckTests : TestBase
{
    private ChatPage _chatPage = null!;

    [SetUp]
    public new async Task SetUp()
    {
        await base.SetUp();
        _chatPage = new ChatPage(Page);
    }

    [Test]
    [Description("The chat UI loads and the page title is present")]
    public async Task ChatUI_Loads_WithCorrectTitle()
    {
        await _chatPage.GotoAsync(BaseUrl);

        var title = await _chatPage.GetPageTitleAsync();

        title.Should().NotBeNullOrWhiteSpace(
            because: "a missing title means the HTML shell failed to load");
    }

    [Test]
    [Description("The health status badge shows 'ok' when the API is up")]
    public async Task HealthBadge_ShowsOk_WhenApiIsRunning()
    {
        await _chatPage.GotoAsync(BaseUrl);

        var status = await _chatPage.GetHealthStatusAsync();

        status.Should().Be("ok",
            because: "the UI polls /health on load and should surface the result to users");
    }

    [Test]
    [Description("The submit button is enabled when the page first loads")]
    public async Task SubmitButton_IsEnabled_OnPageLoad()
    {
        await _chatPage.GotoAsync(BaseUrl);

        var isEnabled = await _chatPage.IsSubmitButtonEnabledAsync();

        isEnabled.Should().BeTrue(
            because: "users should be able to submit a prompt immediately on page load");
    }

    [Test]
    [Description("The page responds within an acceptable time (SLA: 2s)")]
    public async Task ChatUI_Loads_WithinSLA()
    {
        var start = DateTime.UtcNow;

        await _chatPage.GotoAsync(BaseUrl);

        var elapsed = (DateTime.UtcNow - start).TotalMilliseconds;

        elapsed.Should().BeLessThan(2000,
            because: "AC4 requires 95th percentile latency under 500ms; a 2s page load is a red flag");
    }
}
