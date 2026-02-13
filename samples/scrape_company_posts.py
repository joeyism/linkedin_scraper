#!/usr/bin/env python3
import asyncio
from linkedin_scraper.scrapers.company_posts import CompanyPostsScraper
from linkedin_scraper.core.browser import BrowserManager


async def main():
    company_url = "https://www.linkedin.com/company/microsoft/"
    
    # Uses default user_data_dir — session persists automatically
    async with BrowserManager(headless=False) as browser:
        scraper = CompanyPostsScraper(browser.page)
        
        print(f"🔍 Scraping posts from: {company_url}")
        posts = await scraper.scrape(company_url, limit=5)
        
        print(f"\n✓ Found {len(posts)} posts\n")
        print("=" * 60)
        
        for i, post in enumerate(posts, 1):
            print(f"\n📝 Post {i}:")
            print(f"   URL: {post.linkedin_url}")
            print(f"   Posted: {post.posted_date}")
            print(f"   Reactions: {post.reactions_count}")
            print(f"   Comments: {post.comments_count}")
            print(f"   Reposts: {post.reposts_count}")
            print(f"   Images: {len(post.image_urls)}")
            if post.text:
                text_preview = post.text[:200] + "..." if len(post.text) > 200 else post.text
                print(f"   Text: {text_preview}")
            print("-" * 40)
        
        print("\n" + "=" * 60)
    
    print("\n✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())
