    using Microsoft.Playwright;

namespace PlaywrightTests.Pages;

/// <summary>
/// Page Object Model for the Chatbot UI.
/// Encapsulates all selectors and actions so tests stay clean and readable.
/// If the UI changes, you update this file - not every test.
/// </summary>
public class ChatPage
{
    private readonly IPage _page;

    // --- Locators ---
    // Using data-testid attributes is the Playwright-recommended approach.
    // If the mock server UI doesn't have them yet, CSS selectors are the fallback.
    private ILocator PromptInput => _page.GetByTestId("prompt-input");
    private ILocator SubmitButton => _page.GetByTestId("submit-btn");
    private ILocator ResponseContainer => _page.GetByTestId("response-output");
    private ILocator ErrorBanner => _page.GetByTestId("error-banner");
    private ILocator HealthStatusBadge => _page.GetByTestId("health-status");
    private ILocator LoadingSpinner => _page.GetByTestId("loading-spinner");
    private ILocator ChatHistory => _page.GetByTestId("chat-history");

    public ChatPage(IPage page)
    {
        _page = page;
    }

    /// <summary>Navigates to the chat UI and waits for the page to be ready.</summary>
    public async Task GotoAsync(string baseUrl)
    {
        await _page.GotoAsync(baseUrl);
        // Wait for the submit button - confirms the JS app has fully loaded
        await SubmitButton.WaitForAsync(new LocatorWaitForOptions
        {
            State = WaitForSelectorState.Visible,
            Timeout = 10_000
        });
    }

    /// <summary>Types a prompt and submits it, then waits for a response.</summary>
    public async Task<string> SendPromptAsync(string prompt)
    {
        await PromptInput.FillAsync(prompt);
        await SubmitButton.ClickAsync();

    // Wait for spinner if it appears (CI-safe)
    if (await LoadingSpinner.IsVisibleAsync())
    {// before — returns immediately, element always exists
     //   await LoadingSpinner.WaitForAsync(new LocatorWaitForOptions
     //   {
     //       State = WaitForSelectorState.Hidden,
     //       Timeout = 10_000
     //   });
        // after — polls until text is non-empty
        await _page.WaitForFunctionAsync(
            "() => (document.getElementById('response-output')?.textContent ?? '').trim().length > 0",
            null,   
            new PageWaitForFunctionOptions { Timeout = 10_000 }
        );
    }

    await ResponseContainer.WaitForAsync(new LocatorWaitForOptions
    {
        State = WaitForSelectorState.Attached,
        Timeout = 10_000
    });
    return await ResponseContainer.InnerTextAsync();
    }

    /// <summary>Submits without typing anything - used for empty prompt edge case tests.</summary>
    public async Task ClickSubmitAsync() => await SubmitButton.ClickAsync();

    public async Task<string> GetErrorMessageAsync() => await ErrorBanner.InnerTextAsync();
    public async Task<bool> IsErrorVisibleAsync() => await ErrorBanner.IsVisibleAsync();
    public async Task<string> GetHealthStatusAsync() => await HealthStatusBadge.InnerTextAsync();
    public async Task<bool> IsSubmitButtonEnabledAsync() => await SubmitButton.IsEnabledAsync();
    public async Task<int> GetChatHistoryCountAsync() => await ChatHistory.Locator(".chat-message").CountAsync();
    public async Task<string> GetInputValueAsync() => await PromptInput.InputValueAsync();
    public async Task<string> GetPageTitleAsync() => await _page.TitleAsync();
}
