import logging
import re
from typing import List, Optional
from playwright.async_api import Page

from ..models.post import Post
from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper

logger = logging.getLogger(__name__)


class CompanyPostsScraper(BaseScraper):
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        super().__init__(page, callback or SilentCallback())
    
    async def scrape(self, company_url: str, limit: int = 10) -> List[Post]:
        logger.info(f"Starting company posts scraping: {company_url}")
        await self.callback.on_start("company_posts", company_url)
        
        posts_url = self._build_posts_url(company_url)
        await self.navigate_and_wait(posts_url)
        await self.callback.on_progress("Navigated to posts page", 10)
        
        await self.check_rate_limit()
        
        await self._wait_for_posts_to_load()
        await self.callback.on_progress("Posts loaded", 20)
        
        posts = await self._scrape_posts(limit)
        await self.callback.on_progress(f"Scraped {len(posts)} posts", 100)
        await self.callback.on_complete("company_posts", posts)
        
        logger.info(f"Successfully scraped {len(posts)} posts")
        return posts
    
    def _build_posts_url(self, company_url: str) -> str:
        company_url = company_url.rstrip('/')
        if '/posts' not in company_url:
            return f"{company_url}/posts/"
        return company_url
    
    async def _wait_for_posts_to_load(self, timeout: int = 30000) -> None:
        try:
            await self.page.wait_for_load_state('domcontentloaded', timeout=timeout)
        except Exception as e:
            logger.debug(f"DOM load timeout: {e}")
        
        await self.page.wait_for_timeout(3000)
        
        for attempt in range(3):
            await self._trigger_lazy_load()
            
            has_posts = await self.page.evaluate('''() => {
                return [...document.querySelectorAll('[role="listitem"]')].some(
                    el => (el.getAttribute('componentkey') || '').startsWith('update-card-focus')
                );
            }''')
            
            if has_posts:
                logger.debug(f"Posts found after attempt {attempt + 1}")
                return
            
            await self.page.wait_for_timeout(2000)
        
        logger.warning("Posts may not have loaded fully")
    
    async def _trigger_lazy_load(self) -> None:
        await self.page.evaluate('''() => {
            const scrollHeight = document.documentElement.scrollHeight;
            const steps = 8;
            const stepSize = Math.min(scrollHeight / steps, 400);
            
            for (let i = 1; i <= steps; i++) {
                setTimeout(() => window.scrollTo(0, stepSize * i), i * 200);
            }
        }''')
        await self.page.wait_for_timeout(2500)
        
        await self.page.evaluate('window.scrollTo(0, 400)')
        await self.page.wait_for_timeout(1000)
    
    async def _scrape_posts(self, limit: int) -> List[Post]:
        posts: List[Post] = []
        scroll_count = 0
        max_scrolls = (limit // 3) + 2
        
        while len(posts) < limit and scroll_count < max_scrolls:
            new_posts = await self._extract_posts_from_page()
            
            for post in new_posts:
                key = post.urn or post.linkedin_url or (post.text or "")[:100]
                existing = {
                    (p.urn or p.linkedin_url or (p.text or "")[:100]) for p in posts
                }
                if key and key not in existing:
                    posts.append(post)
                    if len(posts) >= limit:
                        break
            
            if len(posts) < limit:
                await self._scroll_for_more_posts()
                scroll_count += 1
        
        return posts[:limit]
    
    async def _extract_posts_from_page(self) -> List[Post]:
        return await self._extract_posts_via_js()
    
    async def _extract_posts_via_js(self) -> List[Post]:
        posts_data = await self.page.evaluate('''() => {
            // Ordered URNs from the feed state (may only cover the first page).
            let urns = [];
            const m = document.documentElement.innerHTML.match(/"currentFirstPageUrns":\\[(.*?)\\]/);
            if (m) {
                const re = /"(urn:li:[^"]+)"/g;
                let x;
                while ((x = re.exec(m[1])) !== null) urns.push(x[1]);
            }

            const cards = [...document.querySelectorAll('[role="listitem"]')].filter(
                el => (el.getAttribute('componentkey') || '').startsWith('update-card-focus')
            );

            const results = [];
            cards.forEach((card, index) => {
                let text = '';
                const box = card.querySelector('[data-testid="expandable-text-box"]');
                if (box) text = (box.innerText || '').trim();

                if (!text) {
                    let best = '';
                    for (const p of card.querySelectorAll('p')) {
                        const t = (p.innerText || '').trim();
                        if (t.length > best.length && !/^\\d+[hdwmy]\\b/.test(t) && !t.includes('followers')) {
                            best = t;
                        }
                    }
                    text = best;
                }

                if (!text || text.length < 10) return;

                let timeText = '';
                for (const p of card.querySelectorAll('p')) {
                    const t = (p.innerText || '').trim();
                    if (/^\\d+[hdwmy]\\b/.test(t)) { timeText = t; break; }
                }

                const findByAria = (needle) => {
                    for (const b of card.querySelectorAll('button')) {
                        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                        if (aria.includes(needle)) return (b.innerText || '').trim();
                    }
                    return '';
                };

                let reactions = findByAria('reaction button state');
                if (!reactions) reactions = findByAria('reaction');
                const comments = findByAria('comment');
                const reposts = findByAria('repost');

                const images = [];
                for (const img of card.querySelectorAll('img[src*="media"]')) {
                    const src = img.getAttribute('src') || '';
                    if (src && !src.includes('profile') && !src.includes('logo')) {
                        images.push(src);
                    }
                }

                const urn = index < urns.length ? urns[index] : null;
                results.push({
                    urn: urn && urn.startsWith('urn:li:activity:') ? urn : null,
                    text,
                    timeText,
                    reactions,
                    comments,
                    reposts,
                    images
                });
            });

            return results;
        }''')
        
        result: List[Post] = []
        for data in posts_data:
            urn = data.get('urn')
            activity_id = urn.replace('urn:li:activity:', '') if urn else None
            post = Post(
                linkedin_url=(
                    f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                    if activity_id else None
                ),
                urn=urn,
                text=data['text'],
                posted_date=self._extract_time_from_text(data.get('timeText', '')),
                reactions_count=self._parse_count(data.get('reactions', '')),
                comments_count=self._parse_count(data.get('comments', '')),
                reposts_count=self._parse_count(data.get('reposts', '')),
                image_urls=data.get('images', [])
            )
            result.append(post)
        
        return result
    
    def _extract_time_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(r'(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        parts = text.split('•')
        if parts:
            return parts[0].strip()
        return None
    
    async def _parse_post_element(self, element) -> Optional[Post]:
        try:
            urn = await element.get_attribute('data-urn')
            if not urn or 'activity' not in urn:
                return None
            
            activity_id = urn.replace('urn:li:activity:', '')
            linkedin_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
            
            text = await self._get_post_text(element)
            posted_date = await self._get_posted_date(element)
            reactions_count = await self._get_reactions_count(element)
            comments_count = await self._get_comments_count(element)
            reposts_count = await self._get_reposts_count(element)
            image_urls = await self._get_image_urls(element)
            
            return Post(
                linkedin_url=linkedin_url,
                urn=urn,
                text=text,
                posted_date=posted_date,
                reactions_count=reactions_count,
                comments_count=comments_count,
                reposts_count=reposts_count,
                image_urls=image_urls
            )
        except Exception as e:
            logger.debug(f"Error parsing post: {e}")
            return None
    
    async def _get_post_text(self, element) -> Optional[str]:
        try:
            text_container = element.locator('.feed-shared-update-v2__description, .break-words')
            if await text_container.count() > 0:
                text = await text_container.first.inner_text()
                return text.strip() if text else None
        except:
            pass
        return None
    
    async def _get_posted_date(self, element) -> Optional[str]:
        try:
            time_elem = element.locator('[class*="actor__sub-description"], [class*="update-components-actor__sub-description"]')
            if await time_elem.count() > 0:
                text = await time_elem.first.inner_text()
                match = re.search(r'(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago)', text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                if text:
                    clean_text = text.split('•')[0].strip()
                    return clean_text if clean_text else None
        except:
            pass
        return None
    
    async def _get_reactions_count(self, element) -> Optional[int]:
        try:
            reactions_elem = element.locator('[class*="social-details-social-counts__reactions"], button[aria-label*="reaction"]')
            if await reactions_elem.count() > 0:
                text = await reactions_elem.first.inner_text()
                return self._parse_count(text)
        except:
            pass
        return None
    
    async def _get_comments_count(self, element) -> Optional[int]:
        try:
            comments_elem = element.locator('button[aria-label*="comment"]')
            if await comments_elem.count() > 0:
                text = await comments_elem.first.inner_text()
                return self._parse_count(text)
        except:
            pass
        return None
    
    async def _get_reposts_count(self, element) -> Optional[int]:
        try:
            reposts_elem = element.locator('button[aria-label*="repost"]')
            if await reposts_elem.count() > 0:
                text = await reposts_elem.first.inner_text()
                return self._parse_count(text)
        except:
            pass
        return None
    
    async def _get_image_urls(self, element) -> List[str]:
        urls: List[str] = []
        try:
            images = await element.locator('img[src*="media"]').all()
            for img in images:
                src = await img.get_attribute('src')
                if src and 'profile' not in src and 'logo' not in src:
                    urls.append(src)
        except:
            pass
        return urls
    
    def _parse_count(self, text: str) -> Optional[int]:
        if not text:
            return None
        try:
            numbers = re.findall(r'[\d,]+', text.replace(',', ''))
            if numbers:
                return int(numbers[0])
        except:
            pass
        return None
    
    async def _scroll_for_more_posts(self) -> None:
        try:
            await self.page.keyboard.press('End')
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            logger.debug(f"Error scrolling: {e}")
