using FluentAssertions;
using NUnit.Framework;
using PlaywrightTests.Pages;
using System.Text.Json;

namespace PlaywrightTests.Tests;

/// <summary>
/// End-to-end chat workflow tests.
/// Mirrors test_chat_workflows.py but drives the actual browser UI,
/// validating the full user-facing experience rather than raw HTTP responses.
/// </summary>
[TestFixture]
[Category("Workflows")]
public class ChatWorkflowTests : TestBase
{
    private ChatPage _chatPage = null!;

    // Load the same prompts.json used by the Python test suite
    // so both layers are testing against identical inputs.
    private static readonly string PromptsPath = Path.Combine(
        AppContext.BaseDirectory, "..", "..", "..", "..", "test_data", "prompts.json");

    [SetUp]
    public new async Task SetUp()
    {
        await base.SetUp();
        _chatPage = new ChatPage(Page);
        await _chatPage.GotoAsync(BaseUrl);
    }

    [Test]
    [Description("A standard prompt produces a visible, non-empty response in the UI")]
    public async Task StandardPrompt_Returns_VisibleResponse()
    {
        var response = await _chatPage.SendPromptAsync("Hello, how are you?");

        response.Should().NotBeNullOrWhiteSpace(
            because: "AC1 requires a valid response for all standard prompt requests");
    }

    [Test]
    [Description("Input field is cleared after a successful prompt submission")]
    public async Task PromptInput_IsClearedAfterSubmission()
    {
        await _chatPage.SendPromptAsync("Clear me after submit");

        var inputValue = await _chatPage.GetInputValueAsync();

        inputValue.Should().BeEmpty(
            because: "good UX clears the input after submission, ready for the next message");
    }

    [Test]
    [Description("Multiple sequential prompts all appear in chat history")]
    public async Task MultiplePrompts_AllAppearInChatHistory()
    {
        await _chatPage.SendPromptAsync("First message");
        await _chatPage.SendPromptAsync("Second message");
        await _chatPage.SendPromptAsync("Third message");

        var historyCount = await _chatPage.GetChatHistoryCountAsync();

        historyCount.Should().BeGreaterThanOrEqualTo(3,
            because: "each prompt/response pair should be appended to the conversation history");
    }

    [Test]
    [Description("All prompts from prompts.json produce a non-empty UI response")]
    public async Task AllDataDrivenPrompts_ReturnVisibleResponses()
    {
        if (!File.Exists(PromptsPath))
            Assert.Ignore("prompts.json not found - skipping data-driven test");

        var json = await File.ReadAllTextAsync(PromptsPath);
        var prompts = JsonSerializer.Deserialize<List<string>>(json) ?? new List<string>();

        foreach (var prompt in prompts)
        {
            var response = await _chatPage.SendPromptAsync(prompt);

            response.Should().NotBeNullOrWhiteSpace(
                because: $"prompt '{prompt[..Math.Min(50, prompt.Length)]}...' should return a response");
        }
    }
}
