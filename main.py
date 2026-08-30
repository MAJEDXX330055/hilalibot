"""Fetch news, generate a tweet with Gemini, and publish it to X.

Set the following environment variables before running:

    X_CONSUMER_KEY
    X_CONSUMER_SECRET
    X_ACCESS_TOKEN
    X_ACCESS_TOKEN_SECRET
    GEMINI_API_KEY

Optional:

    GEMINI_MODEL (defaults to gemini-3.6-flash)
    NEWS_FEED_URL (defaults to the Google News top stories RSS feed)
"""

import os

import feedparser
from google import genai
import tweepy

DEFAULT_NEWS_FEED_URL = (
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
)


def create_x_client() -> tweepy.Client:
    """Create an X API v2 client using OAuth 1.0a User Context."""
    return tweepy.Client(
        consumer_key=os.environ["X_CONSUMER_KEY"],
        consumer_secret=os.environ["X_CONSUMER_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def publish_tweet(tweet: str) -> tweepy.Response:
    """Publish a tweet using OAuth 1.0a User Context."""
    return create_x_client().create_tweet(text=tweet, user_auth=True)


def create_gemini_client() -> genai.Client:
    """Create an authenticated Gemini API client."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Missing required environment variable: GEMINI_API_KEY")

    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_text(client: genai.Client, prompt: str) -> str:
    """Generate text with Gemini."""
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def read_rss_feed(feed_url: str, limit: int = 5) -> list[dict[str, str]]:
    """Read a feed and return a small, normalized list of entries."""
    parsed_feed = feedparser.parse(feed_url)
    if not parsed_feed.entries:
        error = getattr(parsed_feed, "bozo_exception", None)
        detail = f": {error}" if error else ""
        raise RuntimeError(f"No news entries were found in the RSS feed{detail}")

    return [
        {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
        }
        for entry in parsed_feed.entries[:limit]
    ]


def build_tweet_prompt(news_items: list[dict[str, str]]) -> str:
    """Build a grounded prompt from the latest news entries."""
    formatted_items = "\n\n".join(
        f"Headline: {item['title']}\nSummary: {item['summary']}\nSource: {item['link']}"
        for item in news_items
    )
    return f"""Write one factual tweet about the most significant story below.

Rules:
- Return only the tweet text, with no quotation marks, labels, or markdown.
- Keep it under 260 characters so it can be posted safely to X.
- Summarize only information present in the supplied headlines or summaries.
- Do not invent details, statistics, opinions, or quotes.
- Use a clear, neutral news tone.

Latest news:
{formatted_items}
"""


def clean_tweet(tweet: str) -> str:
    """Normalize Gemini output and ensure it fits within X's character limit."""
    cleaned = tweet.strip().replace("\n", " ")
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
    if cleaned.lower().startswith("tweet:"):
        cleaned = cleaned[6:].strip()
    cleaned = cleaned.strip("\"'").strip()

    if not cleaned:
        raise RuntimeError("Gemini returned an empty tweet")
    if len(cleaned) > 280:
        cleaned = f"{cleaned[:277].rstrip()}..."
    return cleaned


def main() -> None:
    """Fetch news, generate a tweet, and publish it to X."""
    gemini_client = create_gemini_client()
    feed_url = os.getenv("NEWS_FEED_URL", DEFAULT_NEWS_FEED_URL)
    news_items = read_rss_feed(feed_url)
    tweet = clean_tweet(generate_text(gemini_client, build_tweet_prompt(news_items)))

    response = publish_tweet(tweet)
    tweet_id = response.data.get("id") if response.data else None
    if not tweet_id:
        raise RuntimeError("X did not return a tweet ID after publishing")

    print(f"Published tweet {tweet_id}:")
    print(tweet)


if __name__ == "__main__":
    main()
