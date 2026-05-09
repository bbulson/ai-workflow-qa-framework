using FluentAssertions;
using Microsoft.Playwright;
using NUnit.Framework;
using System.Text.Json;

namespace PlaywrightTests.Tests;

/// <summary>
/// API-layer tests using Playwright's built-in APIRequestContext.
/// These sit alongside the Python API tests but are written in C#,
/// demonstrating API automation in the same language as the UI tests.
/// No browser is launched here - this is pure HTTP validation.
/// 
/// This is the C# equivalent of test_api_health.py + test_orders_validation.py.
/// </summary>
[TestFixture]
[Category("API")]
public class ApiValidationTests : TestBase
{
    private IAPIRequestContext _apiContext = null!;

    [SetUp]
    public new async Task SetUp()
    {
        await base.SetUp();

        _apiContext = await Playwright.APIRequest.NewContextAsync(new APIRequestNewContextOptions
        {
            BaseURL = BaseUrl,
            IgnoreHTTPSErrors = true,  // mirrors Python's verify=False
            ExtraHTTPHeaders = new Dictionary<string, string>
            {
                ["Content-Type"] = "application/json"
            }
        });
    }

    [TearDown]
    public new async Task TearDown()
    {
        await base.TearDown();
        await _apiContext.DisposeAsync();
    }

    // ---------------------------------------------------------------
    // Health Endpoint
    // ---------------------------------------------------------------

    [Test]
    [Description("GET /health returns HTTP 200")]
    public async Task HealthEndpoint_Returns200()
    {
        var response = await _apiContext.GetAsync("/health");

        response.Status.Should().Be(200,
            because: "AC3: /health must be reachable for pipeline readiness checks");
    }

    [Test]
    [Description("GET /health response body contains status: ok")]
    public async Task HealthEndpoint_ReturnsOkStatus()
    {
        var response = await _apiContext.GetAsync("/health");
        var body = await response.JsonAsync();

        body?.GetProperty("status").GetString()
            .Should().Be("ok",
                because: "the health contract specifies a 'status' field with value 'ok'");
    }

    // ---------------------------------------------------------------
    // Chat Endpoint - Happy Path
    // ---------------------------------------------------------------

    [Test]
    [Description("POST /chat with valid prompt returns HTTP 200")]
    public async Task ChatEndpoint_WithValidPrompt_Returns200()
    {
        var response = await _apiContext.PostAsync("/chat", new APIRequestContextOptions
        {
            DataObject = new { prompt = "Hello from C# Playwright" }
        });

        response.Status.Should().Be(200);
    }

    [Test]
    [Description("POST /chat response body contains a non-empty 'response' field")]
    public async Task ChatEndpoint_ResponseBody_ContainsResponseField()
    {
        var response = await _apiContext.PostAsync("/chat", new APIRequestContextOptions
        {
            DataObject = new { prompt = "Test prompt" }
        });

        var body = await response.JsonAsync();
        var responseText = body?.GetProperty("response").GetString();

        responseText.Should().NotBeNullOrWhiteSpace(
            because: "AC1: the API must return a valid response field for all standard prompts");
    }

    // ---------------------------------------------------------------
    // Chat Endpoint - Error Cases (mirrors test_edge_cases.py)
    // ---------------------------------------------------------------

    [Test]
    [Description("POST /chat with null prompt returns HTTP 400")]
    public async Task ChatEndpoint_WithNullPrompt_Returns400()
    {
        var response = await _apiContext.PostAsync("/chat", new APIRequestContextOptions
        {
            DataObject = new { prompt = (string?)null }
        });

        response.Status.Should().Be(400,
            because: "AC3: malformed requests must return appropriate 4xx codes");
    }

    [Test]
    [Description("POST /chat with empty string prompt returns HTTP 400")]
    public async Task ChatEndpoint_WithEmptyPrompt_Returns400()
    {
        var response = await _apiContext.PostAsync("/chat", new APIRequestContextOptions
        {
            DataObject = new { prompt = "" }
        });

        response.Status.Should().Be(400);
    }

    [Test]
    [Description("POST /chat with 5000+ char prompt returns HTTP 413")]
    public async Task ChatEndpoint_WithOversizedPrompt_Returns413()
    {
        var longPrompt = string.Concat(Enumerable.Repeat("AI ", 2000));

        var response = await _apiContext.PostAsync("/chat", new APIRequestContextOptions
        {
            DataObject = new { prompt = longPrompt }
        });

        response.Status.Should().Be(413,
            because: "the API should reject payloads exceeding the token limit");
    }

    [Test]
    [Description("POST /chat with emoji and special characters returns HTTP 200")]
    public async Task ChatEndpoint_WithSpecialCharacters_Returns200()
    {
        var response = await _apiContext.PostAsync("/chat", new APIRequestContextOptions
        {
            DataObject = new { prompt = "🚀 Test with Emojis and Symbols!@#$" }
        });

        response.Status.Should().Be(200,
            because: "AC2: the service must not crash on emoji or symbol input");
    }

    // ---------------------------------------------------------------
    // Response Time SLA (mirrors JMeter intent, single-request baseline)
    // ---------------------------------------------------------------

    [Test]
    [Description("POST /chat responds within 500ms (SLA baseline - single request)")]
    public async Task ChatEndpoint_RespondsWith_AcceptableLatency()
    {
        var start = DateTime.UtcNow;

        await _apiContext.PostAsync("/chat", new APIRequestContextOptions
        {
            DataObject = new { prompt = "Latency check" }
        });

        var elapsed = (DateTime.UtcNow - start).TotalMilliseconds;

        elapsed.Should().BeLessThan(500,
            because: "AC4: 95% of requests must complete within 500ms under 5 concurrent users");
    }
}
