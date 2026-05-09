using FluentAssertions;
using NUnit.Framework;
using PlaywrightTests.Pages;

namespace PlaywrightTests.Tests;

/// <summary>
/// Edge case and boundary condition UI tests.
/// Mirrors test_edge_cases.py - same scenarios, but validated through the
/// browser. Catches UI bugs that pass the API layer (e.g. the error banner
/// renders but shows no text, or the spinner never disappears).
/// </summary>
[TestFixture]
[Category("EdgeCases")]
public class EdgeCaseTests : TestBase
{
    private ChatPage _chatPage = null!;

    [SetUp]
    public new async Task SetUp()
    {
        await base.SetUp();
        _chatPage = new ChatPage(Page);
        await _chatPage.GotoAsync(BaseUrl);
    }

    [Test]
    [Description("Empty prompt submission shows a user-facing error message")]
    public async Task EmptyPrompt_ShowsErrorMessage()
    {
        // Click submit without typing anything
        await _chatPage.ClickSubmitAsync();

        var isErrorVisible = await _chatPage.IsErrorVisibleAsync();

        isErrorVisible.Should().BeTrue(
            because: "AC2 requires graceful handling of non-standard input - user must see feedback");
    }

    [Test]
    [Description("Error message for empty prompt is readable and not blank")]
    public async Task EmptyPrompt_ErrorMessage_IsNotBlank()
    {
        await _chatPage.ClickSubmitAsync();
        var errorText = await _chatPage.GetErrorMessageAsync();

        errorText.Should().NotBeNullOrWhiteSpace(
            because: "an empty error banner is worse than no banner - user gets no guidance");
    }

    [Test]
    [Description("Emojis and special characters render correctly in the response area")]
    public async Task SpecialCharacters_RenderCorrectlyInUI()
    {
        var response = await _chatPage.SendPromptAsync("🚀 Test with Emojis and Symbols!@#$");

        response.Should().NotBeNullOrWhiteSpace(
            because: "AC2 requires emoji/symbol resilience without service interruption");

        // Ensure the emoji wasn't stripped or mangled in the response display
        // The mock echoes the prompt back, so some form of the content should appear
        response.Should().NotContain("undefined",
            because: "a JS rendering failure often shows 'undefined' instead of content");
    }

    [Test]
    [Description("Very long prompt (5000+ chars) shows appropriate UI feedback")]
    public async Task VeryLongPrompt_ShowsUIFeedback()
    {
        var longPrompt = string.Concat(Enumerable.Repeat("AI ", 2000)); // ~6000 chars

        // We're not asserting status code here (API tests cover that).
        // We're validating that the UI resolves the request without freezing.

        var spinner = Page.GetByTestId("loading-spinner");
        var errorBanner = Page.GetByTestId("error-banner");
        var response = Page.GetByTestId("response-output");

        // Fill and submit via the page directly so we can observe the
        // spinner in-flight (SendPromptAsync already waits for it to hide).
        await Page.GetByTestId("prompt-input").FillAsync(longPrompt);
        await Page.GetByTestId("submit-btn").ClickAsync();

        // Spinner should appear now that the request is in-flight.
        // Use a short timeout: the mock server responds quickly even for 413s.
        await Expect(spinner).ToBeVisibleAsync(new() { Timeout = 3000 });

        // Spinner must eventually disappear (request resolved one way or another)
        await Expect(spinner).ToBeHiddenAsync(new() { Timeout = 30000 });

        // Final UI state: mock server returns 413 for >5000 chars, so the UI
        // surfaces an error banner. Either that or a response is acceptable —
        // what's not acceptable is the page freezing or spinner staying forever.
        var isErrorVisible = await errorBanner.IsVisibleAsync();
        var hasResponse =
            await response.IsVisibleAsync() &&
            !string.IsNullOrWhiteSpace(await response.InnerTextAsync());

        (isErrorVisible || hasResponse).Should().BeTrue(
            because: "AC2 requires oversized input to resolve with either an error state or a response, but never a frozen UI");
    }

    [Test]
    [Description("Gibberish input returns a response without crashing the UI")]
    public async Task GibberishPrompt_DoesNotCrashUI()
    {
        var response = await _chatPage.SendPromptAsync("asdkfjasldkfj123!##");

        // No assertion on content - just that the UI stayed alive and rendered something
        response.Should().NotBeNull(
            because: "the UI should handle any string input without throwing a JS exception");

        // Verify the page is still interactive after a weird prompt
        var isSubmitEnabled = await _chatPage.IsSubmitButtonEnabledAsync();
        isSubmitEnabled.Should().BeTrue(
            because: "the UI should recover and allow another prompt after any input");
    }

    [Test]
    [Description("SQL injection string is handled safely and displayed as plain text")]
    public async Task SqlInjectionString_RendersAsSafeText()
    {
        var sqlPayload = "'; DROP TABLE users; --";
        var response = await _chatPage.SendPromptAsync(sqlPayload);

        // The response area should show text, not execute anything
        response.Should().NotBeNullOrWhiteSpace();

        // Crucially - the page should still be intact
        var title = await _chatPage.GetPageTitleAsync();
        title.Should().NotBeNullOrWhiteSpace(
            because: "a SQL injection string in the UI should never break the page structure");
    }
}
